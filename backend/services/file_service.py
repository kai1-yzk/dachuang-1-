import base64
from typing import Any, Dict, List

from services.ssh_service import run_command_stream


class RemoteFileError(Exception):
    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type
        self.message = message


def _extract_stream_text(result: Dict[str, Any], stream: str) -> str:
    return "".join(c.get("text", "") for c in result.get("chunks", []) if c.get("stream") == stream)


def _classify_error(stderr: str) -> str:
    lowered = (stderr or "").lower()
    if "no such file or directory" in lowered or "cannot access" in lowered and "no such" in lowered:
        return "not_found"
    if "permission denied" in lowered:
        return "permission_denied"
    if (
        ("connection" in lowered and "timed out" in lowered)
        or "connection refused" in lowered
        or "no route to host" in lowered
        or "host key verification failed" in lowered
        or "network is unreachable" in lowered
    ):
        return "ssh_unavailable"
    return "execution_failed"


def _quote(path: str) -> str:
    return path.replace("'", "'\"'\"'")


def list_dir(server_id: int, path: str) -> List[Dict[str, Any]]:
    safe = _quote(path)
    cmd = f"ls -la '{safe}'"
    try:
        result = run_command_stream(server_id, cmd, timeout=20)
    except Exception as e:
        raise RemoteFileError("ssh_unavailable", f"ssh unavailable: {str(e)}") from e

    if int(result.get("exit_status") or 0) != 0:
        stderr = _extract_stream_text(result, "stderr")
        error_type = _classify_error(stderr)
        raise RemoteFileError(error_type, (stderr or "list dir failed")[-300:])

    lines = _extract_stream_text(result, "stdout").splitlines()
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
    stderr = "".join(c.get("text", "") for c in result.get("chunks", []) if c.get("stream") == "stderr")
    return {"ok": ok, "message": "ok" if ok else (stderr[-300:] or "failed")}


def delete_path(server_id: int, path: str, recursive: bool = False) -> Dict[str, Any]:
    safe = _quote(path)
    cmd = (
        f"if [ ! -e '{safe}' ]; then echo 'No such file or directory' 1>&2; exit 4; fi; "
        f"rm {'-rf' if recursive else '-f'} '{safe}'"
    )
    result = run_command_stream(server_id, cmd, timeout=20)
    ok = int(result.get("exit_status") or 0) == 0
    stderr = "".join(c.get("text", "") for c in result.get("chunks", []) if c.get("stream") == "stderr")
    return {"ok": ok, "message": "ok" if ok else (stderr[-300:] or "failed")}


def mkdir(server_id: int, path: str) -> Dict[str, Any]:
    safe = _quote(path)
    cmd = f"mkdir -p '{safe}'"
    result = run_command_stream(server_id, cmd, timeout=20)
    ok = int(result.get("exit_status") or 0) == 0
    stderr = "".join(c.get("text", "") for c in result.get("chunks", []) if c.get("stream") == "stderr")
    return {"ok": ok, "message": "ok" if ok else (stderr[-300:] or "failed")}


def get_server_info(server_id: int) -> Dict[str, Any]:
    result = run_command_stream(
        server_id,
        "uname -a; echo '---'; hostname; echo '---'; whoami; echo '---'; uptime; echo '---'; df -h; echo '---'; ip -brief address 2>/dev/null || ifconfig 2>/dev/null",
        timeout=25,
    )
    stdout = "".join(c.get("text", "") for c in result.get("chunks", []) if c.get("stream") == "stdout")
    stderr = "".join(c.get("text", "") for c in result.get("chunks", []) if c.get("stream") == "stderr")
    ok = int(result.get("exit_status") or 0) == 0
    return {
        "ok": ok,
        "message": "ok" if ok else (stderr[-300:] or "failed"),
        "info": stdout[-12000:],
        "stderr": stderr[-1000:],
    }
