"""命令风险评估与 AI 命令白名单校验的核心行为测试。"""
import pytest

from services.command_risk_service import evaluate_risk, to_command, parse_shell_ast
from utils.security import validate_ai_command


class TestDangerousCommandBlocking:
    @pytest.mark.parametrize(
        "command",
        [
            "rm -rf /",
            "rm -rf /var/lib",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.ext4 /dev/sdb1",
            "reboot",
            "shutdown -h now",
            "fdisk /dev/sda",
        ],
    )
    def test_dangerous_commands_are_high_risk(self, command):
        result = evaluate_risk(command, "operator")
        assert result["risk_level"] == "HIGH"
        assert result["allowed"] is False
        assert result["risk_score"] >= 80

    def test_low_risk_readonly_command_allowed_for_operator(self):
        result = evaluate_risk("df -h", "operator")
        assert result["risk_level"] == "LOW"
        assert result["allowed"] is True

    def test_pipe_and_redirect_raise_risk_level(self):
        # 管道 + 重定向各 +10，仍属中风险，但 operator 会被拦截
        result = evaluate_risk("cat /etc/passwd | grep root > /tmp/out", "operator")
        assert result["risk_score"] >= 20
        assert result["allowed"] is False

    def test_superadmin_high_risk_requires_mfa(self):
        result = evaluate_risk("rm -rf /tmp/x", "superadmin", force_approved=False)
        assert result["risk_level"] == "HIGH"
        assert result["allowed"] is False
        assert result["mfa_required"] is True

    def test_superadmin_high_risk_allowed_after_approval(self):
        result = evaluate_risk("rm -rf /tmp/x", "superadmin", force_approved=True)
        assert result["allowed"] is True
        assert result["mfa_required"] is False


class TestNaturalLanguageMapping:
    def test_nl_command_is_mapped(self):
        assert to_command("查看磁盘")["command"] == "df -h"
        assert to_command("查看磁盘")["mode"] == "language"

    def test_raw_command_passthrough(self):
        mapped = to_command("systemctl status nginx")
        assert mapped["command"] == "systemctl status nginx"
        assert mapped["mode"] == "command"

    def test_empty_input(self):
        mapped = to_command("")
        assert mapped["command"] == ""

    def test_parse_shell_ast_detects_pipe(self):
        info = parse_shell_ast("ps aux | grep nginx")
        assert info["has_pipe"] is True
        assert info["tokens"][0] == "ps"


class TestValidateAICommand:
    def test_blocks_dangerous_keywords(self):
        for cmd in ["rm -rf /", "sudo rm /etc/hosts", "reboot now"]:
            ok, msg = validate_ai_command(cmd)
            assert ok is False, f"{cmd} 应被拦截"
            assert msg

    def test_allows_safe_command(self):
        ok, _ = validate_ai_command("df -h")
        assert ok is True

    def test_empty_command_rejected(self):
        ok, _ = validate_ai_command("")
        assert ok is False
