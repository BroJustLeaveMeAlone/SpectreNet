"""Subfinder wrapper — passive subdomain enumeration."""
from __future__ import annotations

import re
import shutil
from spectrenet.wrappers.base import ToolWrapper

_DOMAIN_RE = re.compile(r'^[a-z0-9][a-z0-9\-\.]*\.[a-z]{2,}$', re.IGNORECASE | re.MULTILINE)


class SubfinderWrapper(ToolWrapper):
    tool_name = "subfinder"

    def is_available(self) -> bool:
        return shutil.which("subfinder") is not None

    def run(self, domain: str, flags: str = "-silent") -> dict:
        """
        Run subfinder against a domain and return discovered subdomains.

        Args:
            domain: Root domain to enumerate (e.g. "example.com")
            flags:  Extra subfinder flags (default: -silent for clean output)
        """
        import subprocess
        args = ["subfinder", "-d", domain, "-silent"]
        if flags and flags != "-silent":
            args += flags.split()
        result = subprocess.run(args, capture_output=True, text=True, timeout=120)
        output = result.stdout + result.stderr
        subdomains = self._parse(output)
        return {
            "raw":        output,
            "domain":     domain,
            "subdomains": subdomains,
            "count":      len(subdomains),
        }

    def _parse(self, output: str) -> list[str]:
        found = []
        for line in output.splitlines():
            line = line.strip()
            if line and _DOMAIN_RE.match(line):
                found.append(line)
        return list(dict.fromkeys(found))  # deduplicate, preserve order

    @property
    def schema(self) -> dict:
        return {
            "domain":     "str  — root domain queried",
            "subdomains": "list[str]  — discovered subdomains",
            "count":      "int",
        }
