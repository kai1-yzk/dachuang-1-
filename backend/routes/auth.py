"""
认证模块路由
创建时间: 2026-03-24
功能说明: 处理用户登录、注册及权限验证 (双令牌机制)
"""
from flask import Blueprint, request, jsonify, current_app
import logging
import jwt
import datetime
import bcrypt
import re
from utils.db import execute_query, execute_update, is_db_available, get_last_db_error
from utils.security import generate_short_code

auth_bp = Blueprint('auth', __name__)

logger = logging.getLogger(__name__)

_USER_HAS_ROLE_NAME = None
_USER_HAS_TENANT_ID = None


def _user_has_role_name_column():
    """兼容旧库结构：按需检测 user 表是否存在 role_name 列。"""
    global _USER_HAS_ROLE_NAME
    if _USER_HAS_ROLE_NAME is None:
        rows = execute_query("SHOW COLUMNS FROM user LIKE %s", ('role_name',))
        _USER_HAS_ROLE_NAME = bool(rows)
    return _USER_HAS_ROLE_NAME


def _user_has_tenant_id_column():
    global _USER_HAS_TENANT_ID
    if _USER_HAS_TENANT_ID is None:
        rows = execute_query("SHOW COLUMNS FROM user LIKE %s", ('tenant_id',))
        _USER_HAS_TENANT_ID = bool(rows)
    return _USER_HAS_TENANT_ID

def validate_password(password):
    """密码复杂度校验：至少8位，包含大小写字母、数字和特殊字符"""
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        if not is_db_available():
            logger.error("注册失败：数据库不可用，last_error=%s", get_last_db_error())
            return jsonify({"code": 503, "message": "Database unavailable"}), 503

        data = request.get_json()
        if not data:
            logger.warning("Register called with empty JSON payload")
            return jsonify({"code": 400, "message": "Invalid or missing JSON body"}), 400

        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        tenant_id = int(data.get('tenant_id') or 1)

        if not all([username, email, password]):
            return jsonify({"code": 400, "message": "Missing required fields"}), 400

        if not validate_password(password):
            return jsonify({"code": 400, "message": "Password does not meet complexity requirements"}), 400

        # 检查是否已存在
        try:
            existing = execute_query("SELECT id FROM user WHERE username=%s OR email=%s", (username, email))
        except Exception as db_e:
            logger.exception("数据库查询失败（检查用户是否存在）: %s", db_e)
            return jsonify({"code": 500, "message": "Database error"}), 500

        if existing:
            return jsonify({"code": 409, "message": "Username or email already exists"}), 409

        # 将密码字符串编码为字节，然后再哈希
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

        # 插入数据库
        if _user_has_role_name_column() and _user_has_tenant_id_column():
            sql = "INSERT INTO user (username, email, password_hash, role_name, tenant_id) VALUES (%s, %s, %s, %s, %s)"
            params = (username, email, password_hash, 'operator', tenant_id)
        elif _user_has_role_name_column():
            sql = "INSERT INTO user (username, email, password_hash, role_name) VALUES (%s, %s, %s, %s)"
            params = (username, email, password_hash, 'operator')
        elif _user_has_tenant_id_column():
            sql = "INSERT INTO user (username, email, password_hash, tenant_id) VALUES (%s, %s, %s, %s)"
            params = (username, email, password_hash, tenant_id)
        else:
            sql = "INSERT INTO user (username, email, password_hash) VALUES (%s, %s, %s)"
            params = (username, email, password_hash)
        try:
            affected = execute_update(sql, params)
        except Exception as db_e:
            logger.exception("数据库写入失败（注册用户）: %s", db_e)
            return jsonify({"code": 500, "message": "Database error"}), 500

        if affected > 0:
            return jsonify({"code": 200, "message": "Registration successful"}), 200
        else:
            logger.error("注册未影响任何行，affected=0 (username=%s, email=%s)", username, email)
            if not is_db_available():
                logger.error("注册写入失败后检测到数据库不可用，last_error=%s", get_last_db_error())
                return jsonify({"code": 503, "message": "Database unavailable"}), 503
            return jsonify({"code": 500, "message": "Failed to register user"}), 500
    except Exception as e:
        logger.exception("Unhandled exception in register: %s", e)
        # 如果不是生产环境，可以返回更详细信息；当前仅返回泛化信息
        return jsonify({"code": 500, "message": "Internal Server Error"}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username')
    password = data.get('password')
    
    if not all([username, password]):
        return jsonify({"code": 400, "message": "Missing username or password"}), 400
        
    if _user_has_role_name_column() and _user_has_tenant_id_column():
        users = execute_query("SELECT id, username, password_hash, role_name, tenant_id FROM user WHERE username=%s", (username,))
    elif _user_has_role_name_column():
        users = execute_query("SELECT id, username, password_hash, role_name FROM user WHERE username=%s", (username,))
    elif _user_has_tenant_id_column():
        users = execute_query("SELECT id, username, password_hash, tenant_id FROM user WHERE username=%s", (username,))
    else:
        users = execute_query("SELECT id, username, password_hash FROM user WHERE username=%s", (username,))
    if not users:
        return jsonify({"code": 401, "message": "Invalid credentials"}), 401
        
    user = users[0]
    try:
        if not bcrypt.checkpw(password.encode('utf-8'), str(user['password_hash']).encode('utf-8')):
            return jsonify({"code": 401, "message": "Invalid credentials (password mismatch)"}), 401
    except Exception as e:
        logger.exception("Bcrypt check failed: %s", e)
        return jsonify({"code": 401, "message": "Invalid credentials (hash error)"}), 401
        
    # 生成双令牌
    secret_key = current_app.config['JWT_SECRET_KEY']
    
    # Access Token: 15分钟
    access_payload = {
        'user_id': user['id'],
        'username': user['username'],
        'role': user.get('role_name') or 'operator',
        'tenant_id': int(user.get('tenant_id') or 1),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    }
    access_token = jwt.encode(access_payload, secret_key, algorithm='HS256')
    
    # Refresh Token: 7天
    refresh_payload = {
        'user_id': user['id'],
        'type': 'refresh',
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    refresh_token = jwt.encode(refresh_payload, secret_key, algorithm='HS256')
    
    # 更新到数据库
    execute_update("UPDATE user SET refresh_token=%s WHERE id=%s", (refresh_token, user['id']))
    
    return jsonify({
        "code": 200,
        "message": "Login success",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_info": {
                "id": user['id'],
                "username": user['username'],
                "role": user.get('role_name') or 'operator',
                "tenant_id": int(user.get('tenant_id') or 1),
            }
        }
    })

