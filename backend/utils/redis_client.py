import redis
import os
import logging
import threading

from utils.env_loader import load_local_env

load_local_env()

logger = logging.getLogger(__name__)

_client = None
_lock = threading.Lock()


def _build_client():
    """按当前环境变量构造 Redis 客户端。

    配置在调用时读取，避免模块导入阶段就把环境变量固化下来
    （模块导入早于 .env 加载时会拿到错误地址）。
    """
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", 6379))
    db = int(os.environ.get("REDIS_DB", 0))
    password = os.environ.get("REDIS_PASSWORD") or None
    try:
        return redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
    except Exception as e:  # pragma: no cover - 构造失败极少发生
        logger.error("Failed to build Redis client: %s", e)
        return None


def get_redis_client():
    """惰性单例：首次使用时才创建客户端。"""
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = _build_client()
    return _client


def reset_redis_client():
    """清空缓存客户端（配置变更或测试时使用）。"""
    global _client
    with _lock:
        _client = None


def __getattr__(name):
    # 兼容旧代码：`from utils.redis_client import redis_client` 仍然可用，
    # 但每次属性访问都会惰性获取真实客户端。
    if name == "redis_client":
        return get_redis_client()
    raise AttributeError(name)
