import datetime
import secrets
from typing import Dict

import jwt
from flask import current_app, request
from flask_socketio import emit, join_room

from services.audit_service import write_audit_log
from services.command_risk_service import evaluate_risk, to_command
from utils.db import execute_query, execute_update

SESSION_TIMEOUT_SECONDS = 15 * 60


def _decode_token(token: str):
    return jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])


def _upsert_session(session_id: str, user_id: int, server_id: int):
    execute_update(
        """
        INSERT INTO terminal_sessions
        (session_id, user_id, server_id, last_activity, status, created_at, updated_at)
        VALUES (%s, %s, %s, NOW(), 'active', NOW(), NOW())
        ON DUPLICATE KEY UPDATE last_activity=NOW(), status='active', updated_at=NOW()
        """,
        (session_id, user_id, server_id),
    )


def _request_short_code(user_id: int, session_id: str, command_text: str) -> str:
    code = f"{secrets.randbelow(10**6):06d}"
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
    execute_update(
        """
        INSERT INTO mfa_challenges
        (user_id, session_id, command_text, short_code, expires_at, used, created_at)
        VALUES (%s, %s, %s, %s, %s, 0, NOW())
        """,
        (user_id, session_id, command_text, code, expires_at),
    )
    return code


def _verify_short_code(user_id: int, session_id: str, code: str) -> bool:
    rows = execute_query(
        """
        SELECT id FROM mfa_challenges
        WHERE user_id=%s AND session_id=%s AND short_code=%s AND used=0 AND expires_at > NOW()
        ORDER BY id DESC LIMIT 1
        """,
        (user_id, session_id, code),
    )
    if not rows:
        return False
    execute_update("UPDATE mfa_challenges SET used=1 WHERE id=%s", (rows[0]["id"],))
    return True


def init_ws_handlers(socketio):
    active_sessions: Dict[str, Dict] = {}

    @socketio.on("terminal_connect")
    def terminal_connect(payload):
        token = (payload or {}).get("token")
        server_id = int((payload or {}).get("server_id") or 1)
        if not token:
            emit("terminal_error", {"message": "missing token"})
            return

        try:
            user = _decode_token(token)
        except Exception:
            emit("terminal_error", {"message": "invalid token"})
            return

        role_name = user.get("role", "operator")
        session_id = secrets.token_urlsafe(16)
        active_sessions[session_id] = {
            "user_id": user.get("user_id"),
            "username": user.get("username", "unknown"),
            "role_name": role_name,
            "server_id": server_id,
            "last_activity": datetime.datetime.utcnow(),
            "force_approved": False,
        }
        _upsert_session(session_id, user.get("user_id"), server_id)

        join_room(session_id)
        emit(
            "terminal_ready",
            {"session_id": session_id, "server_id": server_id, "role": role_name, "timeout": SESSION_TIMEOUT_SECONDS},
        )

    @socketio.on("terminal_command")
    def terminal_command(payload):
        payload = payload or {}
        session_id = payload.get("session_id")
        user_text = (payload.get("input") or "").strip()
        if not session_id or session_id not in active_sessions:
            emit("terminal_error", {"message": "invalid session"})
            return

        session = active_sessions[session_id]
        now = datetime.datetime.utcnow()
        if (now - session["last_activity"]).total_seconds() > SESSION_TIMEOUT_SECONDS:
            emit("terminal_timeout", {"message": "session timeout"}, room=session_id)
            execute_update("UPDATE terminal_sessions SET status='timeout', updated_at=NOW() WHERE session_id=%s", (session_id,))
            active_sessions.pop(session_id, None)
            return

        session["last_activity"] = now
        execute_update("UPDATE terminal_sessions SET last_activity=NOW(), updated_at=NOW() WHERE session_id=%s", (session_id,))

        mapped = to_command(user_text)
        evaluated = evaluate_risk(mapped["command"], session["role_name"], session.get("force_approved", False))

        write_audit_log(
            {
                "user_id": session["user_id"],
                "username": session["username"],
                "role_name": session["role_name"],
                "server_id": session["server_id"],
                "session_id": session_id,
                "command_raw": user_text,
                "command_parsed": evaluated["parsed_command"],
                "risk_score": evaluated["risk_score"],
                "risk_level": evaluated["risk_level"],
                "action": "execute_request",
                "result": "blocked" if not evaluated["allowed"] else "allowed",
                "detail": evaluated["reason"] or "ok",
            }
        )

        if evaluated["mfa_required"]:
            code = _request_short_code(session["user_id"], session_id, evaluated["command"])
            emit(
                "mfa_required",
                {
                    "message": "高危命令需要短码确认",
                    "hint": "演示环境直接回传短码",
                    "demo_code": code,
                    "command": evaluated["command"],
                },
                room=session_id,
            )
            return

        if not evaluated["allowed"]:
            emit(
                "terminal_output",
                {
                    "type": "blocked",
                    "text": f"Blocked: {evaluated['reason']} (risk={evaluated['risk_level']})",
                    "audit": evaluated,
                },
                room=session_id,
            )
            return

        emit(
            "terminal_output",
            {
                "type": "output",
                "text": f"[server-{session['server_id']}] Executed: {evaluated['command']}\nOK",
                "audit": evaluated,
            },
            room=session_id,
        )

    @socketio.on("mfa_confirm")
    def mfa_confirm(payload):
        payload = payload or {}
        session_id = payload.get("session_id")
        code = (payload.get("code") or "").strip()
        if not session_id or session_id not in active_sessions:
            emit("terminal_error", {"message": "invalid session"})
            return

        session = active_sessions[session_id]
        ok = _verify_short_code(session["user_id"], session_id, code)
        if not ok:
            emit("mfa_result", {"ok": False, "message": "短码无效或已过期"}, room=session_id)
            return

        session["force_approved"] = True
        emit("mfa_result", {"ok": True, "message": "短码验证通过，请重新执行命令"}, room=session_id)

    @socketio.on("terminal_disconnect")
    def terminal_disconnect(payload):
        session_id = (payload or {}).get("session_id")
        if session_id and session_id in active_sessions:
            execute_update("UPDATE terminal_sessions SET status='closed', updated_at=NOW() WHERE session_id=%s", (session_id,))
            active_sessions.pop(session_id, None)
