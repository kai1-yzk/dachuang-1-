import re
from typing import Any, Dict, List, Tuple

from services.ssh_service import run_command_stream

COMMON_SERVICES = ["nginx", "mysql", "redis", "docker", "ssh", "cron"]

SERVICE_ALIASES = {
    "mysql": ["mysql", "mysqld", "mariadb"],
    "redis": ["redis", "redis-server"],
    "ssh": ["ssh", "sshd"],
    "cron": ["cron", "crond"],
    "docker": ["docker", "docker.service"],
}


def _safe_tail(text: str, limit: int = 2000) -> str:
    return (text or "")[-limit:]


def _combined_output(run: Dict[str, Any]) -> str:
    return f"{run.get('stdout', '')}\n{run.get('stderr', '')}".strip()


def _is_not_found_text(text: str) -> bool:
    lowered = (text or "").lower()
    patterns = [
        "could not be found",
        "not found",
        "unrecognized service",
        "unknown service",
        "does not exist",
        "failed to find",
        "no such file or directory",
    ]
    return any(p in lowered for p in patterns)


def _is_permission_denied(text: str) -> bool:
    lowered = (text or "").lower()
    patterns = [
        "permission denied",
        "access denied",
        "authentication is required",
        "sudo:",
        "polkit",
        "not in the sudoers",
    ]
    return any(p in lowered for p in patterns)


def _run(server_id: int, command: str, timeout: int = 20) -> Dict[str, Any]:
    result = run_command_stream(server_id, command, timeout=timeout)
    stdout = "".join(chunk.get("text", "") for chunk in result.get("chunks", []) if chunk.get("stream") == "stdout")
    stderr = "".join(chunk.get("text", "") for chunk in result.get("chunks", []) if chunk.get("stream") == "stderr")
    return {
        "exit_status": int(result.get("exit_status") or 0),
        "stdout": _safe_tail(stdout),
        "stderr": _safe_tail(stderr),
    }


def _command_exists(server_id: int, cmd: str) -> bool:
    run = _run(server_id, f"command -v {cmd} >/dev/null 2>&1", timeout=10)
    return run.get("exit_status") == 0


def _try_commands(server_id: int, commands: List[str], timeout: int = 20) -> Dict[str, Any]:
    last = {"exit_status": 1, "stdout": "", "stderr": "no command executed"}
    errors: List[str] = []
    for cmd in commands:
        run = _run(server_id, cmd, timeout=timeout)
        last = run
        if run.get("exit_status") == 0:
            if errors:
                run["stderr"] = "\n".join(errors[-3:])
            return run
        err = (run.get("stderr") or run.get("stdout") or "").strip()
        if err:
            errors.append(err)
    if errors:
        last["stderr"] = "\n".join(errors[-5:])
    return last


def _probe_service_exists(server_id: int, service_name: str) -> Tuple[bool, str, str]:
    """Return (exists, resolved_name, probe_message)."""
    candidates = _service_candidates(service_name)
    if not candidates:
        return False, service_name, "invalid service name"
    has_systemctl = _command_exists(server_id, "systemctl")
    has_service = _command_exists(server_id, "service")
    has_rc_service = _command_exists(server_id, "rc-service")
    has_any_manager = has_systemctl or has_service or has_rc_service

    for name in candidates:
        if has_systemctl:
            run = _run(
                server_id,
                f"systemctl show '{name}' --property=LoadState --value 2>/dev/null || true",
                timeout=12,
            )
            load_state = (run.get("stdout") or "").strip().splitlines()
            load_state_value = load_state[-1].strip() if load_state else ""
            if load_state_value and load_state_value != "not-found":
                return True, name, "service found by systemctl"

        if has_service:
            run = _run(server_id, f"service '{name}' status 2>&1 || true", timeout=12)
            text = _combined_output(run)
            if text and not _is_not_found_text(text) and not _is_permission_denied(text):
                return True, name, "service found by service command"

        init_check = _run(server_id, f"[ -x '/etc/init.d/{name}' ] && echo FOUND || true", timeout=10)
        if "FOUND" in (init_check.get("stdout") or ""):
            return True, name, "service found by init.d"

        if has_rc_service:
            run = _run(server_id, f"rc-service '{name}' status 2>&1 || true", timeout=12)
            text = _combined_output(run)
            if text and not _is_not_found_text(text) and not _is_permission_denied(text):
                return True, name, "service found by rc-service"

    if not has_any_manager:
        return False, candidates[0] if candidates else service_name, "no service manager available on target host"
    return False, candidates[0] if candidates else service_name, f"service '{service_name}' not found"


