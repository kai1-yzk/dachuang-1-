"""
AI 分析与预测路由
创建时间: 2026-03-24
功能说明: 接收预处理后的数据并进行推理，以及提供自然语言运维命令校验
"""
import logging

from flask import Blueprint, jsonify, request
from utils.security import validate_ai_command
from services.command_risk_service import evaluate_risk, to_command
from services.ai_explainer_service import build_explain
from services.audit_service import write_audit_log
from utils.db import execute_query
from utils.security import get_request_tenant_id

ai_bp = Blueprint('ai', __name__)
logger = logging.getLogger(__name__)

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

    artifact_candidates = [
        ai_engine_path / 'models' / 'server_anomaly_artifacts.pkl',
        ai_engine_path / 'models' / 'server_anomaly_artifacts.json',
    ]
    artifact = None
    for candidate in artifact_candidates:
        if candidate.exists():
            artifact = candidate
            break
    if artifact is None:
        raise FileNotFoundError("model artifact not found: server_anomaly_artifacts.(pkl|json)")

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


def _rule_based_prediction(packet: dict):
    series = (packet or {}).get('series') or {}
    cpu_values = series.get('cpu_usage') or []
    memory_values = series.get('memory_usage') or []
    disk_values = series.get('disk_usage') or []
    network_values = series.get('network_total') or []

    cpu = float(cpu_values[-1] if cpu_values else 0.0)
    memory = float(memory_values[-1] if memory_values else 0.0)
    disk = float(disk_values[-1] if disk_values else 0.0)
    network = float(network_values[-1] if network_values else 0.0)

    score = max(cpu, memory, disk, min(network, 100.0)) / 100.0
    is_anomaly = bool(cpu >= 85 or memory >= 85 or disk >= 90)
    if cpu >= 90:
        anomaly_type = 'cpu'
    elif memory >= 90:
        anomaly_type = 'memory'
    elif disk >= 92:
        anomaly_type = 'disk'
    else:
        anomaly_type = 'normal'

    return {
        'ok': True,
        'is_anomaly': is_anomaly,
        'anomaly_score': round(float(score), 4),
        'anomaly_type': anomaly_type,
        'source': 'fallback_rule',
    }


def _normalize_prediction(result: dict):
    if not isinstance(result, dict):
        return {'ok': False, 'message': 'predict result is invalid'}
    normalized = dict(result)
    normalized['ok'] = bool(normalized.get('ok', True))
    normalized['is_anomaly'] = bool(normalized.get('is_anomaly', False))
    normalized['anomaly_score'] = float(normalized.get('anomaly_score') or 0.0)
    return normalized


def _predict_multivariate_with_fallback(packet: dict):
    try:
        predictor = _load_server_predictor()
        result = predictor.predict_multivariate(packet['series'], packet['timestamps'])
        normalized = _normalize_prediction(result)
        if not normalized.get('ok'):
            fallback = _rule_based_prediction(packet)
            fallback['source'] = 'fallback_rule_after_model_not_ok'
            fallback['model_message'] = normalized.get('message') or 'predictor returned not ok'
            return fallback
        return normalized
    except (FileNotFoundError, ImportError, OSError) as e:
        logger.warning('predictor unavailable, fallback to rule-based predictor: %s', e)
        return _rule_based_prediction(packet)
    except Exception as e:
        logger.exception('predictor runtime error: %s', e)
        fallback = _rule_based_prediction(packet)
        fallback['source'] = 'fallback_rule_after_runtime_error'
        fallback['model_message'] = 'predictor runtime error'
        return fallback


def _predict_series_with_fallback(values):
    try:
        predictor = _load_server_predictor()
        result = predictor.predict_series(values)
        normalized = _normalize_prediction(result)
        if not normalized.get('ok'):
            try:
                numbers = [float(v) for v in values]
            except Exception:
                return {'ok': False, 'message': normalized.get('message') or 'invalid values'}
            score = max(numbers) / 100.0 if numbers else 0.0
            return {
                'ok': True,
                'is_anomaly': bool(score >= 0.85),
                'anomaly_score': round(float(score), 4),
                'anomaly_type': 'series',
                'source': 'fallback_rule_after_model_not_ok',
                'model_message': normalized.get('message') or 'predictor returned not ok',
            }
        return normalized
    except (FileNotFoundError, ImportError, OSError) as e:
        logger.warning('predictor unavailable for series, fallback to rule-based predictor: %s', e)
        try:
            numbers = [float(v) for v in values]
        except Exception:
            return {'ok': False, 'message': 'invalid values'}
        score = max(numbers) / 100.0 if numbers else 0.0
        return {
            'ok': True,
            'is_anomaly': bool(score >= 0.85),
            'anomaly_score': round(float(score), 4),
            'anomaly_type': 'series',
            'source': 'fallback_rule',
        }
    except Exception as e:
        logger.exception('predictor runtime error for series: %s', e)
        try:
            numbers = [float(v) for v in values]
        except Exception:
            return {'ok': False, 'message': 'invalid values'}
        score = max(numbers) / 100.0 if numbers else 0.0
        return {
            'ok': True,
            'is_anomaly': bool(score >= 0.85),
            'anomaly_score': round(float(score), 4),
            'anomaly_type': 'series',
            'source': 'fallback_rule_after_runtime_error',
            'model_message': 'predictor runtime error',
        }


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


