import json

from flask import Blueprint, jsonify, request

from services.agent_service import list_servers
from services.ssh_service import run_command_stream, validate_server_ssh_config
from utils.crypto import encrypt_secret
from utils.db import execute_query, execute_update
from utils.security import ensure_role, get_request_tenant_id

servers_bp = Blueprint("servers", __name__)

_SERVERS_HAS_TENANT_ID = None


def _servers_has_tenant_id_column():
    global _SERVERS_HAS_TENANT_ID
    if _SERVERS_HAS_TENANT_ID is None:
        rows = execute_query("SHOW COLUMNS FROM servers LIKE %s", ("tenant_id",))
        _SERVERS_HAS_TENANT_ID = bool(rows)
    return _SERVERS_HAS_TENANT_ID


def _normalize_server_payload(payload):
    hostname = (payload.get("hostname") or "").strip()
    ip = (payload.get("ip") or "").strip()
    port = int(payload.get("port") or 22)
    auth_type = (payload.get("auth_type") or "password").lower()
    ssh_username = (payload.get("ssh_username") or "").strip()
    ssh_password = payload.get("ssh_password")
    private_key = payload.get("private_key")
    private_key_passphrase = payload.get("private_key_passphrase")
    connect_timeout = int(payload.get("connect_timeout") or 15)
    return {
        "hostname": hostname,
        "ip": ip,
        "port": port,
        "auth_type": auth_type,
        "ssh_username": ssh_username,
        "ssh_password": ssh_password,
        "private_key": private_key,
        "private_key_passphrase": private_key_passphrase,
        "connect_timeout": connect_timeout,
    }


def _validate_ssh_payload(data):
    if not data["ip"]:
        return "ip is required"
    if data["auth_type"] not in ("password", "key"):
        return "auth_type must be password or key"
    if not data["ssh_username"]:
        return "ssh_username is required"
    if data["auth_type"] == "password" and not data["ssh_password"]:
        return "ssh_password is required for password auth"
    if data["auth_type"] == "key" and not data["private_key"]:
        return "private_key is required for key auth"
    return None


def _admin_only_guard():
    return ensure_role(request, {"tenant_admin", "platform_admin", "superadmin"})


def _server_manage_guard():
    role = (getattr(request, "user", {}) or {}).get("role")
    if not role:
        return jsonify({"code": 403, "message": "Forbidden: role is required", "data": None}), 403
    return ensure_role(request, {"operator", "tenant_operator", "tenant_admin", "platform_admin", "superadmin"})


@servers_bp.route("/", methods=["GET"])
def list_all():
    tenant_id = get_request_tenant_id(request)
    if _servers_has_tenant_id_column():
        rows = execute_query(
            "SELECT id, hostname, ip, port, protocol, status, last_seen, created_at, updated_at FROM servers WHERE tenant_id=%s ORDER BY updated_at DESC",
            (tenant_id,),
        )
        return jsonify({"code": 200, "message": "ok", "data": rows})
    return jsonify({"code": 200, "message": "ok", "data": list_servers()})


