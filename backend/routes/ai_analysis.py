"""
AI 分析与预测路由
创建时间: 2026-03-24
功能说明: 接收预处理后的数据并进行推理，以及提供自然语言运维命令校验
"""
from flask import Blueprint, jsonify, request
from utils.security import validate_ai_command
from services.command_risk_service import evaluate_risk, to_command
from services.audit_service import write_audit_log

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/predict', methods=['POST'])
def predict_anomaly():
    """
    模型推理接口
    入参: JSON (服务器特征数据)
    出参: JSON (预测结果、异常类型)
    """
    data = request.get_json()
    if not data or 'features' not in data:
        return jsonify({"code": 400, "message": "Bad Request: Missing features"}), 400
        
    # 尝试加载真实模型进行推理
    import os
    import sys
    import numpy as np
    
    # 将 ai_engine 添加到路径以便导入
    ai_engine_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../ai_engine'))
    if ai_engine_path not in sys.path:
        sys.path.append(ai_engine_path)
        
    try:
        from models.fusion_model import AIOpsFusionModel
        import pickle
        import torch
        
        # 提取特征
        current_features = np.array(data['features'], dtype=np.float32)
        # 假设前端传来 10 个时间步的序列用于趋势预测
        seq_features = data.get('sequence', [current_features] * 10) 
        
        model = AIOpsFusionModel(input_features=len(current_features))
        
        model_dir = os.path.join(ai_engine_path, 'models')
        iso_path = os.path.join(model_dir, 'isolation_forest.pkl')
        lstm_path = os.path.join(model_dir, 'lstm_quantized.pth')
        
        # 加载隔离森林
        if os.path.exists(iso_path):
            with open(iso_path, 'rb') as f:
                model.iso_forest = pickle.load(f)
                
        # 加载 LSTM
        if os.path.exists(lstm_path):
            model.lstm_model.load_state_dict(torch.load(lstm_path))
            model.lstm_model.eval()
            
        result = model.predict(current_features, seq_features)
        
        return jsonify({
            "code": 200,
            "message": "Prediction Success",
            "data": {
                "is_anomaly": result['is_anomaly'],
                "predicted_trend": result['predicted_trend'],
                "suggestion": "检测到服务器异常，建议检查负载" if result['is_anomaly'] else "服务器负载平稳，无需干预"
            }
        })
    except Exception as e:
        # 如果模型加载失败，返回 mock 数据
        return jsonify({
            "code": 200,
            "message": "Mock Prediction (Model load failed)",
            "data": {
                "is_anomaly": False,
                "predicted_trend": 45.2,
                "suggestion": "模型未完全加载，此为Mock结果",
                "error": str(e)
            }
        })

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
