"""run_command_stream 的 pty 行为回归测试。

背景：默认 get_pty=True 时，`systemctl restart xxx` 之类命令不会关闭通道，
读取循环会一直跑到 timeout（实测 12s+），导致服务启停接口 500。
"""
from unittest.mock import MagicMock, patch

import services.ssh_service as ssh_service


def _fake_client(exit_status=0, out=b"ok\n"):
    client = MagicMock()
    _, stdout, stderr = MagicMock(), MagicMock(), MagicMock()
    channel = MagicMock()
    channel.recv_ready.side_effect = [True, False, False]
    channel.recv_stderr_ready.return_value = False
    channel.exit_status_ready.return_value = True
    channel.recv.return_value = out
    channel.recv_exit_status.return_value = exit_status
    stdout.channel = channel
    client.exec_command.return_value = (None, stdout, stderr)
    return client


@patch.object(ssh_service, "_connect")
@patch.object(ssh_service, "_load_server_config")
def test_pty_disabled_by_default(mock_cfg, mock_connect):
    mock_cfg.return_value = {"auth_type": "password", "password": "x"}
    fake = _fake_client()
    mock_connect.return_value = fake

    ssh_service.run_command_stream(1, "systemctl restart syslog", timeout=5)

    # 关键断言：默认不分配 pty
    _, kwargs = fake.exec_command.call_args
    assert kwargs.get("get_pty") is False


@patch.object(ssh_service, "_connect")
@patch.object(ssh_service, "_load_server_config")
def test_pty_can_be_enabled_explicitly(mock_cfg, mock_connect):
    mock_cfg.return_value = {"auth_type": "password", "password": "x"}
    fake = _fake_client()
    mock_connect.return_value = fake

    ssh_service.run_command_stream(1, "bash", timeout=5, use_pty=True)

    _, kwargs = fake.exec_command.call_args
    assert kwargs.get("get_pty") is True


@patch.object(ssh_service, "_connect")
@patch.object(ssh_service, "_load_server_config")
def test_stdout_collected(mock_cfg, mock_connect):
    mock_cfg.return_value = {"auth_type": "password", "password": "x"}
    fake = _fake_client(exit_status=0, out=b"Filesystem\n")
    mock_connect.return_value = fake

    result = ssh_service.run_command_stream(1, "df -h", timeout=5)

    assert result["ok"] is True
    assert result["exit_status"] == 0
    assert any("Filesystem" in c["text"] for c in result["chunks"])
