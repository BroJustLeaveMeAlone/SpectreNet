"""
SpectreBot model backend — fine-tuned model hosted on Together.ai.

Usage in config.yaml:
    model_backend: spectre
    together_api_key: sk-...
    together_model: <your-account>/spectre-70b   # set after training completes
"""
from __future__ import annotations

from spectrenet.model.openai_backend import OpenAIBackend

TOGETHER_BASE_URL = "https://api.together.xyz"

# Populated after the first training run completes.
# Override via config.yaml → together_model.
DEFAULT_MODEL = "spectrenet/spectre-70b"


class SpectreBackend(OpenAIBackend):
    """
    ModelInterface implementation for the SpectreBot fine-tuned model.

    Thin wrapper around OpenAIBackend — Together.ai exposes an
    OpenAI-compatible chat completions endpoint so no new HTTP logic
    is needed. The only difference is sensible defaults for the
    Together.ai base URL and the SpectreBot model name.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(
            model=model,
            base_url=TOGETHER_BASE_URL,
            api_key=api_key,
            timeout=timeout,
        )

    @classmethod
    def from_config(cls, cfg) -> "SpectreBackend":
        """Construct from a SpectreNet Config object."""
        return cls(
            api_key=getattr(cfg, "together_api_key", ""),
            model=getattr(cfg, "together_model", DEFAULT_MODEL),
        )
