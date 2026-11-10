"""MFA 短码时区回归测试。

背景：expires_at 用 datetime.utcnow() 写入，但校验时与 MySQL NOW()
（会话时区时间）比较，两者相差 8 小时，导致写入即过期，
短码永远校验失败，MFA 功能实际不可用。
"""
import datetime
from unittest.mock import patch

from routes import ws_terminal


class TestMfaExpiryUsesLocalTime:
    def test_ws_terminal_expiry_is_local_time(self):
        """写入的 expires_at 必须与 datetime.now() 同基准。"""
        captured = {}

        def fake_update(sql, args):
            captured["expires_at"] = args[4]
            return 1

        with patch.object(ws_terminal, "execute_update", side_effect=fake_update):
            before = datetime.datetime.now()
            ws_terminal._request_short_code(1, "sess-1", "rm -rf /tmp/x")
            after = datetime.datetime.now()

        expires = captured["expires_at"]
        delta = (expires - before).total_seconds()
        # 应在 5 分钟左右，且绝不为负（utcnow 会得到 -8h 左右的负差值）
        assert 240 <= delta <= 320, f"expires_at 与本地时间不符，差值 {delta}s"
        assert expires <= after + datetime.timedelta(minutes=6)

    def test_ws_terminal_expiry_not_in_past(self):
        """关键回归：写入的过期时间不得早于当前本地时间。"""
        captured = {}

        def fake_update(sql, args):
            captured["expires_at"] = args[4]
            return 1

        with patch.object(ws_terminal, "execute_update", side_effect=fake_update):
            ws_terminal._request_short_code(1, "sess-2", "cmd")

        assert captured["expires_at"] > datetime.datetime.now(), (
            "过期时间早于当前时间，短码会立即失效"
        )
