import re
import shlex
import os
from typing import Any, Dict

DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bdd\b",
    r"\bfdisk\b",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r":\(\)\{:\|:&\};:",
]

OPERATOR_WHITELIST = [
    "systemctl status",
    "top",
    "tail",
    "df -h",
    "free -m",
    "netstat -an",
    "journalctl -xe",
]


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")

NL_COMMAND_MAP = {
    "检查网络状态": "netstat -an",
    "查看磁盘": "df -h",
    "查看内存": "free -m",
    "查看服务状态": "systemctl status nginx",
    "查看日志": "tail -n 100 /var/log/syslog",
}


def to_command(user_input: str) -> Dict[str, Any]:
    text = (user_input or "").strip()
    if not text:
        return {"command": "", "confidence": 0.0, "mode": "command"}

    if any(ch in text for ch in [" ", "-", "/"]):
        return {"command": text, "confidence": 1.0, "mode": "command"}

    mapped = NL_COMMAND_MAP.get(text)
    if mapped:
        return {"command": mapped, "confidence": 0.86, "mode": "language"}

    return {"command": text, "confidence": 0.5, "mode": "unknown"}


def parse_shell_ast(command: str) -> Dict[str, Any]:
    tokens = shlex.split(command or "")
    return {
        "tokens": tokens,
        "has_pipe": "|" in command,
        "has_redirect": ">" in command or "<" in command,
    }


def evaluate_risk(command: str, role_name: str, force_approved: bool = False) -> Dict[str, Any]:
    ast_info = parse_shell_ast(command)
    score = 0.0

    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command):
            score += 80

    if ast_info["has_pipe"]:
        score += 10
    if ast_info["has_redirect"]:
        score += 10

    # 分级阈值与打分口径要对齐：管道/重定向各 10 分，
    # 因此 >=10 即视为 MEDIUM（含重定向或管道的命令对 operator 一律拦截），
    # >=80（命中危险模式）为 HIGH。
    if score >= 80:
        level = "HIGH"
    elif score >= 10:
        level = "MEDIUM"
    else:
        level = "LOW"

    allowed = True
    mfa_required = False
    reason = ""

    if role_name == "operator":
        # 默认允许低风险命令，避免常见运维指令（如 ls/pwd/ps）被全部拦截。
        strict_whitelist = _bool_env("TERMINAL_STRICT_WHITELIST", default=False)
        if strict_whitelist and not any(command.startswith(prefix) for prefix in OPERATOR_WHITELIST):
            allowed = False
            reason = "普通用户仅允许白名单命令"
        if level in ("MEDIUM", "HIGH"):
            allowed = False
            reason = reason or "风险过高，已拦截"

    if role_name == "superadmin" and level == "HIGH" and not force_approved:
        allowed = False
        mfa_required = True
        reason = "高危命令需要一次性短码确认"

    return {
        "command": command,
        "parsed_command": " ".join(ast_info["tokens"]),
        "risk_score": score,
        "risk_level": level,
        "allowed": allowed,
        "mfa_required": mfa_required,
        "reason": reason,
        "ast": ast_info,
    }