@servers_bp.route("/", methods=["POST"])
def create_or_update_ssh_server():
    deny = _server_manage_guard()
    if deny:
        return deny

    tenant_id = get_request_tenant_id(request)
    payload = request.get_json(silent=True) or {}
    data = _normalize_server_payload(payload)
    error = _validate_ssh_payload(data)
    if error:
        return jsonify({"code": 400, "message": error, "data": None}), 400

    auth_data = {
        "ssh_username": data["ssh_username"],
        "ssh_password": encrypt_secret(data["ssh_password"]) if data["auth_type"] == "password" else None,
        "private_key": encrypt_secret(data["private_key"]) if data["auth_type"] == "key" else None,
        "private_key_passphrase": encrypt_secret(data["private_key_passphrase"]) if data["auth_type"] == "key" else None,
        "connect_timeout": data["connect_timeout"],
    }
    auth_data_json = json.dumps(auth_data, ensure_ascii=False)

    hostname = data["hostname"] or data["ip"]
    if _servers_has_tenant_id_column():
        existing = execute_query("SELECT id FROM servers WHERE ip=%s AND port=%s AND tenant_id=%s LIMIT 1", (data["ip"], data["port"], tenant_id))
    else:
        existing = execute_query("SELECT id FROM servers WHERE ip=%s AND port=%s LIMIT 1", (data["ip"], data["port"]))
    if existing:
        server_id = existing[0]["id"]
        execute_update(
            """
            UPDATE servers
            SET hostname=%s, protocol='ssh', auth_type=%s, auth_data=%s,
                ssh_username=%s, connect_timeout=%s, is_enabled=1, updated_at=NOW()
            WHERE id=%s
            """,
            (hostname, data["auth_type"], auth_data_json, data["ssh_username"], data["connect_timeout"], server_id),
        )
        message = "server updated"
    else:
        if _servers_has_tenant_id_column():
            execute_update(
                """
                INSERT INTO servers
                (tenant_id, hostname, ip, port, protocol, auth_type, auth_data, ssh_username, connect_timeout, is_enabled, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 'ssh', %s, %s, %s, %s, 1, 'offline', NOW(), NOW())
                """,
                (tenant_id, hostname, data["ip"], data["port"], data["auth_type"], auth_data_json, data["ssh_username"], data["connect_timeout"]),
            )
            created = execute_query("SELECT id FROM servers WHERE ip=%s AND port=%s AND tenant_id=%s ORDER BY id DESC LIMIT 1", (data["ip"], data["port"], tenant_id))
        else:
            execute_update(
                """
                INSERT INTO servers
                (hostname, ip, port, protocol, auth_type, auth_data, ssh_username, connect_timeout, is_enabled, status, created_at, updated_at)
                VALUES (%s, %s, %s, 'ssh', %s, %s, %s, %s, 1, 'offline', NOW(), NOW())
                """,
                (hostname, data["ip"], data["port"], data["auth_type"], auth_data_json, data["ssh_username"], data["connect_timeout"]),
            )
            created = execute_query("SELECT id FROM servers WHERE ip=%s AND port=%s ORDER BY id DESC LIMIT 1", (data["ip"], data["port"]))
        server_id = created[0]["id"] if created else None
        message = "server created"

    return jsonify(
        {
            "code": 200,
            "message": message,
            "data": {
                "server_id": server_id,
                "hostname": hostname,
                "ip": data["ip"],
                "port": data["port"],
                "auth_type": data["auth_type"],
                "ssh_username": data["ssh_username"],
            },
        }
    )


@servers_bp.route("/<int:server_id>", methods=["GET"])
def detail(server_id: int):
    tenant_id = get_request_tenant_id(request)
    if _servers_has_tenant_id_column():
        rows = execute_query(
            """
            SELECT s.id, s.hostname, s.ip, s.port, s.protocol, s.status, s.last_seen,
                   m.cpu_usage, m.memory_usage, m.disk_usage, m.network_rx_mb, m.network_tx_mb, m.created_at
            FROM servers s
            LEFT JOIN server_metrics m ON m.server_id = s.id
            WHERE s.id = %s AND s.tenant_id=%s
            ORDER BY m.id DESC
            LIMIT 30
            """,
            (server_id, tenant_id),
        )
    else:
        rows = execute_query(
            """
            SELECT s.id, s.hostname, s.ip, s.port, s.protocol, s.status, s.last_seen,
                   m.cpu_usage, m.memory_usage, m.disk_usage, m.network_rx_mb, m.network_tx_mb, m.created_at
            FROM servers s
            LEFT JOIN server_metrics m ON m.server_id = s.id
            WHERE s.id = %s
            ORDER BY m.id DESC
            LIMIT 30
            """,
            (server_id,),
        )
    if not rows:
        return jsonify({"code": 404, "message": "server not found", "data": None}), 404
    return jsonify({"code": 200, "message": "ok", "data": rows})


