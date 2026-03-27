from flask import Blueprint, jsonify, request

from services.log_service import anomaly_clusters, search_logs
from utils.security import get_request_tenant_id

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/search", methods=["GET"])
def logs_search():
    tenant_id = get_request_tenant_id(request)
    keyword = request.args.get("keyword", default="")
    level = request.args.get("level", default="")
    server_id = request.args.get("server_id", type=int)
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    page = request.args.get("page", default=1, type=int)
    page_size = request.args.get("page_size", default=50, type=int)

    data = search_logs(
        tenant_id=tenant_id,
        keyword=keyword,
        level=level,
        server_id=server_id,
        start_time=start_time,
        end_time=end_time,
        page=max(1, page),
        page_size=max(1, min(page_size, 200)),
    )
    return jsonify({"code": 200, "message": "ok", "data": data})


@logs_bp.route("/anomaly-clusters", methods=["GET"])
def logs_clusters():
    tenant_id = get_request_tenant_id(request)
    limit = request.args.get("limit", default=300, type=int)
    data = anomaly_clusters(tenant_id=tenant_id, limit=max(50, min(limit, 1000)))
    return jsonify({"code": 200, "message": "ok", "data": data})
