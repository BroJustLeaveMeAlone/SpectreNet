# spectrenet/model/ollama_backend.py
import httpx
from spectrenet.model.interface import ModelInterface

class OllamaBackend(ModelInterface):
    def __init__(self, model: str, url: str = "http://localhost:11434", client=None, timeout: float = 120.0):
        self.model = model
        self.url = url.rstrip("/")
        self.timeout = timeout
        self._client = client or httpx.Client()

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        resp = self._client.post(
            f"{self.url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
