"""Shodan CLI wrapper — host lookup and search via the shodan CLI tool."""
from __future__ import annotations

import json
import re
import shutil
from spectrenet.wrappers.base import ToolWrapper

_PORT_RE     = re.compile(r"Ports:\s+(.+)")
_COUNTRY_RE  = re.compile(r"Country:\s+(.+)")
_ORG_RE      = re.compile(r"Organization:\s+(.+)")
_OS_RE       = re.compile(r"Operating System:\s+(.+)")
_HOSTNAME_RE = re.compile(r"Hostnames:\s+(.+)")
_VULN_RE     = re.compile(r"Vulnerabilities:\s+(.+)")


class ShodanWrapper(ToolWrapper):
    tool_name = "shodan"

    def is_available(self) -> bool:
        return shutil.which("shodan") is not None

    def run(self, target: str, flags: str = "") -> dict:
        """
        Run 'shodan host <target>' and return structured output.

        For unauthenticated searches, 'shodan search <query>' is also supported
        by passing flags='search' and target=<query string>.
        """
        import subprocess
        if flags == "search":
            args = ["shodan", "search", "--fields", "ip_str,port,org,hostnames", target]
        else:
            args = ["shodan", "host", target]
            if flags:
                args += flags.split()
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        return {
            "raw":       output,
            "ip":        target,
            "ports":     self._parse_ports(output),
            "country":   self._match(output, _COUNTRY_RE),
            "org":       self._match(output, _ORG_RE),
            "os":        self._match(output, _OS_RE),
            "hostnames": self._parse_list(output, _HOSTNAME_RE),
            "vulns":     self._parse_list(output, _VULN_RE),
        }

    def _match(self, text: str, pattern: re.Pattern) -> str:
        m = pattern.search(text)
        return m.group(1).strip() if m else ""

    def _parse_ports(self, text: str) -> list[int]:
        m = _PORT_RE.search(text)
        if not m:
            return []
        parts = re.split(r"[,\s]+", m.group(1).strip())
        ports = []
        for p in parts:
            p = p.strip()
            if p.isdigit():
                ports.append(int(p))
        return ports

    def _parse_list(self, text: str, pattern: re.Pattern) -> list[str]:
        m = pattern.search(text)
        if not m:
            return []
        return [x.strip() for x in re.split(r"[,\s]+", m.group(1).strip()) if x.strip()]

    @property
    def schema(self) -> dict:
        return {
            "ip":        "str",
            "ports":     "list[int]",
            "country":   "str",
            "org":       "str",
            "os":        "str",
            "hostnames": "list[str]",
            "vulns":     "list[str]  — CVE IDs reported by Shodan",
        }
