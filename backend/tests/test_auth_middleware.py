"""JWT 鉴权中间件的核心行为测试。"""
import datetime

import jwt
import pytest

from app import create_app

SECRET = "test-secret-key-for-unit-tests-only"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": SECRET})
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _token(secret=SECRET, exp_minutes=15, **claims):
    payload = {
        "user_id": 1,
        "username": "tester",
        "role": "operator",
        "tenant_id": 1,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=exp_minutes),
    }
    payload.update(claims)
    return jwt.encode(payload, secret, algorithm="HS256")


class TestRBACMiddleware:
    def test_public_path_needs_no_token(self, client):
        # /api/data/stats 属公开路径，无 Token 也必须是 200
        resp = client.get("/api/data/stats")
        assert resp.status_code == 200

    def test_protected_path_without_token_returns_401(self, client):
        resp = client.get("/api/servers/")
        assert resp.status_code == 401
        assert "Unauthorized" in resp.get_json()["message"]

    def test_expired_token_returns_401(self, client):
        token = _token(exp_minutes=-5)
        resp = client.get("/api/servers/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
        assert resp.get_json()["message"] == "Token expired"

    def test_token_signed_with_wrong_secret_returns_401(self, client):
        token = _token(secret="some-other-secret")
        resp = client.get("/api/servers/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
        assert resp.get_json()["message"] == "Invalid token"

    def test_malformed_header_returns_401(self, client):
        resp = client.get("/api/servers/", headers={"Authorization": "Token abc"})
        assert resp.status_code == 401

    def test_valid_token_passes_middleware(self, client):
        """有效 Token 应通过中间件，不再返回 401（后续业务错误不计）。"""
        resp = client.get("/api/servers/", headers={"Authorization": f"Bearer {_token()}"})
        assert resp.status_code != 401


class TestSecurityHeaders:
    def test_security_headers_present(self, client):
        resp = client.get("/api/data/stats")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") in ("DENY", "SAMEORIGIN")
