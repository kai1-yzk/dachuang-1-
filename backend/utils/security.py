"""
安全模块文件
创建时间: 2026-03-24
功能说明: 包含 RBAC 权限控制中间件、请求头安全处理以及 AI 命令白名单校验
"""
from flask import jsonify
import jwt
import secrets

# AI 命令白名单
COMMAND_WHITELIST = [
    "top -b -n 1",
    "free -m",
    "df -h",
    "netstat -an"
]

PUBLIC_PATH_PREFIX = (
    '/api/health',
    '/api/system/dependencies',
    '/api/auth',
    '/api/data/ingest',
    '/api/data/stats',
    '/api/agents/register',
    '/api/agents/heartbeat',
    '/api/agents/metrics',
    '/socket.io',
)


def _is_public_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIX)

def rbac_middleware(req, secret_key):
    """
    RBAC 权限中间件
    入参: req (flask.request), secret_key (str)
    出参: None (放行) 或 JSON Response (拦截)
    核心逻辑: 验证 JWT Token 并检查权限
    """
    # 登录、接入和预检请求放行
    if _is_public_path(req.path) or req.method == 'OPTIONS':
        return None
        
    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"code": 401, "message": "Unauthorized: No Token Provided"}), 401
        
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        payload.setdefault("role", "operator")
        payload.setdefault("tenant_id", 1)
        req.user = payload  # 将用户信息挂载到 request 上
        req.tenant_id = int(payload.get("tenant_id") or 1)
    except jwt.ExpiredSignatureError:
        return jsonify({"code": 401, "message": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"code": 401, "message": "Invalid token"}), 401
        
    return None

def security_headers_middleware(response):
    """
    安全请求头中间件
    入参: response (flask.Response)
    出参: response
    核心逻辑: 添加常见安全响应头防范 XSS, Clickjacking 等
    """
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # 启用 HSTS (强制HTTPS，此处为示例，需视情况在反代层配置)
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

def validate_ai_command(command):
    """
    AI 命令白名单与语法校验
    入参: command (str)
    出参: is_valid (bool), message (str)
    核心逻辑: 防止AI生成越权指令
    """
    # 基础的高危命令过滤
    dangerous_keywords = ["sudo", "rm ", "chmod", "chown", "reboot", "shutdown", ">", "|"]
    for keyword in dangerous_keywords:
        if keyword in command:
            return False, f"禁止执行高危敏感命令: 包含关键词 '{keyword}'"
    
    # 白名单匹配
    if command not in COMMAND_WHITELIST:
        return False, "命令不在白名单内，禁止执行"
        
    return True, "校验通过"


def generate_short_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def get_request_tenant_id(req) -> int:
    if hasattr(req, "tenant_id"):
        return int(getattr(req, "tenant_id") or 1)
    if hasattr(req, "user"):
        return int(getattr(req, "user", {}).get("tenant_id") or 1)
    return 1


def ensure_role(req, allowed_roles):
    role = getattr(req, "user", {}).get("role", "operator") if hasattr(req, "user") else "operator"
    if role not in allowed_roles:
        return jsonify({"code": 403, "message": "Forbidden: insufficient role", "data": None}), 403
    return None
