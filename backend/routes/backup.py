from flask import Blueprint, jsonify, request

from services.backup_service import create_backup_job, list_backup_jobs, restore_backup, run_backup_job
from utils.security import ensure_role, get_request_tenant_id

backup_bp = Blueprint("backup", __name__)


@backup_bp.route("/jobs", methods=["GET"])
def backup_jobs_list():
    tenant_id = get_request_tenant_id(request)
    limit = request.args.get("limit", default=100, type=int)
    data = list_backup_jobs(tenant_id=tenant_id, limit=max(1, min(limit, 300)))
    return jsonify({"code": 200, "message": "ok", "data": data})


@backup_bp.route("/jobs", methods=["POST"])
def backup_create_job():
    deny = ensure_role(request, {"tenant_admin", "platform_admin", "superadmin"})
    if deny:
        return deny

    tenant_id = get_request_tenant_id(request)
    user_id = int(getattr(request, "user", {}).get("user_id") or 0)
    payload = request.get_json(silent=True) or {}
    server_id = int(payload.get("server_id") or 0)
    backup_type = (payload.get("backup_type") or "config").strip().lower()
    target_path = (payload.get("target_path") or "/tmp/aiops_backup").strip()
    if not server_id or backup_type not in {"database", "config"}:
        return jsonify({"code": 400, "message": "server_id/backup_type invalid", "data": None}), 400

    job_id = create_backup_job(tenant_id, user_id, server_id, backup_type, target_path)
    if not job_id:
        return jsonify({"code": 500, "message": "create backup job failed", "data": None}), 500
    result = run_backup_job(job_id)
    code = 200 if result.get("ok") else 500
    return jsonify({"code": code, "message": result.get("message"), "data": {"job_id": job_id, **result}}), code


@backup_bp.route("/restore", methods=["POST"])
def backup_restore():
    deny = ensure_role(request, {"tenant_admin", "platform_admin", "superadmin"})
    if deny:
        return deny

    payload = request.get_json(silent=True) or {}
    confirm = bool(payload.get("confirm", False))
    artifact_id = int(payload.get("artifact_id") or 0)
    if not confirm:
        return jsonify({"code": 400, "message": "confirm=true is required", "data": None}), 400
    if not artifact_id:
        return jsonify({"code": 400, "message": "artifact_id is required", "data": None}), 400

    tenant_id = get_request_tenant_id(request)
    user_id = int(getattr(request, "user", {}).get("user_id") or 0)
    result = restore_backup(tenant_id, user_id, artifact_id)
    code = 200 if result.get("ok") else 500
    return jsonify({"code": code, "message": result.get("message"), "data": result}), code
