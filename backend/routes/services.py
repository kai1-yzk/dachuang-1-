from flask import Blueprint, jsonify, request

from services.audit_service import write_audit_log
from services.service_manager import control_service, list_services, set_autostart
from utils.security import ensure_role

services_bp = Blueprint("services", __name__)


def _service_error_status(result: dict) -> int:
    error_type = (result or {}).get("error_type")
    if error_type == "not_found":
        return 404
    if error_type == "permission_denied":
        return 403
    if error_type == "manager_unavailable":
        return 503
    if error_type == "invalid_argument":
        return 400
    return 500


@services_bp.route("/list", methods=["GET"])
def service_list():
    server_id = request.args.get("server_id", type=int)
    if not server_id:
        return jsonify({"code": 400, "message": "server_id is required", "data": None}), 400
    try:
        rows = list_services(server_id)
        return jsonify({"code": 200, "message": "ok", "data": rows})
    except Exception as e:
        return jsonify({"code": 500, "message": f"load service list failed: {str(e)}", "data": None}), 500


@services_bp.route("/control", methods=["POST"])
def service_control():
    deny = ensure_role(request, {"tenant_admin", "tenant_operator", "platform_admin", "superadmin", "operator"})
    if deny:
        return deny

    payload = request.get_json(silent=True) or {}
    server_id = int(payload.get("server_id") or 0)
    service_name = (payload.get("service_name") or "").strip()
    action = (payload.get("action") or "").strip().lower()
    if not server_id or not service_name or action not in {"start", "stop", "restart"}:
        return jsonify({"code": 400, "message": "server_id/service_name/action invalid", "data": None}), 400

    result = control_service(server_id, service_name, action)
    write_audit_log({
        "user_id": getattr(request, "user", {}).get("user_id"),
        "username": getattr(request, "user", {}).get("username"),
        "role_name": getattr(request, "user", {}).get("role"),
        "server_id": server_id,
        "command_raw": f"service {action} {service_name}",
        "command_parsed": f"systemctl {action} {service_name}",
        "risk_score": 45,
        "risk_level": "MEDIUM",
        "action": "service_control",
        "result": "success" if result.get("ok") else "failed",
        "detail": result.get("message"),
    })
    status_code = 200 if result.get("ok") else _service_error_status(result)
    return jsonify({"code": status_code, "message": result.get("message"), "data": result}), status_code


@services_bp.route("/autostart", methods=["POST"])
def service_autostart():
    deny = ensure_role(request, {"tenant_admin", "tenant_operator", "platform_admin", "superadmin", "operator"})
    if deny:
        return deny

    payload = request.get_json(silent=True) or {}
    server_id = int(payload.get("server_id") or 0)
    service_name = (payload.get("service_name") or "").strip()
    enabled = bool(payload.get("enabled", True))
    if not server_id or not service_name:
        return jsonify({"code": 400, "message": "server_id/service_name invalid", "data": None}), 400

    result = set_autostart(server_id, service_name, enabled)
    write_audit_log({
        "user_id": getattr(request, "user", {}).get("user_id"),
        "username": getattr(request, "user", {}).get("username"),
        "role_name": getattr(request, "user", {}).get("role"),
        "server_id": server_id,
        "command_raw": f"service {'enable' if enabled else 'disable'} {service_name}",
        "command_parsed": f"systemctl {'enable' if enabled else 'disable'} {service_name}",
        "risk_score": 30,
        "risk_level": "LOW",
        "action": "service_autostart",
        "result": "success" if result.get("ok") else "failed",
        "detail": result.get("message"),
    })
    status_code = 200 if result.get("ok") else _service_error_status(result)
    return jsonify({"code": status_code, "message": result.get("message"), "data": result}), status_code
