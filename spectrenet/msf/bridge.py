# spectrenet/msf/bridge.py
import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("spectrenet")


@dataclass
class MsfSession:
    id: str
    type: str
    tunnel_peer: str
    info: dict[str, Any]


class MsfBridge:
    """Thin wrapper around pymetasploit3's MsfRpcClient. Client is injectable for tests."""

    def __init__(self, host: str = "127.0.0.1", port: int = 55553,
                 password: str = "msf", ssl: bool = False, client=None):
        self.host = host
        self.port = port
        self.password = password
        self.ssl = ssl
        self._client = client
        self._connected = False

    def connect(self) -> bool:
        if self._client is not None:
            self._connected = True
            return True
        try:
            from pymetasploit3.msfrpc import MsfRpcClient
            self._client = MsfRpcClient(
                self.password, host=self.host, port=self.port, ssl=self.ssl
            )
            self._connected = True
            log.info("Connected to msfrpcd at %s:%d", self.host, self.port)
            return True
        except Exception as e:
            log.warning("Failed to connect to msfrpcd: %s", e)
            return False

    def is_connected(self) -> bool:
        return self._connected

    def run_module(self, module_path: str, options: dict) -> str:
        """Run an exploit module. Returns job_id string or raises RuntimeError on failure."""
        if not self._connected:
            raise RuntimeError("Not connected to msfrpcd — call connect() first")
        try:
            exploit = self._client.modules.use("exploit", module_path)
            for k, v in options.items():
                exploit[k] = v
            result = exploit.execute(payload=options.get("PAYLOAD", ""))
            return str(result.get("job_id", ""))
        except Exception as e:
            raise RuntimeError(f"MSF module execution failed: {e}") from e

    def get_sessions(self) -> list[MsfSession]:
        """Return all active Metasploit sessions."""
        if not self._connected:
            return []
        try:
            raw = self._client.sessions.list
            return [
                MsfSession(id=sid, type=info.get("type", ""),
                           tunnel_peer=info.get("tunnel_peer", ""), info=info)
                for sid, info in raw.items()
            ]
        except Exception as e:
            log.warning("Failed to list MSF sessions: %s", e)
            return []

    def get_session_interactor(self, session_id: str) -> "SessionInteractor":
        from spectrenet.msf.session_interactor import SessionInteractor
        return SessionInteractor(self._client, session_id)
