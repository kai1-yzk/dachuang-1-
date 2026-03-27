from collections import Counter
from typing import Any, Dict, List

from utils.db import execute_query


def search_logs(tenant_id: int, keyword: str = "", level: str = "", server_id: int | None = None, start_time: str | None = None, end_time: str | None = None, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    where = ["1=1"]
    args: List[Any] = []

    where.append("(user_id IN (SELECT id FROM user WHERE tenant_id=%s) OR user_id IS NULL)")
    args.append(tenant_id)

    if keyword:
        where.append("(command_raw LIKE %s OR command_parsed LIKE %s OR detail LIKE %s)")
        like = f"%{keyword}%"
        args.extend([like, like, like])

    if level:
        where.append("risk_level=%s")
        args.append(level.upper())

    if server_id:
        where.append("server_id=%s")
        args.append(server_id)

    if start_time and end_time:
        where.append("created_at BETWEEN %s AND %s")
        args.extend([start_time, end_time])

    where_sql = " AND ".join(where)
    count_rows = execute_query(f"SELECT COUNT(1) AS c FROM audit_logs WHERE {where_sql}", tuple(args))
    total = int((count_rows[0] or {}).get("c") or 0) if count_rows else 0

    offset = max(page - 1, 0) * page_size
    rows = execute_query(
        f"""
        SELECT id, user_id, username, role_name, server_id, command_raw, command_parsed,
               risk_score, risk_level, action, result, detail, created_at
        FROM audit_logs
        WHERE {where_sql}
        ORDER BY id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(args + [page_size, offset]),
    )

    return {"total": total, "page": page, "page_size": page_size, "items": rows}


def anomaly_clusters(tenant_id: int, limit: int = 300) -> List[Dict[str, Any]]:
    rows = execute_query(
        """
        SELECT command_parsed, risk_level, result
        FROM audit_logs
        WHERE (user_id IN (SELECT id FROM user WHERE tenant_id=%s) OR user_id IS NULL)
        ORDER BY id DESC
        LIMIT %s
        """,
        (tenant_id, int(limit)),
    )

    patterns = []
    for row in rows:
        parsed = str(row.get("command_parsed") or "unknown").strip()
        if not parsed:
            parsed = "unknown"
        head = parsed.split(" ")[0]
        level = str(row.get("risk_level") or "LOW")
        result = str(row.get("result") or "")
        patterns.append(f"{head}|{level}|{result}")

    counter = Counter(patterns)
    clusters = []
    for token, cnt in counter.most_common(12):
        head, level, result = token.split("|", 2)
        clusters.append({
            "pattern": head,
            "risk_level": level,
            "result": result,
            "count": cnt,
        })
    return clusters
