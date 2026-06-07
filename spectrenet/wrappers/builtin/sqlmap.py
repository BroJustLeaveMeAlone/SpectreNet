from __future__ import annotations
import re
import subprocess
from spectrenet.wrappers.base import ToolWrapper


class SqlmapWrapper(ToolWrapper):
    tool_name = "sqlmap"

    @property
    def schema(self) -> dict:
        return {
            "injectable": bool,
            "payloads":   list,
            "databases":  list,
            "tables":     dict,
            "dump":       dict,
        }

    def parse(self, text: str) -> dict:
        injectable = "is vulnerable" in text or "injection point" in text
        payloads: list[str] = []
        for line in text.splitlines():
            m = re.match(r"\s+Type:\s+(.+)", line)
            if m:
                payloads.append(m.group(1).strip())
        databases: list[str] = []
        in_db_section = False
        for line in text.splitlines():
            if "available databases" in line:
                in_db_section = True
                continue
            if in_db_section:
                m = re.match(r"\[\*\]\s+(\S+)", line)
                if m:
                    databases.append(m.group(1))
                elif line.strip() and not line.startswith("["):
                    in_db_section = False
        return {
            "injectable": injectable,
            "payloads":   payloads,
            "databases":  databases,
            "tables":     {},
            "dump":       {},
        }

    def run(self, target: str = "", **kwargs) -> dict:
        extra = kwargs.get("extra_args", [])
        result = subprocess.run(
            ["sqlmap", "-u", target, "--batch", "--output-dir=/tmp/sqlmap_out"] + extra,
            capture_output=True, text=True, timeout=300,
        )
        return self.parse(result.stdout + result.stderr)
