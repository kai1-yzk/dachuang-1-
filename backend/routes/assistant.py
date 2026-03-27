from flask import Blueprint, jsonify, request

from utils.db import execute_query, execute_update
from utils.security import ensure_role, get_request_tenant_id

assistant_bp = Blueprint("assistant", __name__)


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
