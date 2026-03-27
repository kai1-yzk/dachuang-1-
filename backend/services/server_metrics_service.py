import re
from typing import Dict, List, Optional

from services.ssh_service import run_command_stream
from utils.db import execute_query, execute_update


METRICS_COMMAND = (
    "LANG=C; "
    "CPU=$(top -bn1 | awk -F'[, ]+' '/Cpu\\(s\\)/ {print 100-$8; exit}'); "
    "MEM=$(free | awk '/Mem:/ {printf(\"%.2f\", $3/$2*100)}'); "
    "DISK=$(df -P / | awk 'NR==2 {gsub(\"%\",\"\",$5); print $5}'); "
    "NET=$(cat /proc/net/dev | awk 'NR>2 {rx+=$2; tx+=$10} END {printf(\"%.2f\", (rx+tx)/1024/1024)}'); "
    "echo CPU=$CPU MEM=$MEM DISK=$DISK NET=$NET"
)


def _parse_metrics_text(text: str) -> Optional[Dict[str, float]]:
    match = re.search(r"CPU=([0-9.]+)\s+MEM=([0-9.]+)\s+DISK=([0-9.]+)\s+NET=([0-9.]+)", text)
    if not match:
        return None
    return {
        "cpu": float(match.group(1)),
        "memory": float(match.group(2)),
        "disk": float(match.group(3)),
        "network": float(match.group(4)),
    }


def list_ssh_servers() -> List[Dict]:
    rows = execute_query(
        """
        SELECT id, hostname, ip, port, status
        FROM servers
        WHERE protocol='ssh'
        ORDER BY id ASC
        """
    )
    if rows:
        return rows

    return execute_query(
        """
        SELECT id, hostname, ip, port, status
        FROM servers
        WHERE auth_type IN ('password', 'key')
        ORDER BY id ASC
        """
    )


def collect_server_metrics(server_id: int) -> Dict:
    try:
        result = run_command_stream(server_id, METRICS_COMMAND, timeout=20)
        output_text = "".join(chunk.get("text", "") for chunk in result.get("chunks", []))
        parsed = _parse_metrics_text(output_text)
        if not parsed:
            raise ValueError("failed to parse metrics output")

        execute_update(
            """
            INSERT INTO server_metrics
            (server_id, cpu_usage, memory_usage, disk_usage, network_rx_mb, network_tx_mb, metric_payload, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                server_id,
                parsed["cpu"],
                parsed["memory"],
                parsed["disk"],
                parsed["network"],
                0.0,
                '{"source":"ssh_terminal"}',
            ),
        )
        execute_update(
            "UPDATE servers SET status='online', last_seen=NOW(), updated_at=NOW() WHERE id=%s",
            (server_id,),
        )
        return {"server_id": server_id, "ok": True, "metrics": parsed}
    except Exception as e:
        execute_update(
            "UPDATE servers SET status='offline', updated_at=NOW() WHERE id=%s",
            (server_id,),
        )
        return {"server_id": server_id, "ok": False, "error": str(e)}


def collect_all_ssh_metrics() -> List[Dict]:
    servers = list_ssh_servers()
    results = []
    for server in servers:
        results.append(collect_server_metrics(int(server["id"])))
    return results


def get_dashboard_payload(server_id: Optional[int] = None, points: int = 12) -> Dict:
    if server_id:
        where_sql = "WHERE m.server_id=%s"
        where_args = (server_id,)
    else:
        where_sql = ""
        where_args = None

    summary_rows = execute_query(
        f"""
        SELECT AVG(m.cpu_usage) AS cpu_avg,
               AVG(m.memory_usage) AS memory_avg,
               AVG(m.disk_usage) AS disk_avg,
               AVG(m.network_rx_mb + m.network_tx_mb) AS network_avg
        FROM (
            SELECT sm.*
            FROM server_metrics sm
            JOIN (
                SELECT server_id, MAX(id) AS max_id
                FROM server_metrics
                GROUP BY server_id
            ) t ON t.max_id = sm.id
        ) m
        {where_sql}
        """,
        where_args,
    )

    trend_rows = execute_query(
        f"""
         SELECT DATE_FORMAT(t.bucket, '%%H:%%i:%%s') AS ts,
             AVG(t.cpu_usage) AS cpu,
             AVG(t.memory_usage) AS memory
         FROM (
             SELECT DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS bucket,
                 cpu_usage,
                 memory_usage
             FROM server_metrics
             {'WHERE server_id=%s' if server_id else ''}
         ) t
         GROUP BY t.bucket
         ORDER BY t.bucket DESC
        LIMIT %s
        """,
        ((server_id, points) if server_id else (points,)),
    )
    trend_rows = list(trend_rows or [])
    trend_rows.reverse()

    servers = list_ssh_servers()
    online_count = len([s for s in servers if (s.get("status") or "").lower() == "online"])

    summary = summary_rows[0] if summary_rows else {}
    return {
        "servers": {
            "total": len(servers),
            "online": online_count,
            "items": servers,
        },
        "summary": {
            "cpu": round(float(summary.get("cpu_avg") or 0), 2),
            "memory": round(float(summary.get("memory_avg") or 0), 2),
            "disk": round(float(summary.get("disk_avg") or 0), 2),
            "network": round(float(summary.get("network_avg") or 0), 2),
        },
        "trend": [
            {
                "time": row.get("ts"),
                "cpu": round(float(row.get("cpu") or 0), 2),
                "memory": round(float(row.get("memory") or 0), 2),
            }
            for row in trend_rows
        ],
    }
