"""
Groq backend — OpenAI-compatible endpoint, free tier available.
Fast inference via Groq's LPU hardware. Sign up at console.groq.com.
"""
from spectrenet.model.openai_backend import OpenAIBackend

GROQ_BASE_URL = "https://api.groq.com/openai"
DEFAULT_MODEL  = "llama-3.1-70b-versatile"


class GroqBackend(OpenAIBackend):
    """ModelInterface for Groq's API (free tier, very fast llama/mixtral inference)."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, timeout: float = 60.0) -> None:
        super().__init__(model=model, base_url=GROQ_BASE_URL, api_key=api_key, timeout=timeout)

    @classmethod
    def from_config(cls, cfg) -> "GroqBackend":
        return cls(
            api_key=getattr(cfg, "groq_api_key", ""),
            model=getattr(cfg, "groq_model", DEFAULT_MODEL),
        )
