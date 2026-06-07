import logging
import pytest
from spectrenet.engines.web_vuln import WebVulnEngine


class FakeRegistry:
    def __init__(self, wrappers: dict):
        self._wrappers = wrappers

    def available(self) -> list[str]:
        return list(self._wrappers.keys())

    def get(self, name: str):
        return self._wrappers[name]


class FakeWebWrapper:
    tool_name = "fakeweb"
    schema = {"vulnerabilities": list}

    def run(self, target: str = "", **kwargs) -> dict:
        return {"vulnerabilities": [{"severity": "HIGH", "type": "xss",
                                     "url": f"http://{target}/", "evidence": "test"}]}


def _engine():
    return WebVulnEngine(FakeRegistry({"fakeweb": FakeWebWrapper()}))


def test_scan_returns_vulnerabilities():
    result = _engine().scan(tool="fakeweb", target="10.10.10.5")
    assert "vulnerabilities" in result
    assert len(result["vulnerabilities"]) == 1


def test_scan_raises_for_unknown_tool():
    with pytest.raises(ValueError, match="not available"):
        _engine().scan(tool="nothere", target="10.10.10.5")


def test_scan_passes_kwargs_to_wrapper():
    calls: dict = {}

    class RecordingWrapper:
        tool_name = "recorder"
        schema = {}

        def run(self, target: str = "", **kwargs) -> dict:
            calls["kwargs"] = kwargs
            return {"vulnerabilities": []}

    engine = WebVulnEngine(FakeRegistry({"recorder": RecordingWrapper()}))
    engine.scan(tool="recorder", target="10.10.10.5", extra_args=["--level=3"])
    assert calls["kwargs"].get("extra_args") == ["--level=3"]


def test_scan_logs_finding_count(caplog):
    with caplog.at_level(logging.INFO):
        _engine().scan(tool="fakeweb", target="10.10.10.5")
    assert any("fakeweb" in r.message for r in caplog.records)