def _service_candidates(name: str) -> List[str]:
    base = (name or "").strip()
    if not base:
        return []
    if not re.match(r"^[a-zA-Z0-9_.-]+$", base):
        return []

    allowset = set(COMMON_SERVICES)
    for values in SERVICE_ALIASES.values():
        allowset.update(values)
    allowset.update(SERVICE_ALIASES.keys())
    if base not in allowset:
        return []

    aliases = SERVICE_ALIASES.get(base, [base])
    seen = set()
    result: List[str] = []
    for item in aliases:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _build_batch_status_command() -> str:
    lines = [
        "set +e",
    ]
    for base in COMMON_SERVICES:
        candidates = " ".join(_service_candidates(base))
        lines.extend([
            f"svc_base='{base}'",
            "svc_status='inactive'",
            "svc_autostart='disabled'",
            f"for svc_name in {candidates}; do",
            "  if command -v systemctl >/dev/null 2>&1; then",
            "    systemctl is-active \"$svc_name\" >/dev/null 2>&1 && svc_status='active'",
            "    systemctl is-enabled \"$svc_name\" >/dev/null 2>&1 && svc_autostart='enabled'",
            "  fi",
            "  if [ \"$svc_status\" != 'active' ] && command -v service >/dev/null 2>&1; then",
            "    service \"$svc_name\" status 2>/dev/null | grep -Eiq 'running|start/running|active (running)' && svc_status='active'",
            "  fi",
            "  if [ \"$svc_status\" != 'active' ] && command -v rc-service >/dev/null 2>&1; then",
            "    rc-service \"$svc_name\" status 2>/dev/null | grep -Eiq 'started|running' && svc_status='active'",
            "  fi",
            "  if [ \"$svc_autostart\" != 'enabled' ] && command -v chkconfig >/dev/null 2>&1; then",
            "    chkconfig --list \"$svc_name\" 2>/dev/null | grep -qi ':on' && svc_autostart='enabled'",
            "  fi",
            "  if [ \"$svc_autostart\" != 'enabled' ] && command -v rc-update >/dev/null 2>&1; then",
            "    rc-update show 2>/dev/null | grep -Eq '^[[:space:]]*'\"$svc_name\"'[[:space:]]' && svc_autostart='enabled'",
            "  fi",
            "done",
            "echo __AIOPS_SVC__${svc_base}|${svc_status}|${svc_autostart}",
        ])
    return " ; ".join(lines)


def _batch_service_snapshot(server_id: int) -> Dict[str, Dict[str, str]]:
    run = _run(server_id, _build_batch_status_command(), timeout=30)
    snapshot: Dict[str, Dict[str, str]] = {}
    for ln in (run.get("stdout") or "").splitlines():
        line = (ln or "").strip()
        if not line.startswith("__AIOPS_SVC__"):
            continue
        raw = line.replace("__AIOPS_SVC__", "", 1)
        parts = raw.split("|")
        if len(parts) != 3:
            continue
        name, status, autostart = parts
        snapshot[name] = {
            "status": status or "inactive",
            "autostart": autostart or "disabled",
        }
    return snapshot


