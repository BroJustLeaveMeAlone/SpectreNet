from __future__ import annotations
from typing import Any
from spectrenet.model.interface import ModelInterface

try:
    import httpx as _httpx
except ImportError:
    _httpx = None  # type: ignore[assignment]


class OpenAIBackend(ModelInterface):
    """ModelInterface for any OpenAI-spec endpoint: OpenAI, DeepSeek, Qwen, LM Studio, vLLM."""

    def __init__(self, model: str, base_url: str, api_key: str,
                 client: Any = None, timeout: float = 120.0) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = client
        self._timeout = timeout

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self._base_url}/v1/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type":  "application/json",
        }
        client = self._client
        if client is None:
            if _httpx is None:
                raise ImportError(
                    "httpx is required for OpenAIBackend: pip install httpx"
                )
            client = _httpx
        response = client.post(url, json=payload, headers=headers, timeout=self._timeout)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
