import json
from typing import Any, Dict, List

from services.ssh_service import run_command_stream
from utils.db import execute_query, execute_update


def create_batch_job(tenant_id: int, user_id: int, command: str, server_ids: List[int]) -> int | None:
    execute_update(
        "INSERT INTO batch_jobs (tenant_id, command_text, target_server_ids, status, created_by, created_at, updated_at) VALUES (%s, %s, %s, 'pending_approval', %s, NOW(), NOW())",
        (tenant_id, command, json.dumps(server_ids, ensure_ascii=False), user_id),
    )
    rows = execute_query("SELECT id FROM batch_jobs WHERE tenant_id=%s ORDER BY id DESC LIMIT 1", (tenant_id,))
    return int(rows[0]["id"]) if rows else None


def list_batch_jobs(tenant_id: int, limit: int = 100):
    return execute_query(
        "SELECT id, command_text, target_server_ids, status, approval_status, created_by, created_at, updated_at FROM batch_jobs WHERE tenant_id=%s ORDER BY id DESC LIMIT %s",
        (tenant_id, int(limit)),
    )


def approve_batch_job(tenant_id: int, job_id: int, approver_id: int, approve: bool):
    rows = execute_query("SELECT * FROM batch_jobs WHERE id=%s AND tenant_id=%s LIMIT 1", (job_id, tenant_id))
    if not rows:
        return {"ok": False, "message": "job not found"}

    if not approve:
        execute_update("UPDATE batch_jobs SET status='rejected', approval_status='rejected', approver_id=%s, updated_at=NOW() WHERE id=%s", (approver_id, job_id))
        return {"ok": True, "message": "rejected"}

    job = rows[0]
    server_ids = json.loads(job.get("target_server_ids") or "[]")
    command = str(job.get("command_text") or "")
    execute_update("UPDATE batch_jobs SET status='running', approval_status='approved', approver_id=%s, updated_at=NOW() WHERE id=%s", (approver_id, job_id))

    success = 0
    failed = 0
    for sid in server_ids:
        try:
            result = run_command_stream(int(sid), command, timeout=30)
            exit_status = int(result.get("exit_status") or 0)
            status = "success" if exit_status == 0 else "failed"
            if status == "success":
                success += 1
            else:
                failed += 1
            execute_update(
                "INSERT INTO batch_job_results (job_id, server_id, status, result_json, created_at) VALUES (%s, %s, %s, %s, NOW())",
                (job_id, sid, status, json.dumps({"exit_status": exit_status}, ensure_ascii=False)),
            )
        except Exception as e:
            failed += 1
            execute_update(
                "INSERT INTO batch_job_results (job_id, server_id, status, result_json, created_at) VALUES (%s, %s, 'failed', %s, NOW())",
                (job_id, sid, json.dumps({"error": str(e)}, ensure_ascii=False)),
            )

    final_status = "success" if failed == 0 else ("partial" if success > 0 else "failed")
    execute_update("UPDATE batch_jobs SET status=%s, updated_at=NOW() WHERE id=%s", (final_status, job_id))
    return {"ok": True, "message": final_status, "success": success, "failed": failed}


def job_results(tenant_id: int, job_id: int):
    owner = execute_query("SELECT id FROM batch_jobs WHERE id=%s AND tenant_id=%s LIMIT 1", (job_id, tenant_id))
    if not owner:
        return []
    return execute_query("SELECT id, server_id, status, result_json, created_at FROM batch_job_results WHERE job_id=%s ORDER BY id ASC", (job_id,))
