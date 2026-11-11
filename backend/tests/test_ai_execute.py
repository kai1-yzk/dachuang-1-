"""/api/ai/execute_command 执行链测试：拦截 / 缺参 / 真实 SSH 下发。"""
import datetime
from unittest.mock import patch

import jwt
import pytest

from app import create_app

SECRET = "test-secret-key-for-unit-tests-only"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    app = create_app()
    app.config.update({"TESTING": True, "JWT_SECRET_KEY": SECRET})
    return app.test_client()


def _auth():
    token = jwt.encode(
        {
            "user_id": 1,
            "username": "tester",
            "role": "superadmin",
            "tenant_id": 1,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=15),
        },
        SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@patch("routes.ai_analysis.write_audit_log")
def test_dangerous_command_is_blocked(mock_audit, client):
    resp = client.post(
        "/api/ai/execute_command",
        json={"command": "rm -rf /", "server_id": 1},
        headers=_auth(),
    )
    assert resp.status_code == 403
    assert "Blocked" in resp.get_json()["message"]
    # 拦截行为必须落审计
    mock_audit.assert_called()


@patch("routes.ai_analysis.write_audit_log")
def test_missing_server_id_returns_400(mock_audit, client):
    resp = client.post(
        "/api/ai/execute_command",
        json={"command": "df -h"},
        headers=_auth(),
    )
    assert resp.status_code == 400
    assert "server_id" in resp.get_json()["message"]


@patch("routes.ai_analysis.write_audit_log")
def test_empty_body_returns_4xx_not_500(mock_audit, client):
    resp = client.post(
        "/api/ai/execute_command",
        data="",
        content_type="application/json",
        headers=_auth(),
    )
    assert resp.status_code < 500


@patch("routes.ai_analysis.write_audit_log")
@patch("routes.ai_analysis.run_command_stream")
def test_safe_command_runs_over_ssh(mock_run, mock_audit, client):
    """安全低频命令应真实下发到目标服务器，并返回真实 stdout。"""
    mock_run.return_value = {
        "ok": True,
        "exit_status": 0,
        "chunks": [
            {"stream": "stdout", "text": "Filesystem      Size  Used Avail Use%\n"},
        ],
    }

    resp = client.post(
        "/api/ai/execute_command",
        json={"command": "df -h", "server_id": 7},
        headers=_auth(),
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["exit_status"] == 0
    assert "Filesystem" in body["data"]["stdout"]
    assert body["data"]["server_id"] == 7
    # 禁止返回模拟数据
    assert "[simulated]" not in body["data"]["stdout"]
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0] == 7


@patch("routes.ai_analysis.write_audit_log")
@patch("routes.ai_analysis.run_command_stream")
def test_ssh_failure_returns_502(mock_run, mock_audit, client):
    mock_run.side_effect = RuntimeError("ssh auth failed")

    resp = client.post(
        "/api/ai/execute_command",
        json={"command": "df -h", "server_id": 7},
        headers=_auth(),
    )

    assert resp.status_code == 502
    assert "ssh auth failed" in resp.get_json()["message"]
