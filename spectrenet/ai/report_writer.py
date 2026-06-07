from __future__ import annotations
from datetime import datetime
from typing import Any

_SUMMARY_SYSTEM = (
    "You are a professional penetration tester writing an engagement report. "
    "Given a list of findings and an action summary, write the Executive Summary "
    "and Scope & Methodology sections in clear, professional Markdown. "
    "Be concise. Use ## headings. Do not use code blocks."
)

_RECS_SYSTEM = (
    "You are a professional penetration tester. Given a list of findings by severity, "
    "write a Recommendations section in Markdown. Each recommendation should map to a "
    "specific finding type. Use ## Recommendations as the heading."
)


class ReportWriter:
    def __init__(self, model: Any) -> None:
        self._model = model

    def generate(self, session_store: Any, session_id: int,
                 findings: list[dict] | None = None) -> str:
        findings = findings or []
        actions = session_store.actions_for(session_id)
        approvals = session_store.approvals_for(session_id)

        by_severity: dict[str, list[dict]] = {}
        for f in findings:
            sev = f.get("severity", "INFO")
            by_severity.setdefault(sev, []).append(f)

        finding_summary = (
            f"{len(findings)} total findings: "
            + ", ".join(f"{len(v)} {k}" for k, v in sorted(by_severity.items()))
        ) if findings else "No findings recorded."

        summary_prompt = (
            f"Engagement scope: session {session_id}\n"
            f"Actions performed: {len(actions)}\n"
            f"Approvals granted: {len([a for a in approvals if a.get('result') == 'Y'])}\n"
            f"Findings: {finding_summary}\n"
        )
        summary_section = self._safe_complete(_SUMMARY_SYSTEM, summary_prompt)

        recs_prompt = "\n".join(
            f"- [{f['severity']}] {f['detail']}" for f in findings
        ) or "No findings."
        recs_section = self._safe_complete(_RECS_SYSTEM, recs_prompt)

        timeline = self._build_timeline(actions, approvals)
        findings_section = self._build_findings_section(by_severity)
        action_log = self._build_action_log(actions)

        return "\n\n".join([
            "# SpectreNet Engagement Report",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            summary_section,
            findings_section,
            "## Exploitation Timeline",
            timeline,
            recs_section,
            "## Appendix — Full Action Log",
            action_log,
        ])

    def _safe_complete(self, system: str, user: str) -> str:
        try:
            return self._model.complete(system, user) or ""
        except Exception:
            return ""

    def _build_findings_section(self, by_severity: dict[str, list[dict]]) -> str:
        lines = ["## Findings"]
        order = ["CRITICAL", "HIGH", "MED", "LOW", "INFO"]
        for sev in order:
            items = by_severity.get(sev, [])
            if not items:
                continue
            lines.append(f"\n### {sev}")
            for f in items:
                lines.append(
                    f"- **{f.get('service', '')}** on {f.get('ip', '')}:{f.get('port', '')} "
                    f"— {f.get('detail', '')}"
                )
        if not any(by_severity.get(s) for s in order):
            lines.append("No findings recorded.")
        return "\n".join(lines)

    def _build_timeline(self, actions: list[dict], approvals: list[dict]) -> str:
        approval_map = {a.get("action_id", a.get("id")): a.get("result") for a in approvals}
        lines = []
        for a in actions:
            ts = a.get("ts", a.get("timestamp", ""))
            decision = approval_map.get(a.get("id"))
            dec_str = f" [{decision}]" if decision else ""
            lines.append(
                f"- `{ts}` **{a.get('action_type', a.get('tool', ''))}** "
                f"{a.get('tool', '')} → {a.get('target', a.get('params', ''))}{dec_str}"
            )
        return "\n".join(lines) if lines else "*No actions recorded.*"

    def _build_action_log(self, actions: list[dict]) -> str:
        lines = ["| # | Type | Tool | Target |",
                 "|---|---|---|---|"]
        for a in actions:
            lines.append(
                f"| {a.get('id', '')} | {a.get('action_type', '')} "
                f"| {a.get('tool', '')} | {a.get('target', a.get('params', ''))} |"
            )
        return "\n".join(lines)
