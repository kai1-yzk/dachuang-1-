import re
import os
import threading
import time
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

_AUTO_COLLECTOR_STARTED = False
_AUTO_COLLECTOR_LOCK = threading.Lock()


def _to_positive_int(raw, default_value: int) -> int:
    try:
        value = int(raw)
        return value if value > 0 else default_value
    except Exception:
        return default_value


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


def start_auto_collector() -> None:
    global _AUTO_COLLECTOR_STARTED
    with _AUTO_COLLECTOR_LOCK:
        if _AUTO_COLLECTOR_STARTED:
            return
        _AUTO_COLLECTOR_STARTED = True

    enabled = str(os.environ.get("AUTO_COLLECT_ENABLED", "1")).strip().lower() in ("1", "true", "yes", "on")
    if not enabled:
        return

    interval_seconds = _to_positive_int(os.environ.get("AUTO_COLLECT_INTERVAL_SECONDS", "5"), 5)

    def _loop():
        while True:
            try:
                collect_all_ssh_metrics()
            except Exception:
                pass
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_loop, name="aiops-metrics-auto-collector", daemon=True)
    thread.start()


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


def get_metric_trend(metric: str, period: str, server_id: Optional[int] = None, start_time: Optional[str] = None, end_time: Optional[str] = None) -> Dict:
    metric_map = {
        "cpu": "cpu_usage",
        "memory": "memory_usage",
        "disk": "disk_usage",
        "network": "(network_rx_mb + network_tx_mb)",
    }
    metric_key = (metric or "cpu").strip().lower()
    metric_sql = metric_map.get(metric_key, "cpu_usage")

    where_parts = []
    args: List = []

    if server_id:
        where_parts.append("server_id=%s")
        args.append(server_id)

    if period == "1h":
        where_parts.append("created_at >= NOW() - INTERVAL 1 HOUR")
    elif period == "6h":
        where_parts.append("created_at >= NOW() - INTERVAL 6 HOUR")
    elif period == "24h":
        where_parts.append("created_at >= NOW() - INTERVAL 24 HOUR")
    elif period == "custom" and start_time and end_time:
        where_parts.append("created_at BETWEEN %s AND %s")
        args.extend([start_time, end_time])
    else:
        where_parts.append("created_at >= NOW() - INTERVAL 1 HOUR")

    where_sql = "WHERE " + " AND ".join(where_parts) if where_parts else ""

    rows = execute_query(
        f"""
        SELECT DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS ts,
               {metric_sql} AS metric_value
        FROM server_metrics
        {where_sql}
        ORDER BY created_at ASC
        """,
        tuple(args) if args else None,
    )

    points = [
        {
            "time": row.get("ts"),
            "value": round(float(row.get("metric_value") or 0.0), 3),
        }
        for row in (rows or [])
    ]

    latest = points[-1]["value"] if points else 0.0
    return {
        "metric": metric_key,
        "period": period,
        "count": len(points),
        "latest": latest,
        "points": points,
    }


def get_k8s_overview(server_id: Optional[int] = None) -> Dict:
    servers = list_ssh_servers()
    if not servers:
        return {
            "available": False,
            "message": "no managed ssh server",
            "server_id": None,
            "summary": {},
            "nodes": [],
        }

    target_server_id = server_id or int(servers[0]["id"])

    try:
        nodes_result = run_command_stream(target_server_id, "kubectl get nodes --no-headers 2>/dev/null || true", timeout=15)
        pods_result = run_command_stream(target_server_id, "kubectl get pods -A --no-headers 2>/dev/null || true", timeout=15)
        deploy_result = run_command_stream(target_server_id, "kubectl get deploy -A --no-headers 2>/dev/null || true", timeout=15)

        nodes_text = "".join(x.get("text", "") for x in nodes_result.get("chunks", []) if x.get("stream") == "stdout")
        pods_text = "".join(x.get("text", "") for x in pods_result.get("chunks", []) if x.get("stream") == "stdout")
        deploy_text = "".join(x.get("text", "") for x in deploy_result.get("chunks", []) if x.get("stream") == "stdout")

        node_lines = [line.strip() for line in nodes_text.splitlines() if line.strip()]
        pod_lines = [line.strip() for line in pods_text.splitlines() if line.strip()]
        deploy_lines = [line.strip() for line in deploy_text.splitlines() if line.strip()]

        if not node_lines and not pod_lines:
            return {
                "available": False,
                "message": "kubectl not available or no cluster context",
                "server_id": target_server_id,
                "summary": {},
                "nodes": [],
            }

        nodes = []
        ready_nodes = 0
        for ln in node_lines:
            cols = ln.split()
            if len(cols) < 2:
                continue
            name = cols[0]
            status = cols[1]
            if "Ready" in status:
                ready_nodes += 1
            nodes.append({"name": name, "status": status})

        running_pods = 0
        for ln in pod_lines:
            cols = ln.split()
            if len(cols) >= 4 and cols[3].lower() == "running":
                running_pods += 1

        return {
            "available": True,
            "message": "ok",
            "server_id": target_server_id,
            "summary": {
                "nodes_total": len(nodes),
                "nodes_ready": ready_nodes,
                "pods_total": len(pod_lines),
                "pods_running": running_pods,
                "deployments_total": len(deploy_lines),
            },
            "nodes": nodes[:20],
        }
    except Exception as e:
        return {
            "available": False,
            "message": str(e),
            "server_id": target_server_id,
            "summary": {},
            "nodes": [],
        }
