from flask import Blueprint, jsonify, request

from services.file_service import delete_path, list_dir, mkdir, read_file_text, write_file_text
from utils.security import ensure_role

files_bp = Blueprint("files", __name__)


@files_bp.route("/list", methods=["GET"])
def file_list():
    server_id = request.args.get("server_id", type=int)
    path = request.args.get("path", default="/")
    if not server_id:
        return jsonify({"code": 400, "message": "server_id is required", "data": None}), 400
    items = list_dir(server_id, path)
    return jsonify({"code": 200, "message": "ok", "data": {"path": path, "items": items}})


@files_bp.route("/read", methods=["GET"])
def file_read():
    server_id = request.args.get("server_id", type=int)
    path = request.args.get("path", default="")
    if not server_id or not path:
        return jsonify({"code": 400, "message": "server_id and path are required", "data": None}), 400
    data = read_file_text(server_id, path)
    code = 200 if data.get("ok") else 500
    return jsonify({"code": code, "message": "ok" if data.get("ok") else data.get("message"), "data": data}), code


@files_bp.route("/write", methods=["POST"])
def file_write():
    deny = ensure_role(request, {"tenant_admin", "tenant_operator", "platform_admin", "superadmin", "operator"})
    if deny:
        return deny

    payload = request.get_json(silent=True) or {}
    server_id = int(payload.get("server_id") or 0)
    path = (payload.get("path") or "").strip()
    content = payload.get("content") or ""
    if not server_id or not path:
        return jsonify({"code": 400, "message": "server_id and path are required", "data": None}), 400

    data = write_file_text(server_id, path, content)
    code = 200 if data.get("ok") else 500
    return jsonify({"code": code, "message": data.get("message"), "data": data}), code


@files_bp.route("/mkdir", methods=["POST"])
def file_mkdir():
    deny = ensure_role(request, {"tenant_admin", "tenant_operator", "platform_admin", "superadmin", "operator"})
    if deny:
        return deny

    payload = request.get_json(silent=True) or {}
    server_id = int(payload.get("server_id") or 0)
    path = (payload.get("path") or "").strip()
    if not server_id or not path:
        return jsonify({"code": 400, "message": "server_id and path are required", "data": None}), 400

    data = mkdir(server_id, path)
    code = 200 if data.get("ok") else 500
    return jsonify({"code": code, "message": data.get("message"), "data": data}), code


@files_bp.route("/delete", methods=["POST"])
def file_delete():
    deny = ensure_role(request, {"tenant_admin", "tenant_operator", "platform_admin", "superadmin", "operator"})
    if deny:
        return deny

    payload = request.get_json(silent=True) or {}
    server_id = int(payload.get("server_id") or 0)
    path = (payload.get("path") or "").strip()
    recursive = bool(payload.get("recursive", False))
    confirm = bool(payload.get("confirm", False))
    if not confirm:
        return jsonify({"code": 400, "message": "confirm=true is required", "data": None}), 400
    if not server_id or not path:
        return jsonify({"code": 400, "message": "server_id and path are required", "data": None}), 400

    data = delete_path(server_id, path, recursive=recursive)
    code = 200 if data.get("ok") else 500
    return jsonify({"code": code, "message": data.get("message"), "data": data}), code
