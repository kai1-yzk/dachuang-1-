from flask import Blueprint, jsonify, request
import datetime
import secrets

from services.command_risk_service import evaluate_risk, to_command
from services.ssh_service import run_command_stream
from utils.db import execute_query, execute_update
from utils.security import ensure_role, get_request_tenant_id

assistant_bp = Blueprint("assistant", __name__)
_PENDING_OPS = {}
_OPS_TOKEN_TTL_SECONDS = 300


def _is_admin_role(role: str) -> bool:
    return role in {"tenant_admin", "platform_admin", "superadmin"}


def _cleanup_pending_tokens():
    now = datetime.datetime.utcnow()
    expired_keys = [k for k, v in _PENDING_OPS.items() if v.get("expires_at") < now]
    for key in expired_keys:
        _PENDING_OPS.pop(key, None)


def _safe_has_table(name: str) -> bool:
    rows = execute_query("SHOW TABLES LIKE %s", (name,))
    return bool(rows)


def _fetch_context(question: str, tenant_id: int, server_id=None):
    snippets = []

    audit_sql = "SELECT id, command_raw, result, detail FROM audit_logs WHERE 1=1"
    args = []
    if _safe_has_table("audit_logs"):
        if _safe_has_table("user"):
            audit_sql += " AND user_id IN (SELECT id FROM user WHERE tenant_id=%s)"
            args.append(tenant_id)
        if server_id:
            audit_sql += " AND server_id=%s"
            args.append(server_id)
        audit_sql += " ORDER BY id DESC LIMIT 30"
        rows = execute_query(audit_sql, tuple(args) if args else None)
        for r in rows:
            snippets.append({
                "source": "audit",
                "id": r.get("id"),
                "text": f"command={r.get('command_raw')} result={r.get('result')} detail={r.get('detail')}",
            })

    return snippets[:12]


def _suggestions(question: str):
    q = question.lower()
    suggestions = []
    if "nginx" in q or "服务" in q:
        suggestions.append({
            "title": "检查服务状态",
            "action_type": "command",
            "command": "systemctl status nginx",
            "risk_level": "low",
            "requires_approval": False,
        })
    if "磁盘" in q or "disk" in q:
        suggestions.append({
            "title": "检查磁盘占用",
            "action_type": "command",
            "command": "df -h",
            "risk_level": "low",
            "requires_approval": False,
        })
    if "重启" in q or "restart" in q:
        suggestions.append({
            "title": "重启高风险操作（需审批）",
            "action_type": "command",
            "command": "sudo systemctl restart <service_name>",
            "risk_level": "high",
            "requires_approval": True,
        })
    if not suggestions:
        suggestions.append({
            "title": "查看最近异常命令",
            "action_type": "command",
            "command": "journalctl -xe | tail -n 50",
            "risk_level": "medium",
            "requires_approval": False,
        })
    return suggestions


@assistant_bp.route("/query", methods=["POST"])
def query_assistant():
    deny = ensure_role(request, {"tenant_admin", "tenant_operator", "superadmin", "operator"})
    if deny:
        return deny

    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"code": 400, "message": "question is required", "data": None}), 400

    tenant_id = get_request_tenant_id(request)
    server_id = payload.get("server_id")

    context = _fetch_context(question, tenant_id, server_id=server_id)
    suggestions = _suggestions(question)

    answer = "基于当前运维记录，建议先执行低风险检查，再根据结果决定是否走审批执行高风险操作。"
    return jsonify(
        {
            "code": 200,
            "message": "ok",
            "data": {
                "answer": answer,
                "suggestions": suggestions,
                "citations": context,
                "risk_level": "high" if any(s.get("risk_level") == "high" for s in suggestions) else "medium",
            },
        }
    )


@assistant_bp.route("/suggestion/approve", methods=["POST"])
def approve_suggestion():
    deny = ensure_role(request, {"tenant_admin", "superadmin", "operator"})
    if deny:
        return deny

    payload = request.get_json(silent=True) or {}
    suggestion = payload.get("suggestion") or {}
    tenant_id = get_request_tenant_id(request)
    user_id = int(getattr(request, "user", {}).get("user_id") or 0)

    if not _safe_has_table("assistant_approvals"):
        return jsonify({"code": 500, "message": "assistant_approvals table missing", "data": None}), 500

    execute_update(
        """
        INSERT INTO assistant_approvals
        (tenant_id, user_id, suggestion_json, status, created_at)
        VALUES (%s, %s, %s, 'approved', NOW())
        """,
        (tenant_id, user_id, str(suggestion)),
    )

    return jsonify({"code": 200, "message": "approved", "data": {"approved": True}})


