"""
SpectreBot model catalogue.

Each entry describes a fine-tuned LoRA adapter hosted on HuggingFace.
The adapter is small (~100–350 MB); the base model is downloaded automatically
by transformers on first use (~4–16 GB depending on variant).

Users download adapters via:  snet model download <name>
"""
from __future__ import annotations

SPECTRENET_MODELS: dict[str, dict] = {
    "spectrenet-mini": {
        "hf_repo":         "SpectreNet/spectrenet-mini",
        "base_model":      "microsoft/Phi-3-mini-4k-instruct",
        "adapter_size_mb": 110,
        "base_size_gb":    2.4,
        "min_vram_gb":     4,
        "description":     "3.8B params — runs on 4 GB VRAM or CPU (slow). "
                           "Recommended for machines without a modern GPU.",
        "kaggle_base":     "microsoft/phi-3-mini-4k-instruct",
    },
    "spectrenet-7b": {
        "hf_repo":         "SpectreNet/spectrenet-7b",
        "base_model":      "mistralai/Mistral-7B-Instruct-v0.3",
        "adapter_size_mb": 270,
        "base_size_gb":    4.1,
        "min_vram_gb":     8,
        "description":     "7B params — best balance of quality and speed. "
                           "Recommended for most users with a dedicated GPU.",
        "kaggle_base":     "mistralai/mistral-7b-instruct-v0.3",
    },
    "spectrenet-8b": {
        "hf_repo":         "SpectreNet/spectrenet-8b",
        "base_model":      "meta-llama/Llama-3.1-8B-Instruct",
        "adapter_size_mb": 320,
        "base_size_gb":    5.0,
        "min_vram_gb":     10,
        "description":     "8B Llama 3.1 — highest quality SpectreBot. "
                           "Requires 10 GB+ VRAM or a high-RAM CPU setup.",
        "kaggle_base":     "meta-llama/llama-3.1-8b-instruct",
    },
}

DEFAULT_MODEL = "spectrenet-7b"


def list_models() -> list[dict]:
    """Return a list of model dicts with the 'name' key injected."""
    return [{"name": k, **v} for k, v in SPECTRENET_MODELS.items()]


def get_model(name: str) -> dict | None:
    return SPECTRENET_MODELS.get(name)
