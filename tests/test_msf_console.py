import pytest
from spectrenet.msf.console import MsfConsole


class FakeConsoleObj:
    """Simulates a pymetasploit3 console object."""
    def __init__(self, responses: list[dict]):
        self._responses = iter(responses)
        self.written: list[str] = []
        self.destroyed = False

    def write(self, text: str) -> None:
        self.written.append(text)

    def read(self) -> dict:
        return next(self._responses)

    def destroy(self) -> None:
        self.destroyed = True


class FakeConsoles:
    def __init__(self, console_obj: FakeConsoleObj):
        self._console = console_obj

    def console(self) -> FakeConsoleObj:
        return self._console


class FakeClient:
    def __init__(self, console_obj: FakeConsoleObj):
        self.consoles = FakeConsoles(console_obj)


def test_open_returns_true_with_injected_client():
    obj = FakeConsoleObj([])
    con = MsfConsole(client=FakeClient(obj))
    assert con.open() is True


def test_open_returns_false_on_exception():
    class BrokenClient:
        class consoles:
            @staticmethod
            def console():
                raise RuntimeError("no daemon")
    con = MsfConsole(client=BrokenClient())
    assert con.open() is False


def test_send_returns_output_when_not_busy():
    obj = FakeConsoleObj([
        {"data": "msf output\n", "busy": False},
    ])
    con = MsfConsole(client=FakeClient(obj))
    con.open()
    result = con.send("version")
    assert result == "msf output\n"
    assert "version\n" in obj.written


def test_send_polls_until_not_busy():
    obj = FakeConsoleObj([
        {"data": "partial...", "busy": True},
        {"data": "done\n", "busy": False},
    ])
    con = MsfConsole(client=FakeClient(obj), poll_interval=0)
    con.open()
    result = con.send("use exploit/multi/handler")
    assert result == "partial...done\n"


def test_close_destroys_console():
    obj = FakeConsoleObj([])
    con = MsfConsole(client=FakeClient(obj))
    con.open()
    con.close()
    assert obj.destroyed is True


def test_send_before_open_returns_empty():
    obj = FakeConsoleObj([])
    con = MsfConsole(client=FakeClient(obj))
    result = con.send("anything")
    assert result == ""
