"""
系统入口文件：轻量化 AI 服务器运维防护系统 (Backend)
创建时间: 2026-03-24
功能说明: Flask 应用主入口，注册蓝图，配置中间件及全局错误处理
"""
from flask import Flask, jsonify, request, redirect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO
import logging
import secrets
import os
from typing import Dict, Any

from utils.env_loader import load_local_env
from utils.db import is_db_available, get_last_db_error
from utils.redis_client import redis_client
from tasks import celery_app

load_local_env()

from routes.metrics import metrics_bp
from routes.auth import auth_bp
from routes.ai_analysis import ai_bp
from routes.data_ingestion import data_bp
from routes.agents import agents_bp
from routes.audit import audit_bp
from routes.servers import servers_bp
from routes.assistant import assistant_bp
from routes.tenants import tenants_bp
from routes.services import services_bp
from routes.logs import logs_bp
from routes.backup import backup_bp
from routes.files import files_bp
from routes.batch import batch_bp
from routes.ws_terminal import init_ws_handlers
from services.server_metrics_service import start_auto_collector
from utils.security import rbac_middleware, security_headers_middleware

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 初始化 Limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

socketio = SocketIO(cors_allowed_origins="*", async_mode="gevent")

_WEAK_SECRET_VALUES = {
    "replace_with_a_long_random_secret",
    "replace_with_your_private_secret",
    "super_secret_aiops_key",
    "default",
    "changeme",
    "123456",
    "admin",
}


def _is_production() -> bool:
    return str(os.environ.get("ENV", "development")).strip().lower() == "production"


def _build_dependency_status() -> Dict[str, Any]:
    status: Dict[str, Any] = {
        "database": {
            "ok": False,
            "error_code": "DB_UNAVAILABLE",
            "message": "Database not checked",
            "hint": "检查 DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME 配置与数据库可达性",
        },
        "redis": {
            "ok": False,
            "error_code": "REDIS_UNAVAILABLE",
            "message": "Redis not checked",
            "hint": "检查 REDIS_HOST/REDIS_PORT/REDIS_PASSWORD 配置与 Redis 服务状态",
        },
        "celery_broker": {
            "ok": False,
            "error_code": "CELERY_BROKER_UNAVAILABLE",
            "message": "Celery broker not checked",
            "hint": "检查 Celery broker 配置与 Redis 连通性",
        },
    }

    db_ok = is_db_available()
    status["database"]["ok"] = db_ok
    if db_ok:
        status["database"]["error_code"] = None
        status["database"]["message"] = "Database connection healthy"
        status["database"]["hint"] = None
    else:
        status["database"]["message"] = get_last_db_error() or "Database connection failed"

    try:
        if redis_client is None:
            raise RuntimeError("Redis client not initialized")
        redis_client.ping()
        status["redis"]["ok"] = True
        status["redis"]["error_code"] = None
        status["redis"]["message"] = "Redis connection healthy"
        status["redis"]["hint"] = None
    except Exception as exc:
        status["redis"]["message"] = str(exc)

    broker_url = str(celery_app.conf.get("broker_url") or "")
    if broker_url.startswith("redis://"):
        if status["redis"]["ok"]:
            status["celery_broker"]["ok"] = True
            status["celery_broker"]["error_code"] = None
            status["celery_broker"]["message"] = "Celery broker(redis) inferred healthy"
            status["celery_broker"]["hint"] = None
        else:
            status["celery_broker"]["message"] = "Celery broker(redis) unavailable because Redis is unavailable"
    else:
        status["celery_broker"]["message"] = "Celery broker quick-check only supports redis:// broker"

    return status


