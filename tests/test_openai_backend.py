import pytest
from spectrenet.model.openai_backend import OpenAIBackend
from spectrenet.model.interface import ModelInterface


class FakeHTTPResponse:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


class FakeHTTPClient:
    def __init__(self, response_text: str):
        self._response_text = response_text
        self.last_request: dict = {}

    def post(self, url: str, json: dict, headers: dict, timeout: float):
        self.last_request = {"url": url, "json": json, "headers": headers}
        return FakeHTTPResponse(self._response_text)


def test_complete_returns_model_text():
    client = FakeHTTPClient("hello from model")
    backend = OpenAIBackend(
        model="deepseek-chat", base_url="https://api.deepseek.com",
        api_key="sk-test", client=client,
    )
    assert backend.complete("system prompt", "user prompt") == "hello from model"


def test_complete_posts_to_correct_endpoint():
    client = FakeHTTPClient("ok")
    backend = OpenAIBackend(
        model="deepseek-chat", base_url="https://api.deepseek.com",
        api_key="sk-test", client=client,
    )
    backend.complete("sys", "usr")
    assert client.last_request["url"].endswith("/v1/chat/completions")


def test_complete_sends_system_and_user_messages():
    client = FakeHTTPClient("ok")
    backend = OpenAIBackend(
        model="gpt-4o", base_url="https://api.openai.com",
        api_key="sk-abc", client=client,
    )
    backend.complete("be helpful", "what is 2+2?")
    messages = client.last_request["json"]["messages"]
    roles = [m["role"] for m in messages]
    assert "system" in roles
    assert "user" in roles


def test_complete_sends_api_key_as_bearer():
    client = FakeHTTPClient("ok")
    backend = OpenAIBackend(
        model="qwen-turbo", base_url="https://dashscope.aliyuncs.com/compatible-mode",
        api_key="qwen-key", client=client,
    )
    backend.complete("sys", "usr")
    auth = client.last_request["headers"].get("Authorization", "")
    assert auth == "Bearer qwen-key"


def test_implements_model_interface():
    client = FakeHTTPClient("ok")
    backend = OpenAIBackend("model", "http://localhost", "key", client=client)
    assert isinstance(backend, ModelInterface)
