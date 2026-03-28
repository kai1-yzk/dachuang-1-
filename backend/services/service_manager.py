from typing import Any, Dict, List

from services.ssh_service import run_command_stream

COMMON_SERVICES = ["nginx", "mysql", "redis", "docker", "ssh", "cron"]


def _safe_tail(text: str, limit: int = 2000) -> str:
    return (text or "")[-limit:]


def _run(server_id: int, command: str, timeout: int = 20) -> Dict[str, Any]:
    result = run_command_stream(server_id, command, timeout=timeout)
    stdout = "".join(chunk.get("text", "") for chunk in result.get("chunks", []) if chunk.get("stream") == "stdout")
    stderr = "".join(chunk.get("text", "") for chunk in result.get("chunks", []) if chunk.get("stream") == "stderr")
    return {
        "exit_status": int(result.get("exit_status") or 0),
        "stdout": _safe_tail(stdout),
        "stderr": _safe_tail(stderr),
    }


def _try_commands(server_id: int, commands: List[str], timeout: int = 20) -> Dict[str, Any]:
    last = {"exit_status": 1, "stdout": "", "stderr": "no command executed"}
    for cmd in commands:
        run = _run(server_id, cmd, timeout=timeout)
        last = run
        if run.get("exit_status") == 0:
            return run
    return last


def list_services(server_id: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for name in COMMON_SERVICES:
        active = _run(server_id, f"systemctl is-active {name} || true")
        enabled = _run(server_id, f"systemctl is-enabled {name} || true")
        status = (active.get("stdout") or "unknown").strip().splitlines()[:1]
        enabled_state = (enabled.get("stdout") or "unknown").strip().splitlines()[:1]
        rows.append(
            {
                "service_name": name,
                "status": status[0] if status else "unknown",
                "autostart": enabled_state[0] if enabled_state else "unknown",
                "health": "healthy" if (status and status[0] == "active") else "unhealthy",
            }
        )
    return rows


def control_service(server_id: int, service_name: str, action: str) -> Dict[str, Any]:
    if action not in {"start", "stop", "restart"}:
        return {"ok": False, "message": "invalid action"}

    names = [service_name]
    if service_name == "ssh":
        names.extend(["sshd", "ssh"])

    commands = []
    for name in names:
        commands.extend([
            f"systemctl {action} {name}",
            f"sudo -n systemctl {action} {name}",
            f"service {name} {action}",
        ])

    run = _try_commands(server_id, commands)
    ok = run.get("exit_status") == 0
    return {
        "ok": ok,
        "message": "ok" if ok else (run.get("stderr") or run.get("stdout") or "failed"),
        "result": run,
    }


def set_autostart(server_id: int, service_name: str, enabled: bool) -> Dict[str, Any]:
    action = "enable" if enabled else "disable"

    names = [service_name]
    if service_name == "ssh":
        names.extend(["sshd", "ssh"])

    commands = []
    for name in names:
        commands.extend([
            f"systemctl {action} {name}",
            f"sudo -n systemctl {action} {name}",
            f"chkconfig {name} {'on' if enabled else 'off'}",
        ])

    run = _try_commands(server_id, commands)
    ok = run.get("exit_status") == 0
    return {
        "ok": ok,
        "message": "ok" if ok else (run.get("stderr") or run.get("stdout") or "failed"),
        "result": run,
    }
