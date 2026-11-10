"""/api/assistant/ops-plan 与 ops-execute 的风险拦截回归测试。

背景：修复前 ops-plan 对 evaluate_risk 判定 allowed=False 的命令仍会签发
execution_token，用户确认二次弹窗后高危命令会被真实下发执行。
"""
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


def _auth(role="superadmin", user_id=1):
    token = jwt.encode(
        {
            "user_id": user_id,
            "username": "tester",
            "role": role,
            "tenant_id": 1,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=15),
        },
        SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _plan_command(command, role="superadmin"):
    """直接调用底层函数构造 token，绕过 AI 外部调用。"""
    from services.command_risk_service import evaluate_risk, to_command

    mapped = to_command(command)
    return evaluate_risk(mapped["command"], role, force_approved=False)


class TestOpsPlanRiskGate:
    @patch("routes.assistant.generate_ops_plan")
    def test_dangerous_command_rejected_without_token(self, mock_plan, client):
        """高危命令必须在 ops-plan 阶段就被拒，且不签发 execution_token。"""
        mock_plan.return_value = {"command": "rm -rf /tmp/data", "ai_source": "fallback"}

        resp = client.post(
            "/api/assistant/ops-plan",
            json={"command": "rm -rf /tmp/data", "server_id": 1},
            headers=_auth("operator"),
        )

        assert resp.status_code == 403
        body = resp.get_json()
        assert body["code"] == 403
        assert "blocked" in body["message"].lower()
        # 关键断言：不得返回可用令牌
        assert "execution_token" not in (body.get("data") or {})

    @patch("routes.assistant.generate_ops_plan")
    def test_safe_command_issues_token(self, mock_plan, client):
        mock_plan.return_value = {"command": "df -h", "ai_source": "fallback"}

        resp = client.post(
            "/api/assistant/ops-plan",
            json={"command": "df -h", "server_id": 1},
            headers=_auth("operator"),
        )

        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["execution_token"]
        assert data["risk"]["level"] == "LOW"

    @patch("routes.assistant.generate_ops_plan")
    def test_missing_server_id_rejected(self, mock_plan, client):
        mock_plan.return_value = {"command": "df -h"}
        resp = client.post(
            "/api/assistant/ops-plan",
            json={"command": "df -h"},
            headers=_auth("operator"),
        )
        assert resp.status_code == 400


class TestOpsExecuteRiskGate:
    @patch("routes.assistant.run_command_stream")
    def test_does_not_execute_when_token_missing(self, mock_run, client):
        resp = client.post(
            "/api/assistant/ops-execute",
            json={"consent": True},
            headers=_auth(),
        )
        assert resp.status_code == 400
        mock_run.assert_not_called()

    @patch("routes.assistant.run_command_stream")
    def test_requires_consent(self, mock_run, client):
        from routes.assistant import _PENDING_OPS

        token = "test-token-no-consent"
        _PENDING_OPS[token] = {
            "user_id": 1,
            "role": "superadmin",
            "server_id": 1,
            "command": "df -h",
            "risk_level": "LOW",
            "expires_at": datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
        }
        resp = client.post(
            "/api/assistant/ops-execute",
            json={"execution_token": token, "consent": False},
            headers=_auth(),
        )
        assert resp.status_code == 400
        assert "consent" in resp.get_json()["message"].lower()
        mock_run.assert_not_called()
        _PENDING_OPS.pop(token, None)

    @patch("routes.assistant.run_command_stream")
    def test_token_owned_by_other_user_rejected(self, mock_run, client):
        from routes.assistant import _PENDING_OPS

        token = "test-token-other-user"
        _PENDING_OPS[token] = {
            "user_id": 999,
            "role": "superadmin",
            "server_id": 1,
            "command": "df -h",
            "risk_level": "LOW",
            "expires_at": datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
        }
        resp = client.post(
            "/api/assistant/ops-execute",
            json={"execution_token": token, "consent": True},
            headers=_auth(),
        )
        assert resp.status_code == 403
        mock_run.assert_not_called()
        _PENDING_OPS.pop(token, None)

    @patch("routes.assistant.run_command_stream")
    def test_high_risk_requires_second_confirmation(self, mock_run, client):
        from routes.assistant import _PENDING_OPS

        token = "test-token-high-risk"
        _PENDING_OPS[token] = {
            "user_id": 1,
            "role": "superadmin",
            "server_id": 1,
            "command": "rm -rf /tmp/x",
            "risk_level": "HIGH",
            "expires_at": datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
        }
        resp = client.post(
            "/api/assistant/ops-execute",
            json={"execution_token": token, "consent": True, "high_risk_confirmed": False},
            headers=_auth(),
        )
        assert resp.status_code == 409
        mock_run.assert_not_called()
        _PENDING_OPS.pop(token, None)

    @patch("routes.assistant.run_command_stream")
    def test_operator_high_risk_blocked_even_if_token_says_low(self, mock_run, client):
        """回归：token 签发后用 operator 身份重放，必须被重新评估拦截。"""
        from routes.assistant import _PENDING_OPS

        token = "test-token-replay"
        _PENDING_OPS[token] = {
            "user_id": 2,
            "role": "superadmin",
            "server_id": 1,
            "command": "rm -rf /tmp/x",
            "risk_level": "LOW",  # 伪造为低风险
            "expires_at": datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
        }
        resp = client.post(
            "/api/assistant/ops-execute",
            json={"execution_token": token, "consent": True, "high_risk_confirmed": True},
            headers=_auth(role="operator", user_id=2),
        )
        assert resp.status_code == 403
        mock_run.assert_not_called()
        assert token not in _PENDING_OPS

    @patch("routes.assistant.run_command_stream")
    def test_safe_command_executes_over_ssh(self, mock_run, client):
        from routes.assistant import _PENDING_OPS

        mock_run.return_value = {
            "ok": True,
            "exit_status": 0,
            "chunks": [{"stream": "stdout", "text": "Filesystem Size Used\n"}],
        }
        token = "test-token-safe"
        _PENDING_OPS[token] = {
            "user_id": 1,
            "role": "operator",
            "server_id": 3,
            "command": "df -h",
            "risk_level": "LOW",
            "expires_at": datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
        }
        resp = client.post(
            "/api/assistant/ops-execute",
            json={"execution_token": token, "consent": True},
            headers=_auth(role="operator"),
        )
        assert resp.status_code == 200
        assert "Filesystem" in resp.get_json()["data"]["stdout"]
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == 3
