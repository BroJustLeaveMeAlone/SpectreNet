import pytest
from spectrenet.ai.report_writer import ReportWriter


class ScriptedModel:
    def __init__(self, responses: list[str]):
        self._it = iter(responses)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        try:
            return next(self._it)
        except StopIteration:
            return ""


class FakeSessionStore:
    def actions_for(self, session_id: int) -> list[dict]:
        return [
            {"id": 1, "action_type": "recon",   "tool": "nmap",
             "target": "10.10.10.5", "ts": "2026-06-07T10:00:00"},
            {"id": 2, "action_type": "exploit",  "tool": "ms17_010_eternalblue",
             "target": "10.10.10.5", "ts": "2026-06-07T10:01:00"},
        ]

    def approvals_for(self, session_id: int) -> list[dict]:
        return [
            {"action_id": 2, "result": "Y", "ts": "2026-06-07T10:00:55"},
        ]


FINDINGS = [
    {"type": "open_port",    "ip": "10.10.10.5", "port": 445, "service": "microsoft-ds",
     "version": "Samba 4.6", "severity": "INFO",     "detail": "SMB open"},
    {"type": "vulnerability","ip": "10.10.10.5", "port": 445, "service": "smb",
     "version": "",           "severity": "CRITICAL",  "detail": "EternalBlue exploitable"},
]


def test_report_contains_executive_summary():
    model = ScriptedModel([
        "## Executive Summary\nThis engagement identified one critical vulnerability.",
        "## Recommendations\nPatch immediately.",
    ])
    report = ReportWriter(model).generate(FakeSessionStore(), session_id=1, findings=FINDINGS)
    assert "Executive Summary" in report


def test_report_contains_findings_section():
    model = ScriptedModel(["Summary here", "Recommendations here"])
    report = ReportWriter(model).generate(FakeSessionStore(), session_id=1, findings=FINDINGS)
    assert "Findings" in report


def test_report_contains_exploitation_timeline():
    model = ScriptedModel(["Summary", "Recs"])
    report = ReportWriter(model).generate(FakeSessionStore(), session_id=1, findings=FINDINGS)
    assert "Timeline" in report or "nmap" in report


def test_report_groups_findings_by_severity():
    model = ScriptedModel(["Summary", "Recs"])
    report = ReportWriter(model).generate(FakeSessionStore(), session_id=1, findings=FINDINGS)
    assert "CRITICAL" in report


def test_report_with_empty_findings_still_returns_markdown():
    model = ScriptedModel(["Summary", "Recs"])
    report = ReportWriter(model).generate(FakeSessionStore(), session_id=1, findings=[])
    assert isinstance(report, str)
    assert len(report) > 0
