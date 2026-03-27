from flask import Blueprint, jsonify, request

from services.audit_service import get_security_overview, list_audit_logs

audit_bp = Blueprint("audit", __name__)


@audit_bp.route("/logs", methods=["GET"])
def logs():
    limit = int(request.args.get("limit", 100))
    data = list_audit_logs(limit)
    return jsonify({"code": 200, "message": "ok", "data": data})


@audit_bp.route("/security-overview", methods=["GET"])
def security_overview():
    limit = int(request.args.get("limit", 500))
    data = get_security_overview(limit)
    return jsonify({"code": 200, "message": "ok", "data": data})
