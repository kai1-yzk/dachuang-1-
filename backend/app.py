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

from routes.metrics import metrics_bp
from routes.auth import auth_bp
from routes.ai_analysis import ai_bp
from routes.data_ingestion import data_bp
from routes.agents import agents_bp
from routes.audit import audit_bp
from routes.servers import servers_bp
from routes.ws_terminal import init_ws_handlers
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

def create_app():
    """创建并配置 Flask 应用"""
    app = Flask(__name__)
    
    # CORS 白名单
    CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "https://yourdomain.com"]}}, supports_credentials=True)
    
    # 初始化限流器
    limiter.init_app(app)
    socketio.init_app(app)
    
    # 随机生成 256-bit (32 bytes) 密钥，或使用环境变量
    app.config['JWT_SECRET_KEY'] = os.environ.get("JWT_SECRET_KEY", secrets.token_hex(32))
    
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
