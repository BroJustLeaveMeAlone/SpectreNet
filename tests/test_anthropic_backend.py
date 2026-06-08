from unittest.mock import MagicMock
import pytest
from spectrenet.model.anthropic_backend import AnthropicBackend


def _make_client(text: str):
    content = MagicMock()
    content.text = text
    message = MagicMock()
    message.content = [content]
    client = MagicMock()
    client.messages.create.return_value = message
    return client


def test_complete_returns_text():
    client = _make_client("Use ms17_010.")
    backend = AnthropicBackend(api_key="test", client=client)
    result = backend.complete("sys", "exploit smb?")
    assert result == "Use ms17_010."


def test_complete_passes_system_and_user():
    client = _make_client("ok")
    backend = AnthropicBackend(api_key="sk-ant-test", client=client)
    backend.complete("SYSTEM", "USER")
    call = client.messages.create.call_args
    assert call.kwargs["system"] == "SYSTEM"
    assert call.kwargs["messages"][0]["content"] == "USER"


def test_complete_passes_model():
    client = _make_client("ok")
    backend = AnthropicBackend(api_key="x", model="claude-opus-4-8", client=client)
    backend.complete("s", "u")
    assert client.messages.create.call_args.kwargs["model"] == "claude-opus-4-8"


def test_from_config():
    cfg = MagicMock()
    cfg.anthropic_api_key = "sk-ant-abc"
    cfg.anthropic_model   = "claude-haiku-4-5-20251001"
    b = AnthropicBackend.from_config(cfg)
    assert b._api_key == "sk-ant-abc"
    assert b._model   == "claude-haiku-4-5-20251001"


def test_import_error_without_client():
    import spectrenet.model.anthropic_backend as mod
    orig = mod._anthropic
    mod._anthropic = None
    try:
        with pytest.raises(ImportError, match="anthropic package"):
            AnthropicBackend(api_key="x")
    finally:
        mod._anthropic = orig