@assistant_bp.route("/ops-plan", methods=["POST"])
def ops_plan():
    deny = ensure_role(request, {"tenant_admin", "tenant_operator", "platform_admin", "superadmin", "operator"})
    if deny:
        return deny

    payload = request.get_json(silent=True) or {}
    command_text = (payload.get("command") or "").strip()
    server_id = int(payload.get("server_id") or 0)
    if not command_text or not server_id:
        return jsonify({"code": 400, "message": "command and server_id are required", "data": None}), 400

    role = getattr(request, "user", {}).get("role", "operator")
    mapped = to_command(command_text)
    evaluated = evaluate_risk(mapped.get("command") or command_text, role, force_approved=False)

    steps = [
        "1) 建议先执行命令前置检查（资源与权限）",
        f"2) 执行命令: {evaluated.get('command')}",
        "3) 校验执行结果是否符合预期，并记录审计日志",
    ]
    expected = "命令正常返回退出状态 exit_status=0，目标服务状态恢复或指标回落。"

    token = secrets.token_urlsafe(18)
    _cleanup_pending_tokens()
    _PENDING_OPS[token] = {
        "user_id": int(getattr(request, "user", {}).get("user_id") or 0),
        "role": role,
        "server_id": server_id,
        "command": evaluated.get("command") or command_text,
        "risk_level": evaluated.get("risk_level"),
        "expires_at": datetime.datetime.utcnow() + datetime.timedelta(seconds=_OPS_TOKEN_TTL_SECONDS),
    }

    data = {
        "solution": {
            "steps": steps,
            "expected_effect": expected,
        },
        "risk": {
            "level": evaluated.get("risk_level"),
            "score": evaluated.get("risk_score"),
            "is_high_risk": evaluated.get("risk_level") == "HIGH",
            "risk_consequence": "可能导致服务中断或数据丢失" if evaluated.get("risk_level") == "HIGH" else "风险可控",
        },
        "requires_explicit_consent": True,
        "execution_token": token,
        "token_ttl_seconds": _OPS_TOKEN_TTL_SECONDS,
        "ask": "是否允许AI自动执行该命令？",
    }
    return jsonify({"code": 200, "message": "ok", "data": data})


@assistant_bp.route("/ops-execute", methods=["POST"])
def ops_execute():
    deny = ensure_role(request, {"tenant_admin", "platform_admin", "superadmin", "operator"})
    if deny:
        return deny

    payload = request.get_json(silent=True) or {}
    token = (payload.get("execution_token") or "").strip()
    consent = bool(payload.get("consent", False))
    high_risk_confirmed = bool(payload.get("high_risk_confirmed", False))
    if not token:
        return jsonify({"code": 400, "message": "execution_token is required", "data": None}), 400

    _cleanup_pending_tokens()
    pending = _PENDING_OPS.get(token)
    if not pending:
        return jsonify({"code": 404, "message": "execution token expired or invalid", "data": None}), 404

    current_user_id = int(getattr(request, "user", {}).get("user_id") or 0)
    current_role = getattr(request, "user", {}).get("role", "operator")
    if pending.get("user_id") != current_user_id:
        return jsonify({"code": 403, "message": "token does not belong to current user", "data": None}), 403

    if not _is_admin_role(current_role):
        return jsonify({"code": 403, "message": "only admin can execute operation", "data": None}), 403

    if not consent:
        return jsonify({"code": 400, "message": "consent required before execution", "data": None}), 400

    if pending.get("risk_level") == "HIGH" and not high_risk_confirmed:
        return jsonify({
            "code": 409,
            "message": "high risk command requires second confirmation",
            "data": {"risk_level": "极高风险", "risk_consequence": "可能导致数据丢失或业务中断"},
        }), 409

    try:
        result = run_command_stream(int(pending["server_id"]), str(pending["command"]), timeout=25)
        stdout = "".join(c.get("text", "") for c in result.get("chunks", []) if c.get("stream") == "stdout")
        stderr = "".join(c.get("text", "") for c in result.get("chunks", []) if c.get("stream") == "stderr")
        _PENDING_OPS.pop(token, None)
        return jsonify({
            "code": 200,
            "message": "executed",
            "data": {
                "exit_status": int(result.get("exit_status") or 0),
                "stdout": stdout[-3000:],
                "stderr": stderr[-1500:],
            },
        })
    except Exception as e:
        return jsonify({"code": 500, "message": f"execute failed: {str(e)}", "data": None}), 500
