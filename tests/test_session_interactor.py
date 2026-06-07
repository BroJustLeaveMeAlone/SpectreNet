# tests/test_session_interactor.py
import pytest
from spectrenet.msf.session_interactor import SessionInteractor


class FakeMeterpreterSession:
    type = "meterpreter"

    def __init__(self, outputs: list[str]):
        self._outputs = iter(outputs)

    def run_with_output(self, command: str) -> str:
        return next(self._outputs)


class FakeShellSession:
    type = "shell"

    def __init__(self, outputs: list[str]):
        self._outputs = iter(outputs)
        self.written: list[str] = []

    def write(self, text: str) -> None:
        self.written.append(text)

    def read(self) -> str:
        return next(self._outputs)


class FakeSessions:
    def __init__(self, session_obj):
        self._session = session_obj

    def session(self, sid: str):
        return self._session


class FakeClient:
    def __init__(self, session_obj):
        self.sessions = FakeSessions(session_obj)


def test_session_type_meterpreter():
    s = SessionInteractor(FakeClient(FakeMeterpreterSession([])), "1")
    assert s.session_type() == "meterpreter"


def test_session_type_shell():
    s = SessionInteractor(FakeClient(FakeShellSession([])), "2")
    assert s.session_type() == "shell"


def test_run_meterpreter_returns_output():
    sess = FakeMeterpreterSession(["NT AUTHORITY\\SYSTEM"])
    s = SessionInteractor(FakeClient(sess), "1")
    assert s.run("getuid") == "NT AUTHORITY\\SYSTEM"


def test_run_shell_returns_output():
    sess = FakeShellSession(["root\n"])
    s = SessionInteractor(FakeClient(sess), "1")
    result = s.run("id")
    assert result == "root\n"
    assert "id\n" in sess.written


def test_run_handles_exception_gracefully():
    class BrokenSession:
        type = "meterpreter"
        def run_with_output(self, cmd):
            raise RuntimeError("session dead")

    s = SessionInteractor(FakeClient(BrokenSession()), "1")
    result = s.run("getuid")
    assert "error" in result.lower() or result == ""
