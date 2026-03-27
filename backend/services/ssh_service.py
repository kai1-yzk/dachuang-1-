import io
import json
import os
import time
from typing import Any, Dict, List

import paramiko

from utils.crypto import decrypt_secret
from utils.db import execute_query


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _load_server_config(server_id: int) -> Dict[str, Any]:
    rows = execute_query(
        """
        SELECT id, hostname, ip, port, auth_type, auth_data, status
        FROM servers
        WHERE id = %s
        LIMIT 1
        """,
        (server_id,),
    )
    if not rows:
        raise ValueError("server not found")

    row = rows[0]
    auth_data = {}
    if row.get("auth_data"):
        try:
            auth_data = json.loads(row["auth_data"])
        except Exception:
            auth_data = {}

    return {
        "server_id": row["id"],
        "host": row["ip"],
        "port": int(row.get("port") or 22),
        "auth_type": (row.get("auth_type") or "password").lower(),
        "username": auth_data.get("ssh_username") or auth_data.get("username"),
        "password": decrypt_secret(auth_data.get("ssh_password") or auth_data.get("password")),
        "private_key": decrypt_secret(auth_data.get("private_key")),
        "private_key_passphrase": decrypt_secret(auth_data.get("private_key_passphrase")),
        "timeout": int(auth_data.get("connect_timeout") or os.environ.get("SSH_DEFAULT_TIMEOUT", "15")),
    }


def _connect(config: Dict[str, Any]) -> paramiko.SSHClient:
    if not config.get("username"):
        raise ValueError("server ssh username not configured")

    client = paramiko.SSHClient()
    strict_host_key = _bool_env("SSH_STRICT_HOST_KEY", default=False)
    if strict_host_key:
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    kwargs = {
        "hostname": config["host"],
        "port": config["port"],
        "username": config["username"],
        "timeout": config["timeout"],
        "banner_timeout": config["timeout"],
        "auth_timeout": config["timeout"],
        "look_for_keys": False,
        "allow_agent": False,
    }

    if config.get("auth_type") == "key":
        key_text = config.get("private_key")
        if not key_text:
            raise ValueError("private key not configured")

        pkey = None
        key_stream = io.StringIO(key_text)
        passphrase = config.get("private_key_passphrase") or None
        loaders = [
            paramiko.RSAKey.from_private_key,
            paramiko.Ed25519Key.from_private_key,
            paramiko.ECDSAKey.from_private_key,
        ]
        for loader in loaders:
            key_stream.seek(0)
            try:
                pkey = loader(key_stream, password=passphrase)
                break
            except Exception:
                continue

        if not pkey:
            raise ValueError("invalid private key")
        kwargs["pkey"] = pkey
    else:
        password = config.get("password")
        if not password:
            raise ValueError("server ssh password not configured")
        kwargs["password"] = password

    client.connect(**kwargs)
    return client


def validate_server_ssh_config(server_id: int) -> Dict[str, Any]:
    config = _load_server_config(server_id)
    if not config.get("host"):
        return {"ok": False, "message": "server host not configured"}
    if not config.get("username"):
        return {"ok": False, "message": "ssh username missing"}

    if config.get("auth_type") == "key" and not config.get("private_key"):
        return {"ok": False, "message": "private key missing"}

    if config.get("auth_type") != "key" and not config.get("password"):
        return {"ok": False, "message": "ssh password missing"}

    return {"ok": True, "config": config}


def run_command_stream(server_id: int, command: str, timeout: int = 20) -> Dict[str, Any]:
    config = _load_server_config(server_id)
    client = _connect(config)
    chunks: List[Dict[str, str]] = []
    try:
        _, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
        channel = stdout.channel

        start = time.time()
        while True:
            if channel.recv_ready():
                data = channel.recv(4096)
                if data:
                    chunks.append({"stream": "stdout", "text": data.decode("utf-8", errors="replace")})

            if channel.recv_stderr_ready():
                data = channel.recv_stderr(4096)
                if data:
                    chunks.append({"stream": "stderr", "text": data.decode("utf-8", errors="replace")})

            if channel.exit_status_ready() and (not channel.recv_ready()) and (not channel.recv_stderr_ready()):
                break

            if time.time() - start > timeout:
                raise TimeoutError("ssh command timeout")

            time.sleep(0.03)

        exit_status = channel.recv_exit_status()
        return {"ok": True, "exit_status": exit_status, "chunks": chunks}
    finally:
        client.close()
