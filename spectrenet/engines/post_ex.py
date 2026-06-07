"""Post-exploitation engine — session management, pivot helpers, loot collection."""
from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from spectrenet.loot import LootVault


@dataclass
class Session:
    id:        int
    host:      str
    platform:  str = "unknown"
    user:      str = ""
    pid:       int = 0
    opened_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes:     list[str] = field(default_factory=list)


class PostExEngine:
    """Manages active sessions and automates common post-exploitation tasks."""

    # Commands to run for auto-enumeration on a new session
    AUTO_ENUM_UNIX = [
        "id",
        "uname -a",
        "hostname",
        "cat /etc/passwd | grep -v nologin | grep -v false",
        "ip addr",
        "ss -tlnp",
        "sudo -l 2>/dev/null",
        "find / -perm -4000 -type f 2>/dev/null | head -20",
        "cat /etc/crontab 2>/dev/null",
        "env | grep -i pass 2>/dev/null",
    ]

    AUTO_ENUM_WINDOWS = [
        "whoami /all",
        "systeminfo",
        "ipconfig /all",
        "netstat -an",
        "net user",
        "net localgroup administrators",
        "schtasks /query /fo csv /nh 2>nul",
        "reg query HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run 2>nul",
    ]

    def __init__(self, loot: LootVault | None = None) -> None:
        self._sessions: dict[int, Session] = {}
        self._next_id  = 1
        self._loot     = loot or LootVault()
        self._lock     = threading.Lock()

    # ── Session registry ──────────────────────────────────────────────────────

    def register_session(self, host: str, platform: str = "unknown", user: str = "", pid: int = 0) -> Session:
        with self._lock:
            s = Session(id=self._next_id, host=host, platform=platform, user=user, pid=pid)
            self._sessions[self._next_id] = s
            self._next_id += 1
        return s

    def get_session(self, session_id: int) -> Session | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[Session]:
        return list(self._sessions.values())

    def kill_session(self, session_id: int) -> bool:
        return self._sessions.pop(session_id, None) is not None

    # ── Local command execution (shell passthrough) ───────────────────────────

    def run_local(self, cmd: str, timeout: int = 30) -> str:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout
            )
            return (result.stdout + result.stderr).strip()
        except subprocess.TimeoutExpired:
            return "[timeout]"
        except Exception as e:
            return f"[error: {e}]"

    # ── Loot extraction helpers ────────────────────────────────────────────────

    def extract_creds(self, output: str) -> list[str]:
        """Grep output for credential patterns and save to loot vault."""
        import re
        patterns = [
            re.compile(r'["\']?password["\']?\s*[=:]\s*["\']?(\S+)', re.IGNORECASE),
            re.compile(r'["\']?passwd["\']?\s*[=:]\s*["\']?(\S+)',   re.IGNORECASE),
            re.compile(r'["\']?secret["\']?\s*[=:]\s*["\']?(\S+)',   re.IGNORECASE),
            re.compile(r'["\']?api[_-]?key["\']?\s*[=:]\s*["\']?(\S+)', re.IGNORECASE),
        ]
        found = []
        for pat in patterns:
            for m in pat.finditer(output):
                val = m.group(1).strip("'\",:;")
                if val and len(val) > 3:
                    self._loot.add("cred", m.group(0).strip())
                    found.append(val)
        return found

    def extract_hashes(self, output: str) -> list[str]:
        """Extract NTLM / shadow-style hashes and save to loot."""
        import re
        ntlm_re   = re.compile(r'[a-f0-9]{32}:[a-f0-9]{32}', re.IGNORECASE)
        shadow_re = re.compile(r'\$[16]\$[^\s:]+')
        found = []
        for m in ntlm_re.finditer(output):
            self._loot.add("hash", m.group(0))
            found.append(m.group(0))
        for m in shadow_re.finditer(output):
            self._loot.add("hash", m.group(0))
            found.append(m.group(0))
        return found

    # ── Pivot helpers ─────────────────────────────────────────────────────────

    def suggest_pivot(self, session: Session, discovered_hosts: list[str]) -> list[str]:
        """Generate pivot commands to reach discovered hosts through this session."""
        suggestions = []
        for host in discovered_hosts:
            suggestions.append(f"# Route through {session.host} → {host}")
            if "linux" in session.platform.lower() or "unix" in session.platform.lower():
                suggestions.append(f"ssh -L 1080:127.0.0.1:1080 {session.user}@{session.host} -N &")
                suggestions.append(f"proxychains nmap -sV {host} -p 22,80,443,445")
            else:
                suggestions.append(f"# Windows pivot: portfwd add -l 4445 -p 445 -r {host}")
                suggestions.append(f"msf route add {session.host}/32 {session.id}")
        return suggestions

    # ── Auto-enumeration ──────────────────────────────────────────────────────

    def auto_enum_commands(self, platform: str = "linux") -> list[str]:
        """Return enumeration commands for the given platform."""
        if "win" in platform.lower():
            return list(self.AUTO_ENUM_WINDOWS)
        return list(self.AUTO_ENUM_UNIX)

    # ── Reporting ─────────────────────────────────────────────────────────────

    def session_summary(self) -> str:
        if not self._sessions:
            return "no active sessions"
        lines = []
        for s in self.list_sessions():
            lines.append(
                f"  [{s.id}] {s.host}  platform={s.platform}  user={s.user or '?'}  "
                f"pid={s.pid or '?'}  opened={s.opened_at[:16]}"
            )
        return "\n".join(lines)