@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    data = request.get_json(silent=True) or {}
    refresh_token = data.get('refresh_token')
    
    if not refresh_token:
        return jsonify({"code": 400, "message": "Refresh token missing"}), 400
        
    secret_key = current_app.config['JWT_SECRET_KEY']
    try:
        payload = jwt.decode(refresh_token, secret_key, algorithms=["HS256"])
        if payload.get('type') != 'refresh':
            raise jwt.InvalidTokenError()
            
        user_id = payload['user_id']
        
        # 验证数据库中是否匹配 (防止token被主动吊销)
        if _user_has_role_name_column() and _user_has_tenant_id_column():
            users = execute_query("SELECT refresh_token, username, role_name, tenant_id FROM user WHERE id=%s", (user_id,))
        elif _user_has_role_name_column():
            users = execute_query("SELECT refresh_token, username, role_name FROM user WHERE id=%s", (user_id,))
        elif _user_has_tenant_id_column():
            users = execute_query("SELECT refresh_token, username, tenant_id FROM user WHERE id=%s", (user_id,))
        else:
            users = execute_query("SELECT refresh_token, username FROM user WHERE id=%s", (user_id,))
        if not users or users[0]['refresh_token'] != refresh_token:
            return jsonify({"code": 401, "message": "Invalid or revoked refresh token"}), 401
            
        # 签发新的 Access Token
        access_payload = {
            'user_id': user_id,
            'username': users[0]['username'],
            'role': users[0].get('role_name') or 'operator',
            'tenant_id': int(users[0].get('tenant_id') or 1),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
        }
        access_token = jwt.encode(access_payload, secret_key, algorithm='HS256')
        
        return jsonify({
            "code": 200,
            "message": "Token refreshed",
            "data": {
                "access_token": access_token
            }
        })
    except jwt.ExpiredSignatureError:
        return jsonify({"code": 401, "message": "Refresh token expired. Please login again."}), 401
    except jwt.InvalidTokenError:
        return jsonify({"code": 401, "message": "Invalid refresh token"}), 401

@auth_bp.route('/logout', methods=['POST'])
def logout():
    # 通常前端通过Authorization header发送access_token
    # 我们也可以要求传递refresh_token以确保清除
    # 此处假设中间件已将 user 解析到 request.user
    if hasattr(request, 'user') and 'user_id' in request.user:
        user_id = request.user['user_id']
        execute_update("UPDATE user SET refresh_token=NULL WHERE id=%s", (user_id,))
        
    return jsonify({"code": 200, "message": "Logout successful"}), 200


@auth_bp.route('/mfa/request-code', methods=['POST'])
def request_mfa_code():
    if not hasattr(request, 'user') or 'user_id' not in request.user:
        return jsonify({"code": 401, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    session_id = data.get('session_id')
    command_text = data.get('command_text', '')
    if not session_id:
        return jsonify({"code": 400, "message": "session_id is required"}), 400

    code = generate_short_code()
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
    execute_update(
        """
        INSERT INTO mfa_challenges
        (user_id, session_id, command_text, short_code, expires_at, used, created_at)
        VALUES (%s, %s, %s, %s, %s, 0, NOW())
        """,
        (request.user['user_id'], session_id, command_text, code, expires_at),
    )

    # 生产环境应发送到邮件/短信服务，演示环境返回短码用于联调
    return jsonify({
        "code": 200,
        "message": "短码已生成",
        "data": {
            "session_id": session_id,
            "expires_in_sec": 300,
            "demo_code": code,
        }
    })


@auth_bp.route('/mfa/verify-code', methods=['POST'])
def verify_mfa_code():
    if not hasattr(request, 'user') or 'user_id' not in request.user:
        return jsonify({"code": 401, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    session_id = data.get('session_id')
    code = (data.get('code') or '').strip()
    if not session_id or not code:
        return jsonify({"code": 400, "message": "session_id and code are required"}), 400

    rows = execute_query(
        """
        SELECT id FROM mfa_challenges
        WHERE user_id=%s AND session_id=%s AND short_code=%s AND used=0 AND expires_at > NOW()
        ORDER BY id DESC LIMIT 1
        """,
        (request.user['user_id'], session_id, code),
    )
    if not rows:
        return jsonify({"code": 400, "message": "短码无效或已过期"}), 400

    execute_update("UPDATE mfa_challenges SET used=1 WHERE id=%s", (rows[0]['id'],))
    return jsonify({"code": 200, "message": "短码验证通过", "data": {"verified": True}})
