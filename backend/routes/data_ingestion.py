"""
数据接收模块路由 (替代原 Java DataIngestionController)
保持原有URL路径、请求/响应格式及状态码完全一致
"""
from flask import Blueprint, request, jsonify
from utils.redis_client import redis_client
from tasks import process_data_async

data_bp = Blueprint('data', __name__)

@data_bp.route('/ingest', methods=['POST'])
def ingest_data():
    """
    等价于 Java 端: @PostMapping("/ingest")
    """
    payload = request.get_json() or {}
    
    # 使用 Redis 原子递增替代 AtomicLong
    count = 1
    if redis_client:
        try:
            count = redis_client.incr('aiops:event_count')
        except:
            pass # 降级处理
            
    # 将实际数据处理投递到 Celery 异步队列
    process_data_async.delay(payload, count)
    
    # 保持原有 Java 返回格式
    return jsonify({
        "status": "success",
        "eventId": count,
        "message": "Data ingested successfully"
    })

@data_bp.route('/stats', methods=['GET'])
def get_stats():
    """
    等价于 Java 端: @GetMapping("/stats")
    """
    count = 0
    if redis_client:
        try:
            count = int(redis_client.get('aiops:event_count') or 0)
        except:
            pass
            
    return jsonify({
        "totalIngested": count,
        "status": "running"
    })
