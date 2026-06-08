"""
OpenRouter backend — routes to 100+ models via a single API key.
Free tier available for many open models. Sign up at openrouter.ai.
"""
from spectrenet.model.openai_backend import OpenAIBackend

OPENROUTER_BASE_URL = "https://openrouter.ai/api"
DEFAULT_MODEL        = "meta-llama/llama-3.1-70b-instruct"


class OpenRouterBackend(OpenAIBackend):
    """ModelInterface for OpenRouter (access to Claude, Llama, Mistral, etc.)."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, timeout: float = 60.0) -> None:
        super().__init__(model=model, base_url=OPENROUTER_BASE_URL, api_key=api_key, timeout=timeout)

    @classmethod
    def from_config(cls, cfg) -> "OpenRouterBackend":
        return cls(
            api_key=getattr(cfg, "openrouter_api_key", ""),
            model=getattr(cfg, "openrouter_model", DEFAULT_MODEL),
        )