@servers_bp.route("/<int:server_id>/ssh-config", methods=["PUT"])
def update_ssh_config(server_id: int):
    deny = _server_manage_guard()
    if deny:
        return deny

    tenant_id = get_request_tenant_id(request)
    payload = request.get_json(silent=True) or {}
    auth_type = (payload.get("auth_type") or "password").lower()
    ssh_username = (payload.get("ssh_username") or "").strip()
    ssh_password = payload.get("ssh_password")
    private_key = payload.get("private_key")
    private_key_passphrase = payload.get("private_key_passphrase")
    connect_timeout = int(payload.get("connect_timeout") or 15)

    if auth_type not in ("password", "key"):
        return jsonify({"code": 400, "message": "auth_type must be password or key", "data": None}), 400
    if not ssh_username:
        return jsonify({"code": 400, "message": "ssh_username is required", "data": None}), 400
    if auth_type == "password" and not ssh_password:
        return jsonify({"code": 400, "message": "ssh_password is required for password auth", "data": None}), 400
    if auth_type == "key" and not private_key:
        return jsonify({"code": 400, "message": "private_key is required for key auth", "data": None}), 400

    if _servers_has_tenant_id_column():
        server = execute_query("SELECT id FROM servers WHERE id=%s AND tenant_id=%s LIMIT 1", (server_id, tenant_id))
    else:
        server = execute_query("SELECT id FROM servers WHERE id=%s LIMIT 1", (server_id,))
    if not server:
        return jsonify({"code": 404, "message": "server not found", "data": None}), 404

    auth_data = {
        "ssh_username": ssh_username,
        "ssh_password": encrypt_secret(ssh_password) if auth_type == "password" else None,
        "private_key": encrypt_secret(private_key) if auth_type == "key" else None,
        "private_key_passphrase": encrypt_secret(private_key_passphrase) if auth_type == "key" else None,
        "connect_timeout": connect_timeout,
    }

    execute_query_res = execute_query("SELECT auth_data FROM servers WHERE id=%s LIMIT 1", (server_id,))
    if execute_query_res and execute_query_res[0].get("auth_data"):
        try:
            existing = json.loads(execute_query_res[0]["auth_data"])
            for key, value in existing.items():
                if key not in auth_data:
                    auth_data[key] = value
        except Exception:
            pass

    auth_data_json = json.dumps(auth_data, ensure_ascii=False)
    execute_update(
        """
        UPDATE servers
        SET auth_type=%s, auth_data=%s, updated_at=NOW()
        WHERE id=%s
        """,
        (auth_type, auth_data_json, server_id),
    )

    return jsonify(
        {
            "code": 200,
            "message": "ssh config updated",
            "data": {
                "server_id": server_id,
                "auth_type": auth_type,
                "ssh_username": ssh_username,
                "connect_timeout": connect_timeout,
            },
        }
    )


@servers_bp.route("/<int:server_id>/ssh-test", methods=["POST"])
def test_ssh_connection(server_id: int):
    deny = _server_manage_guard()
    if deny:
        return deny

    tenant_id = get_request_tenant_id(request)
    if _servers_has_tenant_id_column():
        owns = execute_query("SELECT id FROM servers WHERE id=%s AND tenant_id=%s LIMIT 1", (server_id, tenant_id))
        if not owns:
            return jsonify({"code": 404, "message": "server not found", "data": None}), 404
    check = validate_server_ssh_config(server_id)
    if not check.get("ok"):
        return jsonify({"code": 400, "message": check.get("message", "invalid ssh config"), "data": None}), 400

    try:
        result = run_command_stream(server_id, "echo __AIOPS_SSH_OK__", timeout=10)
        output = "".join(chunk.get("text", "") for chunk in result.get("chunks", []))
        ok = "__AIOPS_SSH_OK__" in output and int(result.get("exit_status", 1)) == 0
        if not ok:
            return jsonify({"code": 500, "message": "ssh connected but test command failed", "data": result}), 500
        return jsonify({"code": 200, "message": "ssh connection success", "data": {"server_id": server_id}})
    except Exception as e:
        return jsonify({"code": 500, "message": f"ssh connection failed: {str(e)}", "data": None}), 500


@servers_bp.route("/<int:server_id>", methods=["DELETE"])
def delete_server(server_id: int):
    deny = _admin_only_guard()
    if deny:
        return deny

    payload = request.get_json(silent=True) or {}
    confirm = bool(payload.get("confirm", False))
    if not confirm:
        return jsonify({"code": 400, "message": "confirm=true is required", "data": None}), 400

    tenant_id = get_request_tenant_id(request)
    if _servers_has_tenant_id_column():
        exists = execute_query("SELECT id FROM servers WHERE id=%s AND tenant_id=%s LIMIT 1", (server_id, tenant_id))
    else:
        exists = execute_query("SELECT id FROM servers WHERE id=%s LIMIT 1", (server_id,))
    if not exists:
        return jsonify({"code": 404, "message": "server not found", "data": None}), 404

    execute_update("DELETE FROM servers WHERE id=%s", (server_id,))
    return jsonify({"code": 200, "message": "server deleted", "data": {"server_id": server_id}})
