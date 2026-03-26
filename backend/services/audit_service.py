from typing import Any, Dict, List

from utils.db import execute_query, execute_update


def write_audit_log(payload: Dict[str, Any]) -> None:
    execute_update(
        """
        INSERT INTO audit_logs
        (user_id, username, role_name, server_id, session_id, command_raw, command_parsed,
         risk_score, risk_level, action, result, detail, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """,
        (
            payload.get("user_id"),
            payload.get("username"),
            payload.get("role_name"),
            payload.get("server_id"),
            payload.get("session_id"),
            payload.get("command_raw"),
            payload.get("command_parsed"),
            float(payload.get("risk_score", 0.0)),
            payload.get("risk_level", "LOW"),
            payload.get("action"),
            payload.get("result"),
            payload.get("detail"),
        ),
    )


def list_audit_logs(limit: int = 100) -> List[Dict[str, Any]]:
    return execute_query(
        """
        SELECT id, user_id, username, role_name, server_id, session_id,
               command_raw, command_parsed, risk_score, risk_level,
               action, result, detail, created_at
        FROM audit_logs
        ORDER BY id DESC
        LIMIT %s
        """,
        (int(limit),),
    )
