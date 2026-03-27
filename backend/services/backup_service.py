import json
from typing import Any, Dict, List

from services.ssh_service import run_command_stream
from utils.db import execute_query, execute_update


def _find_latest_job_id(tenant_id: int) -> int | None:
    rows = execute_query("SELECT id FROM backup_jobs WHERE tenant_id=%s ORDER BY id DESC LIMIT 1", (tenant_id,))
    return int(rows[0]["id"]) if rows else None


def create_backup_job(tenant_id: int, user_id: int, server_id: int, backup_type: str, target_path: str) -> int | None:
    execute_update(
        """
        INSERT INTO backup_jobs
        (tenant_id, server_id, backup_type, target_path, status, created_by, created_at, updated_at)
        VALUES (%s, %s, %s, %s, 'pending', %s, NOW(), NOW())
        """,
        (tenant_id, server_id, backup_type, target_path, user_id),
    )
    return _find_latest_job_id(tenant_id)


def run_backup_job(job_id: int) -> Dict[str, Any]:
    rows = execute_query("SELECT * FROM backup_jobs WHERE id=%s LIMIT 1", (job_id,))
    if not rows:
        return {"ok": False, "message": "job not found"}
    job = rows[0]
    server_id = int(job.get("server_id"))
    backup_type = str(job.get("backup_type") or "config")
    target_path = str(job.get("target_path") or "/tmp")

    if backup_type == "database":
        filename = "db_backup.sql.gz"
        cmd = f"mkdir -p {target_path} && mysqldump --all-databases | gzip > {target_path}/{filename}"
    else:
        filename = "config_backup.tar.gz"
        cmd = f"mkdir -p {target_path} && tar -czf {target_path}/{filename} /etc"

    execute_update("UPDATE backup_jobs SET status='running', updated_at=NOW() WHERE id=%s", (job_id,))
    try:
        result = run_command_stream(server_id, cmd, timeout=120)
        exit_status = int(result.get("exit_status") or 0)
        chunks = result.get("chunks") or []
        stdout = "".join(c.get("text", "") for c in chunks if c.get("stream") == "stdout")
        stderr = "".join(c.get("text", "") for c in chunks if c.get("stream") == "stderr")
        status = "success" if exit_status == 0 else "failed"
        execute_update(
            "UPDATE backup_jobs SET status=%s, result_json=%s, updated_at=NOW() WHERE id=%s",
            (status, json.dumps({"exit_status": exit_status, "stdout": stdout[-2000:], "stderr": stderr[-2000:]}, ensure_ascii=False), job_id),
        )
        if exit_status == 0:
            execute_update(
                "INSERT INTO backup_artifacts (job_id, file_path, file_type, created_at) VALUES (%s, %s, %s, NOW())",
                (job_id, f"{target_path}/{filename}", backup_type),
            )
        return {"ok": exit_status == 0, "message": status, "file_path": f"{target_path}/{filename}"}
    except Exception as e:
        execute_update("UPDATE backup_jobs SET status='failed', result_json=%s, updated_at=NOW() WHERE id=%s", (json.dumps({"error": str(e)}, ensure_ascii=False), job_id))
        return {"ok": False, "message": str(e)}


def list_backup_jobs(tenant_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    return execute_query(
        """
        SELECT id, tenant_id, server_id, backup_type, target_path, status, result_json, created_by, created_at, updated_at
        FROM backup_jobs
        WHERE tenant_id=%s
        ORDER BY id DESC
        LIMIT %s
        """,
        (tenant_id, int(limit)),
    )


def restore_backup(tenant_id: int, user_id: int, artifact_id: int) -> Dict[str, Any]:
    rows = execute_query(
        """
        SELECT a.id, a.file_path, a.file_type, j.server_id
        FROM backup_artifacts a JOIN backup_jobs j ON a.job_id=j.id
        WHERE a.id=%s AND j.tenant_id=%s
        LIMIT 1
        """,
        (artifact_id, tenant_id),
    )
    if not rows:
        return {"ok": False, "message": "artifact not found"}
    art = rows[0]
    server_id = int(art.get("server_id"))
    file_path = str(art.get("file_path"))
    file_type = str(art.get("file_type") or "config")

    if file_type == "database":
        cmd = f"gzip -dc {file_path} | mysql"
    else:
        cmd = f"tar -xzf {file_path} -C /"

    execute_update(
        "INSERT INTO restore_records (tenant_id, artifact_id, server_id, status, created_by, created_at, updated_at) VALUES (%s, %s, %s, 'running', %s, NOW(), NOW())",
        (tenant_id, artifact_id, server_id, user_id),
    )
    rid_rows = execute_query("SELECT id FROM restore_records WHERE tenant_id=%s ORDER BY id DESC LIMIT 1", (tenant_id,))
    restore_id = int(rid_rows[0]["id"]) if rid_rows else None

    try:
        result = run_command_stream(server_id, cmd, timeout=120)
        exit_status = int(result.get("exit_status") or 0)
        status = "success" if exit_status == 0 else "failed"
        execute_update("UPDATE restore_records SET status=%s, result_json=%s, updated_at=NOW() WHERE id=%s", (status, json.dumps({"exit_status": exit_status}, ensure_ascii=False), restore_id))
        return {"ok": exit_status == 0, "message": status, "restore_id": restore_id}
    except Exception as e:
        execute_update("UPDATE restore_records SET status='failed', result_json=%s, updated_at=NOW() WHERE id=%s", (json.dumps({"error": str(e)}, ensure_ascii=False), restore_id))
        return {"ok": False, "message": str(e), "restore_id": restore_id}
