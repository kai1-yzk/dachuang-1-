from flask import Blueprint, jsonify, request

from services.batch_exec_service import approve_batch_job, create_batch_job, job_results, list_batch_jobs
from utils.security import ensure_role, get_request_tenant_id

batch_bp = Blueprint("batch", __name__)


@batch_bp.route("/jobs", methods=["GET"])
def batch_jobs():
    tenant_id = get_request_tenant_id(request)
    limit = request.args.get("limit", default=100, type=int)
    rows = list_batch_jobs(tenant_id, max(1, min(limit, 200)))
    return jsonify({"code": 200, "message": "ok", "data": rows})


@batch_bp.route("/jobs", methods=["POST"])
def batch_create():
    deny = ensure_role(request, {"tenant_admin", "platform_admin", "superadmin"})
    if deny:
        return deny

    payload = request.get_json(silent=True) or {}
    command = (payload.get("command") or "").strip()
    server_ids = payload.get("server_ids") or []
    if not command or not isinstance(server_ids, list) or not server_ids:
        return jsonify({"code": 400, "message": "command and server_ids are required", "data": None}), 400

    tenant_id = get_request_tenant_id(request)
    user_id = int(getattr(request, "user", {}).get("user_id") or 0)
    job_id = create_batch_job(tenant_id, user_id, command, [int(x) for x in server_ids])
    if not job_id:
        return jsonify({"code": 500, "message": "create job failed", "data": None}), 500
    return jsonify({"code": 200, "message": "approval required", "data": {"job_id": job_id, "status": "pending_approval"}})


@batch_bp.route("/jobs/<int:job_id>/approve", methods=["POST"])
def batch_approve(job_id: int):
    deny = ensure_role(request, {"tenant_admin", "platform_admin", "superadmin"})
    if deny:
        return deny

    payload = request.get_json(silent=True) or {}
    approve = bool(payload.get("approve", True))
    tenant_id = get_request_tenant_id(request)
    user_id = int(getattr(request, "user", {}).get("user_id") or 0)
    result = approve_batch_job(tenant_id, job_id, user_id, approve)
    code = 200 if result.get("ok") else 500
    return jsonify({"code": code, "message": result.get("message"), "data": result}), code


@batch_bp.route("/jobs/<int:job_id>/results", methods=["GET"])
def batch_results(job_id: int):
    tenant_id = get_request_tenant_id(request)
    rows = job_results(tenant_id, job_id)
    return jsonify({"code": 200, "message": "ok", "data": rows})
