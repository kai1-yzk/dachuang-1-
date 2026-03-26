from flask import Blueprint, jsonify

from services.agent_service import list_servers
from utils.db import execute_query

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
