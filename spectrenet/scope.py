"""Scope enforcement — check targets against configured CIDR ranges."""
from __future__ import annotations

import ipaddress
import re

_IP_RE = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d+)?\b')


class ScopeEnforcer:
    """
    Checks tool arguments against a list of allowed CIDR ranges.

    If no ranges are configured, every target is considered in-scope.
    strict=True blocks execution; strict=False warns but allows.
    """

    def __init__(self, ranges: list[str] | None = None, strict: bool = False) -> None:
        self._strict   = strict
        self._networks: list[ipaddress.IPv4Network] = []
        for r in (ranges or []):
            try:
                self._networks.append(ipaddress.IPv4Network(r, strict=False))
            except ValueError:
                pass

    @property
    def active(self) -> bool:
        return len(self._networks) > 0

    def add(self, cidr: str) -> bool:
        try:
            self._networks.append(ipaddress.IPv4Network(cidr, strict=False))
            return True
        except ValueError:
            return False

    def in_scope(self, target: str) -> bool:
        if not self._networks:
            return True
        try:
            addr = ipaddress.IPv4Address(target.split("/")[0])
            return any(addr in net for net in self._networks)
        except ValueError:
            return True  # hostnames pass through unchecked

    def check_args(self, args: list[str]) -> tuple[bool, list[str]]:
        """Extract IPs from args and return (all_in_scope, out_of_scope_list)."""
        if not self._networks:
            return True, []
        raw  = " ".join(args)
        ips  = _IP_RE.findall(raw)
        out  = [ip for ip in ips if not self.in_scope(ip.split("/")[0])]
        return len(out) == 0, out

    def summary(self) -> str:
        if not self._networks:
            return "no scope defined — all targets allowed"
        mode = "[red]strict[/]" if self._strict else "[yellow]warn[/]"
        nets = "  ".join(str(n) for n in self._networks)
        return f"{mode}: {nets}"
