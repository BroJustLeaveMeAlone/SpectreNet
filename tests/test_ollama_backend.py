# tests/test_ollama_backend.py
from spectrenet.model.ollama_backend import OllamaBackend

class FakeResponse:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p

class FakeClient:
    def __init__(self, payload): self._p = payload; self.last = None
    def post(self, url, json, timeout):
        self.last = {"url": url, "json": json}
        return FakeResponse(self._p)

def test_ollama_complete_returns_message_content():
    fake = FakeClient({"message": {"content": "pong"}})
    be = OllamaBackend(model="llama3.1:70b", url="http://x:11434", client=fake)
    out = be.complete("you are a scanner", "ping")
    assert out == "pong"
    # verify it sent both prompts as chat messages
    msgs = fake.last["json"]["messages"]
    assert msgs[0]["role"] == "system" and msgs[0]["content"] == "you are a scanner"
    assert msgs[1]["role"] == "user" and msgs[1]["content"] == "ping"
