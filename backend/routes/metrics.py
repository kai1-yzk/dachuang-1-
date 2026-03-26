"""
监控指标路由
创建时间: 2026-03-24
功能说明: 返回服务器核心运行指标数据
"""
from flask import Blueprint, jsonify
import psutil
import platform

metrics_bp = Blueprint('metrics', __name__)

@metrics_bp.route('/current', methods=['GET'])
def get_current_metrics():
    """
    获取实时服务器运行指标
    入参: None
    出参: JSON (cpu, memory, disk_usage)
    核心逻辑: 使用 psutil 收集系统实时指标
    """
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    data = {
        "os": platform.system(),
        "cpu_usage_percent": cpu_percent,
        "memory_total_gb": round(memory.total / (1024**3), 2),
        "memory_used_percent": memory.percent,
        "disk_total_gb": round(disk.total / (1024**3), 2),
        "disk_used_percent": disk.percent
    }
    
    return jsonify({
        "code": 200,
        "message": "Success",
        "data": data
    })
