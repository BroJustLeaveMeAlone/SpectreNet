# spectrenet/msf/session_interactor.py
import logging

log = logging.getLogger("spectrenet")


class SessionInteractor:
    """Send commands to and read output from an active Metasploit session."""

    def __init__(self, client, session_id: str):
        self._client = client
        self._session_id = session_id

    def session_type(self) -> str:
        return self._client.sessions.session(self._session_id).type

    def run(self, command: str) -> str:
        try:
            sess = self._client.sessions.session(self._session_id)
            if sess.type == "meterpreter":
                return sess.run_with_output(command)
            else:
                sess.write(command + "\n")
                return sess.read()
        except Exception as e:
            log.error("Session %s command failed: %s", self._session_id, e)
            return f"[error: {e}]"
