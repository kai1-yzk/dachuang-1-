"""Redis / Celery 配置组装测试（A-01 / A-02 回归）。"""
import os
from unittest.mock import patch

from utils import redis_client as rc
from tasks import _build_redis_url


class TestRedisLazyInit:
    def test_client_reads_env_at_call_time(self, monkeypatch):
        """模块导入后修改环境变量，仍应生效（惰性初始化）。"""
        rc.reset_redis_client()
        monkeypatch.setenv("REDIS_HOST", "10.0.0.9")
        monkeypatch.setenv("REDIS_PORT", "6390")
        monkeypatch.setenv("REDIS_DB", "2")
        client = rc.get_redis_client()
        assert client is not None
        kwargs = client.connection_pool.connection_kwargs
        assert kwargs["host"] == "10.0.0.9"
        assert kwargs["port"] == 6390
        assert kwargs["db"] == 2
        rc.reset_redis_client()

    def test_password_is_applied(self, monkeypatch):
        rc.reset_redis_client()
        monkeypatch.setenv("REDIS_PASSWORD", "s3cret")
        client = rc.get_redis_client()
        assert client.connection_pool.connection_kwargs["password"] == "s3cret"
        rc.reset_redis_client()

    def test_module_level_attr_is_lazy_compatible(self):
        # 兼容旧写法 `from utils.redis_client import redis_client`
        client = rc.redis_client
        assert client is not None


class TestCeleryUrl:
    def test_url_without_password(self, monkeypatch):
        monkeypatch.setenv("REDIS_HOST", "redis")
        monkeypatch.setenv("REDIS_PORT", "6379")
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        assert _build_redis_url(1) == "redis://redis:6379/1"

    def test_url_with_password_and_db(self, monkeypatch):
        monkeypatch.setenv("REDIS_HOST", "redis")
        monkeypatch.setenv("REDIS_PORT", "6380")
        monkeypatch.setenv("REDIS_PASSWORD", "p@ss")
        assert _build_redis_url(3) == "redis://:p@ss@redis:6380/3"
