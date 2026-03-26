from flask import Blueprint, jsonify, request

from services.agent_service import heartbeat, list_servers, register_agent, save_metrics

agents_bp = Blueprint("agents", __name__)


@agents_bp.route("/register", methods=["POST"])
def register():
    payload = request.get_json() or {}
    result = register_agent(payload)
    if not result["ok"]:
        return jsonify({"code": 400, "message": result["message"], "data": None}), 400
    return jsonify({"code": 200, "message": "agent registered", "data": result["data"]})


@agents_bp.route("/heartbeat", methods=["POST"])
def beat():
    payload = request.get_json() or {}
    ok = heartbeat(
        int(payload.get("server_id") or 0),
        payload.get("agent_token") or "",
        payload.get("stats") or {},
    )
    if not ok:
        return jsonify({"code": 401, "message": "invalid server_id or token", "data": None}), 401
    return jsonify({"code": 200, "message": "heartbeat updated", "data": None})


@agents_bp.route("/metrics", methods=["POST"])
def metrics():
    payload = request.get_json() or {}
    ok = save_metrics(
        int(payload.get("server_id") or 0),
        payload.get("agent_token") or "",
        payload.get("metrics") or {},
    )
    if not ok:
        return jsonify({"code": 401, "message": "invalid server_id or token", "data": None}), 401
    return jsonify({"code": 200, "message": "metrics saved", "data": None})


@agents_bp.route("/servers", methods=["GET"])
def servers():
    data = list_servers()
    return jsonify({"code": 200, "message": "ok", "data": data})


@agents_bp.route("/discover", methods=["POST"])
def discover():
    payload = request.get_json() or {}
    targets = payload.get("targets") or []
    protocol = payload.get("protocol", "ssh")

    discovered = []
    for target in targets:
        item = {
            "hostname": target.get("hostname") or f"auto-{target.get('ip', 'unknown')}",
            "ip": target.get("ip"),
            "port": int(target.get("port") or (161 if protocol == "snmp" else 22)),
            "protocol": protocol,
            "tags": ["auto-discovery", protocol],
            "capabilities": {"metrics": True, "command": protocol == "ssh"},
        }
        if not item["ip"]:
            continue
        result = register_agent(item)
        if result["ok"]:
            discovered.append(result["data"])

    return jsonify({"code": 200, "message": "discover finished", "data": discovered})