def _validate_bootstrap_config() -> None:
    missing = []
    for key in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"):
        value = str(os.environ.get(key, "")).strip()
        if not value:
            missing.append(key)

    if missing:
        logger.warning(
            "Startup preflight: missing required DB env vars: %s. "
            "请在 backend/.env 配置后重启服务。",
            ",".join(missing),
        )

    jwt_secret = str(os.environ.get("JWT_SECRET_KEY", "")).strip()
    aiops_secret = str(os.environ.get("AIOPS_SECRET_KEY", "")).strip()

    if _is_production():
        if not jwt_secret:
            raise RuntimeError(
                "SECURITY_CONFIG_ERROR: missing JWT_SECRET_KEY in production. "
                "请设置强随机密钥后再启动。"
            )
        if not aiops_secret:
            raise RuntimeError(
                "SECURITY_CONFIG_ERROR: missing AIOPS_SECRET_KEY in production. "
                "请设置强随机密钥后再启动。"
            )
        if jwt_secret in _WEAK_SECRET_VALUES or aiops_secret in _WEAK_SECRET_VALUES:
            raise RuntimeError(
                "SECURITY_CONFIG_ERROR: weak default secret detected in production. "
                "请替换为强随机密钥后再启动。"
            )
    else:
        if not jwt_secret:
            logger.warning(
                "JWT_SECRET_KEY 未设置，开发模式将使用临时随机密钥。"
                "重启后旧 token 会失效，建议在 backend/.env 固定配置。"
            )
        if not aiops_secret or aiops_secret in _WEAK_SECRET_VALUES:
            logger.warning(
                "AIOPS_SECRET_KEY 未设置或为弱值。开发环境可运行，但生产环境必须设置强随机密钥。"
            )

def create_app():
    """创建并配置 Flask 应用"""
    app = Flask(__name__)

    _validate_bootstrap_config()
    
    # CORS 白名单
    CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "https://yourdomain.com"]}}, supports_credentials=True)
    
    # 初始化限流器
    limiter.init_app(app)
    socketio.init_app(app)
    
    # 随机生成 256-bit (32 bytes) 密钥，或使用环境变量
    app.config['JWT_SECRET_KEY'] = os.environ.get("JWT_SECRET_KEY", secrets.token_hex(32))

    @app.get('/api/health')
    def health_check():
        dependency_status = _build_dependency_status()
        all_ok = all(dep.get("ok") for dep in dependency_status.values())
        response = {
            "code": 200 if all_ok else 503,
            "message": "ok" if all_ok else "degraded",
            "data": {
                "status": "healthy" if all_ok else "degraded",
                "dependencies": dependency_status,
            },
        }
        return jsonify(response), (200 if all_ok else 503)

    @app.get('/api/system/dependencies')
    def dependencies_status():
        dependency_status = _build_dependency_status()
        all_ok = all(dep.get("ok") for dep in dependency_status.values())
        return jsonify({
            "code": 200,
            "message": "success",
            "data": {
                "overall_ok": all_ok,
                "dependencies": dependency_status,
            },
        }), 200
    
    # 注册中间件
    @app.before_request
    def before_request():
        # HTTPS 强制跳转 (在生产环境且有HTTP头的代理下生效)
        if request.headers.get('X-Forwarded-Proto', 'http') == 'http' and not app.debug and os.environ.get("ENV") == "production":
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)
            
        # 添加安全相关的拦截与验证
        return rbac_middleware(request, app.config['JWT_SECRET_KEY'])

    @app.after_request
    def after_request(response):
        return security_headers_middleware(response)
        
    # 注册蓝图
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(metrics_bp, url_prefix='/api/metrics')
    app.register_blueprint(ai_bp, url_prefix='/api/ai')
    app.register_blueprint(data_bp, url_prefix='/api/data')
    app.register_blueprint(agents_bp, url_prefix='/api/agents')
    app.register_blueprint(audit_bp, url_prefix='/api/audit')
    app.register_blueprint(servers_bp, url_prefix='/api/servers')
    app.register_blueprint(assistant_bp, url_prefix='/api/assistant')
    app.register_blueprint(tenants_bp, url_prefix='/api/tenants')
    app.register_blueprint(services_bp, url_prefix='/api/services')
    app.register_blueprint(logs_bp, url_prefix='/api/logs')
    app.register_blueprint(backup_bp, url_prefix='/api/backup')
    app.register_blueprint(files_bp, url_prefix='/api/files')
    app.register_blueprint(batch_bp, url_prefix='/api/batch')
    start_auto_collector()
    init_ws_handlers(socketio)
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        """全局异常处理"""
        logger.error(f"Server Error: {str(e)}")
        return jsonify({"code": 500, "message": "Internal Server Error", "data": None}), 500
        
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({"code": 429, "message": f"Rate limit exceeded: {e.description}"}), 429

    return app

if __name__ == '__main__':
    app = create_app()
    socketio.run(app, host='0.0.0.0', port=5001, debug=False)