def list_services(server_id: int) -> List[Dict[str, Any]]:
    snapshot = _batch_service_snapshot(server_id)
    rows: List[Dict[str, Any]] = []
    for name in COMMON_SERVICES:
        status = (snapshot.get(name) or {}).get("status", "inactive")
        autostart = (snapshot.get(name) or {}).get("autostart", "disabled")
        rows.append(
            {
                "service_name": name,
                "status": status,
                "autostart": autostart,
                "health": "healthy" if status == "active" else "unhealthy",
            }
        )
    return rows


def control_service(server_id: int, service_name: str, action: str) -> Dict[str, Any]:
    if action not in {"start", "stop", "restart"}:
        return {"ok": False, "error_type": "invalid_argument", "message": "invalid action"}

    if not _service_candidates(service_name):
        return {"ok": False, "error_type": "invalid_argument", "message": "invalid or unsupported service_name"}

    exists, resolved_name, probe_msg = _probe_service_exists(server_id, service_name)
    if not exists:
        if "no service manager available" in probe_msg:
            return {"ok": False, "error_type": "manager_unavailable", "message": probe_msg}
        return {"ok": False, "error_type": "not_found", "message": probe_msg}

    names = _service_candidates(resolved_name)

    commands = []
    for name in names:
        commands.extend([
            f"systemctl {action} {name}",
            f"sudo -n systemctl {action} {name}",
            f"service {name} {action}",
            f"sudo -n service {name} {action}",
            f"/etc/init.d/{name} {action}",
            f"sudo -n /etc/init.d/{name} {action}",
            f"command -v rc-service >/dev/null 2>&1 && rc-service {name} {action}",
            f"command -v rc-service >/dev/null 2>&1 && sudo -n rc-service {name} {action}",
        ])

    run = _try_commands(server_id, commands)
    message = run.get("stderr") or run.get("stdout") or "failed, check sudo/service manager availability"
    ok = run.get("exit_status") == 0
    if not ok and _is_permission_denied(message):
        return {"ok": False, "error_type": "permission_denied", "message": message, "result": run}
    if not ok and _is_not_found_text(message):
        return {"ok": False, "error_type": "not_found", "message": message, "result": run}
    return {
        "ok": ok,
        "error_type": None if ok else "execution_failed",
        "message": "ok" if ok else message,
        "resolved_service_name": resolved_name,
        "probe": probe_msg,
        "result": run,
    }


def set_autostart(server_id: int, service_name: str, enabled: bool) -> Dict[str, Any]:
    action = "enable" if enabled else "disable"

    if not _service_candidates(service_name):
        return {"ok": False, "error_type": "invalid_argument", "message": "invalid or unsupported service_name"}

    exists, resolved_name, probe_msg = _probe_service_exists(server_id, service_name)
    if not exists:
        if "no service manager available" in probe_msg:
            return {"ok": False, "error_type": "manager_unavailable", "message": probe_msg}
        return {"ok": False, "error_type": "not_found", "message": probe_msg}

    names = _service_candidates(resolved_name)

    commands = []
    for name in names:
        commands.extend([
            f"systemctl {action} {name}",
            f"sudo -n systemctl {action} {name}",
            f"chkconfig {name} {'on' if enabled else 'off'}",
            f"sudo -n chkconfig {name} {'on' if enabled else 'off'}",
            f"command -v rc-update >/dev/null 2>&1 && rc-update {'add' if enabled else 'del'} {name} default",
            f"command -v rc-update >/dev/null 2>&1 && sudo -n rc-update {'add' if enabled else 'del'} {name} default",
        ])

    run = _try_commands(server_id, commands)
    message = run.get("stderr") or run.get("stdout") or "failed, check sudo/service manager availability"
    ok = run.get("exit_status") == 0
    if not ok and _is_permission_denied(message):
        return {"ok": False, "error_type": "permission_denied", "message": message, "result": run}
    if not ok and _is_not_found_text(message):
        return {"ok": False, "error_type": "not_found", "message": message, "result": run}
    return {
        "ok": ok,
        "error_type": None if ok else "execution_failed",
        "message": "ok" if ok else message,
        "resolved_service_name": resolved_name,
        "probe": probe_msg,
        "result": run,
    }
