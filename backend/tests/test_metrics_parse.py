"""指标采集输出解析与布尔解析的单元测试。"""
import pytest

from services.server_metrics_service import _parse_metrics_text, _to_positive_int
from routes.services import _parse_enabled


class TestMetricsParse:
    def test_parse_normal_output(self):
        text = "CPU=12.34 MEM=45.67 DISK=78 NET=1024.50"
        parsed = _parse_metrics_text(text)
        assert parsed == {"cpu": 12.34, "memory": 45.67, "disk": 78.0, "network": 1024.5}

    def test_parse_with_surrounding_banner(self):
        text = "Welcome to Ubuntu\nCPU=1.00 MEM=2.00 DISK=3 NET=4.00\n"
        parsed = _parse_metrics_text(text)
        assert parsed is not None
        assert parsed["cpu"] == 1.0

    @pytest.mark.parametrize(
        "text",
        ["", "garbage output", "CPU=abc MEM=1 DISK=1 NET=1", "CPU=1 MEM=2 DISK=3"],
    )
    def test_parse_invalid_returns_none(self, text):
        assert _parse_metrics_text(text) is None

    def test_to_positive_int(self):
        assert _to_positive_int("5", 3) == 5
        assert _to_positive_int("0", 3) == 3
        assert _to_positive_int("-1", 3) == 3
        assert _to_positive_int("abc", 3) == 3
        assert _to_positive_int(None, 3) == 3


class TestParseEnabled:
    @pytest.mark.parametrize("value", [True, "true", "TRUE", "1", "yes", "on", 1])
    def test_true_values(self, value):
        ok, result = _parse_enabled(value)
        assert ok is True and result is True

    @pytest.mark.parametrize("value", [False, "false", "FALSE", "0", "no", "off", 0])
    def test_false_values(self, value):
        # 关键回归：字符串 "false" 不能被 bool() 当成 True
        ok, result = _parse_enabled(value)
        assert ok is True and result is False

    @pytest.mark.parametrize("value", ["maybe", 2, None, object()])
    def test_invalid_values(self, value):
        ok, result = _parse_enabled(value)
        assert ok is False and result is None
