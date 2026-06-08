"""
Anthropic backend — Claude models via the Anthropic API.
Requires: pip install anthropic
Get an API key at console.anthropic.com.
"""
from __future__ import annotations
from typing import Any
from spectrenet.model.interface import ModelInterface

try:
    import anthropic as _anthropic
except ImportError:
    _anthropic = None  # type: ignore[assignment]

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class AnthropicBackend(ModelInterface):
    """ModelInterface for Anthropic's Claude API."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 2048,
        timeout: float = 120.0,
        client: Any = None,
    ) -> None:
        if _anthropic is None and client is None:
            raise ImportError(
                "anthropic package required: pip install anthropic"
            )
        self._api_key   = api_key
        self._model     = model
        self._max_tokens = max_tokens
        self._timeout   = timeout
        self._client    = client

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        client = self._client
        if client is None:
            client = _anthropic.Anthropic(api_key=self._api_key)
        message = client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text

    @classmethod
    def from_config(cls, cfg) -> "AnthropicBackend":
        return cls(
            api_key=getattr(cfg, "anthropic_api_key", ""),
            model=getattr(cfg, "anthropic_model", DEFAULT_MODEL),
        )
