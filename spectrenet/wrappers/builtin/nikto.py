from __future__ import annotations
import re
import subprocess
from spectrenet.wrappers.base import ToolWrapper

_FINDING_RE = re.compile(r"\+\s+(OSVDB-\d+|CVE-[\d-]+):\s+(.+)")
_TARGET_RE   = re.compile(r"\+ Target IP:\s+(\S+)")


class NiktoWrapper(ToolWrapper):
    tool_name = "nikto"

    @property
    def schema(self) -> dict:
        return {"target": str, "findings": list}

    def parse(self, text: str) -> dict:
        target = ""
        m = _TARGET_RE.search(text)
        if m:
            target = m.group(1)
        findings: list[dict] = []
        for line in text.splitlines():
            fm = _FINDING_RE.search(line)
            if fm:
                findings.append({
                    "id":       fm.group(1),
                    "method":   "GET",
                    "url":      "",
                    "msg":      fm.group(2).strip(),
                    "severity": "LOW",
                })
        return {"target": target, "findings": findings}

    def run(self, target: str = "", **kwargs) -> dict:
        port = kwargs.get("port", 80)
        result = subprocess.run(
            ["nikto", "-h", target, "-p", str(port), "-nointeractive"],
            capture_output=True, text=True, timeout=300,
        )
        return self.parse(result.stdout + result.stderr)
