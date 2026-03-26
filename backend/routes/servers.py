import json

from flask import Blueprint, jsonify, request

from services.agent_service import list_servers
from utils.db import execute_query, execute_update

servers_bp = Blueprint("servers", __name__)


@servers_bp.route("/", methods=["GET"])
def list_all():
    return jsonify({"code": 200, "message": "ok", "data": list_servers()})


@servers_bp.route("/<int:server_id>", methods=["GET"])
def detail(server_id: int):
    rows = execute_query(
        """
        SELECT s.id, s.hostname, s.ip, s.port, s.protocol, s.status, s.last_seen,
               m.cpu_usage, m.memory_usage, m.disk_usage, m.network_rx_mb, m.network_tx_mb, m.created_at
        FROM servers s
        LEFT JOIN server_metrics m ON m.server_id = s.id
        WHERE s.id = %s
        ORDER BY m.id DESC
        LIMIT 30
        """,
        (server_id,),
    )
    if not rows:
        return jsonify({"code": 404, "message": "server not found", "data": None}), 404
    return jsonify({"code": 200, "message": "ok", "data": rows})


@servers_bp.route("/<int:server_id>/ssh-config", methods=["PUT"])
def update_ssh_config(server_id: int):
    payload = request.get_json(silent=True) or {}
    auth_type = (payload.get("auth_type") or "password").lower()
    ssh_username = (payload.get("ssh_username") or "").strip()
    ssh_password = payload.get("ssh_password")
    private_key = payload.get("private_key")
    private_key_passphrase = payload.get("private_key_passphrase")
    connect_timeout = int(payload.get("connect_timeout") or 15)

    if auth_type not in ("password", "key"):
        return jsonify({"code": 400, "message": "auth_type must be password or key", "data": None}), 400
    if not ssh_username:
        return jsonify({"code": 400, "message": "ssh_username is required", "data": None}), 400
    if auth_type == "password" and not ssh_password:
        return jsonify({"code": 400, "message": "ssh_password is required for password auth", "data": None}), 400
    if auth_type == "key" and not private_key:
        return jsonify({"code": 400, "message": "private_key is required for key auth", "data": None}), 400

    server = execute_query("SELECT id FROM servers WHERE id=%s LIMIT 1", (server_id,))
    if not server:
        return jsonify({"code": 404, "message": "server not found", "data": None}), 404

    auth_data = {
        "ssh_username": ssh_username,
        "ssh_password": ssh_password if auth_type == "password" else None,
        "private_key": private_key if auth_type == "key" else None,
        "private_key_passphrase": private_key_passphrase if auth_type == "key" else None,
        "connect_timeout": connect_timeout,
    }

    execute_query_res = execute_query("SELECT auth_data FROM servers WHERE id=%s LIMIT 1", (server_id,))
    if execute_query_res and execute_query_res[0].get("auth_data"):
        try:
            existing = json.loads(execute_query_res[0]["auth_data"])
            for key, value in existing.items():
                if key not in auth_data:
                    auth_data[key] = value
        except Exception:
            pass

    auth_data_json = json.dumps(auth_data, ensure_ascii=False)
    execute_update(
        """
        UPDATE servers
        SET auth_type=%s, auth_data=%s, updated_at=NOW()
        WHERE id=%s
        """,
        (auth_type, auth_data_json, server_id),
    )

    return jsonify(
        {
            "code": 200,
            "message": "ssh config updated",
            "data": {
                "server_id": server_id,
                "auth_type": auth_type,
                "ssh_username": ssh_username,
                "connect_timeout": connect_timeout,
            },
        }
    )
