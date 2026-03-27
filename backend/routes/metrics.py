"""监控指标路由：支持 SSH 实时采集与大屏展示。"""
from flask import Blueprint, jsonify, request

from services.server_metrics_service import collect_all_ssh_metrics, get_dashboard_payload

metrics_bp = Blueprint('metrics', __name__)

@metrics_bp.route('/current', methods=['GET'])
def get_current_metrics():
    """兼容保留：返回聚合后的当前指标。"""
    data = get_dashboard_payload(server_id=None, points=1)
    return jsonify({
        "code": 200,
        "message": "Success",
        "data": data.get("summary", {})
    })


@metrics_bp.route('/collect', methods=['POST'])
def collect_metrics_from_ssh_servers():
    """手动触发一次对已接入 SSH 服务器的实时采集。"""
    results = collect_all_ssh_metrics()
    ok_count = len([x for x in results if x.get("ok")])
    return jsonify({
        "code": 200,
        "message": "collect finished",
        "data": {
            "total": len(results),
            "success": ok_count,
            "failed": len(results) - ok_count,
            "results": results,
        }
    })


@metrics_bp.route('/dashboard', methods=['GET'])
def dashboard_metrics():
    """返回监控大屏需要的真实数据；可选触发即时采集。"""
    server_id = request.args.get('server_id', type=int)
    points = request.args.get('points', default=12, type=int)
    collect_now = request.args.get('collect_now', default='1')

    collected = None
    if str(collect_now).strip() in ('1', 'true', 'True'):
        collected = collect_all_ssh_metrics()

    payload = get_dashboard_payload(server_id=server_id, points=max(6, min(points, 60)))
    return jsonify({
        "code": 200,
        "message": "ok",
        "data": {
            **payload,
            "collect_result": collected,
        }
    })
