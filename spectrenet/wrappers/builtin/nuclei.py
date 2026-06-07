from __future__ import annotations
import re
import subprocess
from spectrenet.wrappers.base import ToolWrapper

_LINE_RE = re.compile(
    r"\[[\d\-: ]+\]\s+\[([^\]]+)\]\s+\[([^\]]+)\]\s+\[([^\]]+)\]\s+(\S+)"
)


class NucleiWrapper(ToolWrapper):
    tool_name = "nuclei"

    @property
    def schema(self) -> dict:
        return {"vulnerabilities": list}

    def parse(self, text: str) -> dict:
        vulns: list[dict] = []
        for line in text.splitlines():
            m = _LINE_RE.search(line)
            if m:
                template_id, proto, severity, url = m.groups()
                vulns.append({
                    "template_id": template_id,
                    "severity":    severity,
                    "type":        proto,
                    "url":         url,
                    "matched_at":  url,
                    "evidence":    line.strip(),
                })
        return {"vulnerabilities": vulns}

    def run(self, target: str = "", **kwargs) -> dict:
        templates = kwargs.get("templates", "cves,vulnerabilities")
        result = subprocess.run(
            ["nuclei", "-u", target, "-t", templates, "-silent"],
            capture_output=True, text=True, timeout=300,
        )
        return self.parse(result.stdout + result.stderr)
