"""CrackMapExec / NetExec wrapper — supports both `crackmapexec` (cme) and `netexec` (nxc)."""
from __future__ import annotations

import re
import shutil
from spectrenet.wrappers.base import ToolWrapper

_SUCCESS_RE = re.compile(r"\[(\+)\]\s+(.+)")
_SHARE_RE   = re.compile(r"\s+([\w\$\-]+)\s+READ|WRITE", re.IGNORECASE)
_USER_RE    = re.compile(r"username:\s*(\S+)", re.IGNORECASE)
_HASH_RE    = re.compile(r"([a-f0-9]{32}:[a-f0-9]{32})", re.IGNORECASE)


def _find_binary() -> str | None:
    for name in ("netexec", "nxc", "crackmapexec", "cme"):
        if shutil.which(name):
            return name
    return None


class CrackMapExecWrapper(ToolWrapper):
    tool_name = "crackmapexec"

    def is_available(self) -> bool:
        return _find_binary() is not None

    def run(
        self,
        protocol: str = "smb",
        target: str = "",
        username: str = "",
        password: str = "",
        flags: str = "",
    ) -> dict:
        import subprocess
        binary = _find_binary() or "crackmapexec"
        args   = [binary, protocol, target]
        if username:
            args += ["-u", username]
        if password:
            args += ["-p", password]
        if flags:
            args += flags.split()
        result  = subprocess.run(args, capture_output=True, text=True, timeout=120)
        output  = result.stdout + result.stderr
        return {
            "raw":       output,
            "successes": self._parse_successes(output),
            "shares":    self._parse_shares(output),
            "hashes":    _HASH_RE.findall(output),
            "users":     _USER_RE.findall(output),
        }

    def _parse_successes(self, output: str) -> list[str]:
        return [m.group(2).strip() for m in _SUCCESS_RE.finditer(output)]

    def _parse_shares(self, output: str) -> list[str]:
        return list(dict.fromkeys(_SHARE_RE.findall(output)))

    @property
    def schema(self) -> dict:
        return {
            "successes": "list[str]  — lines flagged with [+]",
            "shares":    "list[str]  — readable/writable share names",
            "hashes":    "list[str]  — NTLM hashes found",
            "users":     "list[str]  — usernames found",
        }
