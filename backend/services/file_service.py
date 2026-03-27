import base64
from typing import Any, Dict, List

from services.ssh_service import run_command_stream


def _quote(path: str) -> str:
    return path.replace("'", "'\"'\"'")


def list_dir(server_id: int, path: str) -> List[Dict[str, Any]]:
    safe = _quote(path)
    cmd = f"ls -la '{safe}'"
    result = run_command_stream(server_id, cmd, timeout=20)
    lines = "".join(c.get("text", "") for c in result.get("chunks", []) if c.get("stream") == "stdout").splitlines()
    items = []
    for ln in lines[1:]:
        parts = ln.split(maxsplit=8)
        if len(parts) < 9:
            continue
        perm = parts[0]
        name = parts[8]
        if name in {".", ".."}:
            continue
        items.append({
            "name": name,
            "is_dir": perm.startswith("d"),
            "perm": perm,
            "size": parts[4],
            "mtime": " ".join(parts[5:8]),
        })
    return items


def read_file_text(server_id: int, path: str) -> Dict[str, Any]:
    safe = _quote(path)
    cmd = f"base64 -w 0 '{safe}'"
    result = run_command_stream(server_id, cmd, timeout=20)
    exit_status = int(result.get("exit_status") or 0)
    if exit_status != 0:
        stderr = "".join(c.get("text", "") for c in result.get("chunks", []) if c.get("stream") == "stderr")
        return {"ok": False, "message": stderr[-300:]}
    data = "".join(c.get("text", "") for c in result.get("chunks", []) if c.get("stream") == "stdout").strip()
    content = base64.b64decode(data.encode("utf-8")).decode("utf-8", errors="replace") if data else ""
    return {"ok": True, "content": content}


def write_file_text(server_id: int, path: str, content: str) -> Dict[str, Any]:
    safe = _quote(path)
    b64 = base64.b64encode((content or "").encode("utf-8")).decode("utf-8")
    cmd = f"echo '{b64}' | base64 -d > '{safe}'"
    result = run_command_stream(server_id, cmd, timeout=20)
    ok = int(result.get("exit_status") or 0) == 0
    return {"ok": ok, "message": "ok" if ok else "failed"}


def delete_path(server_id: int, path: str, recursive: bool = False) -> Dict[str, Any]:
    safe = _quote(path)
    cmd = f"rm {'-rf' if recursive else '-f'} '{safe}'"
    result = run_command_stream(server_id, cmd, timeout=20)
    ok = int(result.get("exit_status") or 0) == 0
    return {"ok": ok, "message": "ok" if ok else "failed"}


def mkdir(server_id: int, path: str) -> Dict[str, Any]:
    safe = _quote(path)
    cmd = f"mkdir -p '{safe}'"
    result = run_command_stream(server_id, cmd, timeout=20)
    ok = int(result.get("exit_status") or 0) == 0
    return {"ok": ok, "message": "ok" if ok else "failed"}