def _build_alert_detail(packet: dict, prediction: dict):
    series = packet.get("series", {}) if packet else {}
    cpu_values = series.get("cpu_usage", [])
    memory_values = series.get("memory_usage", [])
    disk_values = series.get("disk_usage", [])
    network_values = series.get("network_total", [])

    current_cpu = float(cpu_values[-1] if cpu_values else 0.0)
    current_mem = float(memory_values[-1] if memory_values else 0.0)
    current_disk = float(disk_values[-1] if disk_values else 0.0)
    current_net = float(network_values[-1] if network_values else 0.0)

    fault_type = "系统负载异常"
    cause = "多个资源指标出现异常波动"
    emergency = "先检查系统活跃进程并释放高负载任务"
    prevention = "配置容量冗余并设置分级阈值告警"

    top_metric = max([
        ("CPU过载", current_cpu),
        ("内存不足", current_mem),
        ("磁盘压力过高", current_disk),
    ], key=lambda x: x[1])[0]
    if top_metric == "CPU过载":
        cause = f"CPU负载连续高位，当前值 {current_cpu:.2f}%"
        emergency = "关闭非必要进程，并限制高CPU任务"
        prevention = "升级CPU配置或优化任务调度策略"
    elif top_metric == "内存不足":
        cause = f"内存使用率持续偏高，当前值 {current_mem:.2f}%"
        emergency = "释放缓存并排查内存泄漏进程"
        prevention = "增加内存容量并设置应用内存配额"
    elif top_metric == "磁盘压力过高":
        cause = f"磁盘使用率接近阈值，当前值 {current_disk:.2f}%"
        emergency = "清理临时与历史日志文件，释放可用空间"
        prevention = "扩容磁盘并配置日志轮转策略"

    if prediction.get("is_anomaly"):
        score = float(prediction.get("anomaly_score") or 0)
        if score >= 0.75 or current_cpu >= 90 or current_mem >= 90 or current_disk >= 90:
            risk_level = "高"
        elif score >= 0.45 or current_cpu >= 80 or current_mem >= 80 or current_disk >= 80:
            risk_level = "中"
        else:
            risk_level = "低"
    else:
        risk_level = "低"

    return {
        "fault_type": top_metric if prediction.get("is_anomaly") else "未检测到故障",
        "risk_level": risk_level,
        "lead_time_minutes": 10,
        "cause": cause,
        "emergency_solution": emergency,
        "prevention_advice": prevention,
        "metrics_snapshot": {
            "cpu": round(current_cpu, 2),
            "memory": round(current_mem, 2),
            "disk": round(current_disk, 2),
            "network": round(current_net, 2),
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
        if server_id:
            packet = _load_server_metric_series(int(server_id), get_request_tenant_id(request), limit=120)
            if not packet:
                return jsonify({"code": 404, "message": "No server metrics found"}), 404
            result = _predict_multivariate_with_fallback(packet)
            if not result.get('ok'):
                return jsonify({"code": 422, "message": result.get('message') or 'Prediction data not sufficient'}), 422
        else:
            values = data.get('values') or data.get('features')
            if not values:
                return jsonify({"code": 400, "message": "Missing values or server_id"}), 400
            result = _predict_series_with_fallback(values)
            if not result.get('ok'):
                return jsonify({"code": 422, "message": result.get('message') or 'Prediction data not sufficient'}), 422

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
        packet = _load_server_metric_series(server_id, get_request_tenant_id(request), limit=120)
        if not packet:
            return jsonify({"code": 404, "message": "No server metrics found"}), 404

        result = _predict_multivariate_with_fallback(packet)
        if not result.get('ok'):
            return jsonify({"code": 422, "message": result.get('message') or 'Prediction data not sufficient'}), 422
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


@ai_bp.route('/predict-alert/<int:server_id>', methods=['GET'])
def predict_alert(server_id: int):
    try:
        packet = _load_server_metric_series(server_id, get_request_tenant_id(request), limit=120)
        if not packet:
            return jsonify({"code": 404, "message": "No server metrics found"}), 404

        result = _predict_multivariate_with_fallback(packet)
        if not result.get('ok'):
            return jsonify({"code": 422, "message": result.get('message') or 'Prediction data not sufficient'}), 422

        alert = _build_alert_detail(packet, result)
        explain = build_explain(alert, result, server_id)

        return jsonify({
            "code": 200,
            "message": "Prediction Success",
            "data": {
                "server_id": server_id,
                **result,
                "alert": alert,
                "explain": explain,
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
    data = request.get_json(silent=True) or {}
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
