from flask import Blueprint, jsonify, request

from utils.db import execute_query, execute_update
from utils.security import ensure_role, get_request_tenant_id

tenants_bp = Blueprint("tenants", __name__)


@tenants_bp.route("/", methods=["GET"])
def list_tenants():
    deny = ensure_role(request, {"platform_admin", "superadmin", "tenant_admin", "operator"})
    if deny:
        return deny

    rows = execute_query("SELECT id, name, status, created_at FROM tenants ORDER BY id DESC")
    return jsonify({"code": 200, "message": "ok", "data": rows})


@tenants_bp.route("/", methods=["POST"])
def create_tenant():
    deny = ensure_role(request, {"platform_admin", "superadmin", "operator"})
    if deny:
        return deny

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"code": 400, "message": "name is required", "data": None}), 400

    execute_update("INSERT INTO tenants (name, status, created_at, updated_at) VALUES (%s, 'active', NOW(), NOW())", (name,))
    row = execute_query("SELECT id, name, status FROM tenants WHERE name=%s ORDER BY id DESC LIMIT 1", (name,))
    return jsonify({"code": 200, "message": "created", "data": row[0] if row else None})


@tenants_bp.route("/context", methods=["GET"])
def current_tenant_context():
    tenant_id = get_request_tenant_id(request)
    role = getattr(request, "user", {}).get("role", "operator")
    return jsonify({"code": 200, "message": "ok", "data": {"tenant_id": tenant_id, "role": role}})
