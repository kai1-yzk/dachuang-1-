import secrets
from typing import Any, Dict, List

from utils.db import execute_query, execute_update


def _to_json(data: Dict[str, Any]) -> str:
    import json

    return json.dumps(data, ensure_ascii=False)


def register_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    hostname = payload.get("hostname") or "unknown"
    ip = payload.get("ip") or ""
    port = int(payload.get("port") or 22)
    protocol = payload.get("protocol") or "agent"
    tags = payload.get("tags") or []
    capabilities = payload.get("capabilities") or {}

    if not ip:
        return {"ok": False, "message": "ip is required"}

    token = secrets.token_urlsafe(24)

    existing = execute_query("SELECT id FROM servers WHERE ip=%s AND port=%s", (ip, port))
    if existing:
        server_id = existing[0]["id"]
        execute_update(
            """
            UPDATE servers
            SET hostname=%s, protocol=%s, status='online',
                tags=%s, capabilities=%s, agent_token=%s,
                last_seen=NOW(), updated_at=NOW()
            WHERE id=%s
            """,
            (hostname, protocol, _to_json({"tags": tags}), _to_json(capabilities), token, server_id),
        )
    else:
        execute_update(
            """
            INSERT INTO servers
            (hostname, ip, port, protocol, auth_type, status, tags, capabilities, agent_token, last_seen, created_at, updated_at)
            VALUES (%s, %s, %s, %s, 'agent_token', 'online', %s, %s, %s, NOW(), NOW(), NOW())
            """,
            (hostname, ip, port, protocol, _to_json({"tags": tags}), _to_json(capabilities), token),
        )
        created = execute_query("SELECT id FROM servers WHERE ip=%s AND port=%s ORDER BY id DESC LIMIT 1", (ip, port))
        server_id = created[0]["id"] if created else None

    return {
        "ok": True,
        "data": {
            "server_id": server_id,
            "agent_token": token,
            "heartbeat_interval_sec": 15,
        },
    }


def heartbeat(server_id: int, agent_token: str, stats: Dict[str, Any]) -> bool:
    rows = execute_update(
        """
        UPDATE servers
        SET status='online', last_seen=NOW(), updated_at=NOW(), runtime_stats=%s
        WHERE id=%s AND agent_token=%s
        """,
        (_to_json(stats or {}), server_id, agent_token),
    )
    return rows > 0


def save_metrics(server_id: int, agent_token: str, metrics: Dict[str, Any]) -> bool:
    auth = execute_query("SELECT id FROM servers WHERE id=%s AND agent_token=%s", (server_id, agent_token))
    if not auth:
        return False

    execute_update(
        """
        INSERT INTO server_metrics
        (server_id, cpu_usage, memory_usage, disk_usage, network_rx_mb, network_tx_mb, metric_payload, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """,
        (
            server_id,
            float(metrics.get("cpu", 0.0)),
            float(metrics.get("memory", 0.0)),
            float(metrics.get("disk", 0.0)),
            float(metrics.get("network_rx", 0.0)),
            float(metrics.get("network_tx", 0.0)),
            _to_json(metrics),
        ),
    )
    return True


def list_servers() -> List[Dict[str, Any]]:
    return execute_query(
        """
        SELECT id, hostname, ip, port, protocol, status, last_seen, created_at, updated_at
        FROM servers
        ORDER BY updated_at DESC
        """
    )
