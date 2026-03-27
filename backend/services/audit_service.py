import re
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


def get_security_overview(limit: int = 500) -> Dict[str, Any]:
    rows = execute_query(
        """
        SELECT id, command_raw, command_parsed, risk_score, risk_level, action, result, detail, created_at
        FROM audit_logs
        ORDER BY id DESC
        LIMIT %s
        """,
        (int(limit),),
    )

    ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    blocked_rows = []
    high_risk_rows = []
    blocked_ips = set()

    for row in rows:
        result = str(row.get("result") or "").lower()
        action = str(row.get("action") or "").lower()
        detail = str(row.get("detail") or "")
        risk_level = str(row.get("risk_level") or "").upper()
        risk_score = float(row.get("risk_score") or 0)

        text_blob = " ".join([
            str(row.get("command_raw") or ""),
            str(row.get("command_parsed") or ""),
            detail,
        ])
        ips = ip_pattern.findall(text_blob)

        is_blocked = (
            result in {"blocked", "deny", "denied", "forbidden", "rejected"}
            or "block" in result
            or "block" in action
            or "拦截" in detail
        )
        is_abnormal = risk_level in {"HIGH", "CRITICAL"} or risk_score >= 70

        if is_blocked:
            blocked_rows.append(row)
            for ip in ips:
                blocked_ips.add(ip)

        if is_abnormal:
            high_risk_rows.append(row)

    recent_blocked_events = [
        {
            "id": item.get("id"),
            "time": item.get("created_at"),
            "action": item.get("action"),
            "result": item.get("result"),
            "detail": item.get("detail"),
        }
        for item in blocked_rows[:8]
    ]

    return {
        "window_count": len(rows),
        "blocked_request_count": len(blocked_rows),
        "abnormal_request_count": len(high_risk_rows),
        "blocked_ip_count": len(blocked_ips),
        "blocked_ips": sorted(list(blocked_ips))[:20],
        "recent_blocked_events": recent_blocked_events,
    }
