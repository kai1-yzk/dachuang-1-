"""命令回退链 _try_commands 的回归测试。

背景：`systemctl restart` 因权限失败后回退到 `sudo -n systemctl` 成功，
但原实现把前序失败信息写进 stderr，导致 /api/services/control 返回
{"ok": true, "message": "ok", "stderr": "Interactive authentication required"}，
前端据 message 显示为失败。
"""
from unittest.mock import patch

from services import service_manager as sm


def _ok(stdout=""):
    return {"exit_status": 0, "stdout": stdout, "stderr": ""}


def _fail(stderr="boom"):
    return {"exit_status": 1, "stdout": "", "stderr": stderr}


class TestTryCommands:
    def test_first_command_success(self):
        with patch.object(sm, "_run", return_value=_ok("done")):
            result = sm._try_commands(1, ["a", "b"])
        assert result["exit_status"] == 0
        assert result["stderr"] == ""

    def test_fallback_success_has_no_stale_error(self):
        """关键回归：回退成功后不得残留前一条命令的错误信息。"""
        side_effect = [_fail("Interactive authentication required"), _ok()]
        with patch.object(sm, "_run", side_effect=side_effect):
            result = sm._try_commands(1, ["systemctl restart x", "sudo -n systemctl restart x"])

        assert result["exit_status"] == 0
        assert result["stderr"] == "", f"成功结果不应含错误信息，实际: {result['stderr']!r}"

    def test_all_failed_returns_aggregated_errors(self):
        side_effect = [_fail("err-one"), _fail("err-two")]
        with patch.object(sm, "_run", side_effect=side_effect):
            result = sm._try_commands(1, ["a", "b"])

        assert result["exit_status"] == 1
        assert "err-one" in result["stderr"]
        assert "err-two" in result["stderr"]

    def test_stops_at_first_success(self):
        with patch.object(sm, "_run", side_effect=[_fail(), _ok(), _ok()]) as mock_run:
            sm._try_commands(1, ["a", "b", "c"])
        assert mock_run.call_count == 2, "成功后不应继续尝试剩余命令"
