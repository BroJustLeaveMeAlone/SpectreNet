import logging
import time

log = logging.getLogger("spectrenet")


class MsfConsole:
    """Wraps pymetasploit3's RPC console API. Client is injectable for tests."""

    def __init__(self, client=None, poll_interval: float = 0.5):
        self._client = client
        self._console = None
        self._poll_interval = poll_interval

    def open(self) -> bool:
        try:
            self._console = self._client.consoles.console()
            return True
        except Exception as e:
            log.warning("Failed to open MSF console: %s", e)
            return False

    def send(self, command: str, timeout: float = 60.0) -> str:
        if self._console is None:
            return ""
        self._console.write(command + "\n")
        output = ""
        deadline = time.monotonic() + timeout
        while True:
            result = self._console.read()
            output += result.get("data", "")
            if not result.get("busy", True):
                break
            if time.monotonic() > deadline:
                log.warning("MSF console read timed out after %.0fs for command: %s", timeout, command)
                output += "\n[timed out]"
                break
            if self._poll_interval > 0:
                time.sleep(self._poll_interval)
        return output

    def close(self) -> None:
        if self._console is not None:
            self._console.destroy()
            self._console = None
