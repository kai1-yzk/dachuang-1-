"""
AI 分析与预测路由
创建时间: 2026-03-24
功能说明: 接收预处理后的数据并进行推理，以及提供自然语言运维命令校验
"""
from flask import Blueprint, jsonify, request
from utils.security import validate_ai_command
from services.command_risk_service import evaluate_risk, to_command
from services.audit_service import write_audit_log
from utils.db import execute_query
from utils.security import get_request_tenant_id

ai_bp = Blueprint('ai', __name__)

_PREDICTOR_CACHE = None
_SERVERS_HAS_TENANT_ID = None


def _servers_has_tenant_id_column():
    global _SERVERS_HAS_TENANT_ID
    if _SERVERS_HAS_TENANT_ID is None:
        rows = execute_query("SHOW COLUMNS FROM servers LIKE %s", ("tenant_id",))
        _SERVERS_HAS_TENANT_ID = bool(rows)
    return _SERVERS_HAS_TENANT_ID


def _load_server_predictor():
    global _PREDICTOR_CACHE
    if _PREDICTOR_CACHE is not None:
        return _PREDICTOR_CACHE

    import importlib.util
    import sys
    from pathlib import Path

    ai_engine_path = Path(__file__).resolve().parents[2] / 'ai_engine'
    model_module_path = ai_engine_path / 'models'
    if str(model_module_path) not in sys.path:
        sys.path.append(str(model_module_path))

    artifact = ai_engine_path / 'models' / 'server_anomaly_artifacts.pkl'
    if not artifact.exists():
        raise FileNotFoundError(f"model artifact not found: {artifact}")

    predictor_module_file = model_module_path / 'server_anomaly_predictor.py'
    if not predictor_module_file.exists():
        raise FileNotFoundError(f"predictor module not found: {predictor_module_file}")

    spec = importlib.util.spec_from_file_location("server_anomaly_predictor", str(predictor_module_file))
    if spec is None or spec.loader is None:
        raise ImportError("failed to load predictor module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ServerAnomalyPredictor = getattr(module, "ServerAnomalyPredictor")

    _PREDICTOR_CACHE = ServerAnomalyPredictor.load(artifact)
    return _PREDICTOR_CACHE


def _load_server_metric_series(server_id: int, tenant_id: int, limit: int = 120):
    if _servers_has_tenant_id_column():
        rows = execute_query(
            """
            SELECT cpu_usage, memory_usage, disk_usage,
                   (network_rx_mb + network_tx_mb) AS network_total,
                   UNIX_TIMESTAMP(created_at) AS ts
            FROM server_metrics
            WHERE server_id=%s AND server_id IN (SELECT id FROM servers WHERE id=%s AND tenant_id=%s)
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (server_id, server_id, tenant_id, limit),
        )
    else:
        rows = execute_query(
            """
            SELECT cpu_usage, memory_usage, disk_usage,
                   (network_rx_mb + network_tx_mb) AS network_total,
                   UNIX_TIMESTAMP(created_at) AS ts
            FROM server_metrics
            WHERE server_id=%s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (server_id, limit),
        )
    if not rows:
        return None

    rows = list(rows)[::-1]
    return {
        "timestamps": [int(r.get('ts') or 0) for r in rows],
        "series": {
            "cpu_usage": [float(r.get('cpu_usage') or 0.0) for r in rows],
            "memory_usage": [float(r.get('memory_usage') or 0.0) for r in rows],
            "disk_usage": [float(r.get('disk_usage') or 0.0) for r in rows],
            "network_total": [float(r.get('network_total') or 0.0) for r in rows],
        },
    }

@ai_bp.route('/predict', methods=['POST'])
def predict_anomaly():
    """
    模型推理接口
    入参: JSON (服务器特征数据)
    出参: JSON (预测结果、异常类型)
    """
    data = request.get_json() or {}
    server_id = data.get('server_id')

    try:
        predictor = _load_server_predictor()
    except Exception as e:
        return jsonify({"code": 500, "message": f"Model not ready: {str(e)}"}), 500

    try:
        if server_id:
            packet = _load_server_metric_series(int(server_id), get_request_tenant_id(request), limit=120)
            if not packet:
                return jsonify({"code": 404, "message": "No server metrics found"}), 404
            result = predictor.predict_multivariate(packet['series'], packet['timestamps'])
        else:
            values = data.get('values') or data.get('features')
            if not values:
                return jsonify({"code": 400, "message": "Missing values or server_id"}), 400
            result = predictor.predict_series(values)

        return jsonify({
            "code": 200,
            "message": "Prediction Success",
            "data": {
                **result,
                "suggestion": "检测到服务器异常，建议检查负载/进程/网络" if result.get('is_anomaly') else "服务器负载平稳，无需干预"
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "message": f"Prediction failed: {str(e)}"}), 500


@ai_bp.route('/predict/server/<int:server_id>', methods=['GET'])
def predict_server_anomaly(server_id: int):
    """按 server_id 从 server_metrics 读取最近数据并预测异常。"""
    try:
        predictor = _load_server_predictor()
        packet = _load_server_metric_series(server_id, get_request_tenant_id(request), limit=120)
        if not packet:
            return jsonify({"code": 404, "message": "No server metrics found"}), 404

        result = predictor.predict_multivariate(packet['series'], packet['timestamps'])
        return jsonify({
            "code": 200,
            "message": "Prediction Success",
            "data": {
                "server_id": server_id,
                **result,
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "message": f"Prediction failed: {str(e)}"}), 500

@ai_bp.route('/execute_command', methods=['POST'])
def execute_command():
    """
    AI 运维命令安全执行接口
    入参: JSON (command)
    出参: JSON (执行结果)
    核心逻辑: 经白名单与高危拦截后才允许下发系统
    """
    data = request.get_json()
    command = data.get('command', '')
    mapped = to_command(command)
    role_name = getattr(request, 'user', {}).get('role', 'operator')
    evaluated = evaluate_risk(mapped['command'], role_name, force_approved=False)

    write_audit_log({
        'user_id': getattr(request, 'user', {}).get('user_id'),
        'username': getattr(request, 'user', {}).get('username', 'unknown'),
        'role_name': role_name,
        'server_id': data.get('server_id'),
        'session_id': data.get('session_id'),
        'command_raw': command,
        'command_parsed': evaluated['parsed_command'],
        'risk_score': evaluated['risk_score'],
        'risk_level': evaluated['risk_level'],
        'action': 'execute_request',
        'result': 'blocked' if not evaluated['allowed'] else 'allowed',
        'detail': evaluated['reason'] or 'ok'
    })

    is_valid, msg = validate_ai_command(mapped['command'])
    if (not is_valid) or (not evaluated['allowed']):
        return jsonify({
            "code": 403,
            "message": f"AI Command Blocked: {msg if not evaluated['reason'] else evaluated['reason']}",
            "data": None
        }), 403
        
    # 模拟执行
    return jsonify({
        "code": 200,
        "message": "Command Executed",
        "data": {
            "stdout": f"[simulated] {mapped['command']}\nActive connections...\n...",
            "risk": {
                "score": evaluated['risk_score'],
                "level": evaluated['risk_level']
            }
        }
    })
