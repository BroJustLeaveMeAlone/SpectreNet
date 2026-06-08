"""
Local SpectreBot backend — loads a downloaded LoRA adapter on top of its base model
and runs inference entirely on the local machine.

Requirements (CPU or CUDA GPU):
    pip install transformers peft torch accelerate

For 4-bit quantised inference (reduces VRAM by ~50%):
    pip install bitsandbytes

Usage in config.yaml:
    model_backend: local
    local_model_name: spectrenet-7b        # adapter name; resolved via models registry
    local_model_path: ""                   # leave empty to use ~/.spectrenet/models/<name>
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Any

from spectrenet.model.interface import ModelInterface

log = logging.getLogger("spectrenet")

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    import torch
    _transformers_available = True
except ImportError:
    _transformers_available = False

try:
    from peft import PeftModel
    _peft_available = True
except ImportError:
    _peft_available = False


class LocalSpectreBackend(ModelInterface):
    """
    Runs a locally downloaded SpectreBot LoRA adapter.
    The base model is downloaded automatically from HuggingFace on first use.
    """

    def __init__(
        self,
        adapter_path: str | Path,
        base_model: str,
        load_in_4bit: bool = True,
        max_new_tokens: int = 512,
        device: str | None = None,
        _model: Any = None,
        _tokenizer: Any = None,
    ) -> None:
        if not _transformers_available:
            raise ImportError(
                "transformers and torch are required for local inference:\n"
                "  pip install transformers torch accelerate\n"
                "Or for 4-bit quantisation: pip install transformers torch accelerate bitsandbytes"
            )
        if not _peft_available:
            raise ImportError(
                "peft is required to load LoRA adapters:\n"
                "  pip install peft"
            )
        self._adapter_path   = Path(adapter_path)
        self._base_model     = base_model
        self._load_in_4bit   = load_in_4bit
        self._max_new_tokens = max_new_tokens
        self._device         = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._model          = _model
        self._tokenizer      = _tokenizer

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        log.info("Loading SpectreBot adapter from %s (base: %s)", self._adapter_path, self._base_model)

        quant_cfg = None
        if self._load_in_4bit and self._device == "cuda":
            try:
                quant_cfg = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
            except Exception:
                quant_cfg = None

        self._tokenizer = AutoTokenizer.from_pretrained(self._base_model, trust_remote_code=True)
        base = AutoModelForCausalLM.from_pretrained(
            self._base_model,
            quantization_config=quant_cfg,
            device_map="auto" if self._device == "cuda" else None,
            torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
            trust_remote_code=True,
        )
        self._model = PeftModel.from_pretrained(base, str(self._adapter_path))
        if self._device == "cpu":
            self._model = self._model.to("cpu")
        self._model.eval()
        log.info("SpectreBot adapter loaded successfully on %s", self._device)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self._ensure_loaded()
        prompt = (
            f"<|system|>\n{system_prompt}</s>\n"
            f"<|user|>\n{user_prompt}</s>\n"
            f"<|assistant|>\n"
        )
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._device)
        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=self._max_new_tokens,
                do_sample=False,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        generated = output_ids[0][inputs["input_ids"].shape[1]:]
        return self._tokenizer.decode(generated, skip_special_tokens=True).strip()

    @classmethod
    def from_config(cls, cfg) -> "LocalSpectreBackend":
        from spectrenet.models.registry import SPECTRENET_MODELS
        from spectrenet.models.downloader import adapter_path_for

        name = getattr(cfg, "local_model_name", "spectrenet-7b")
        path = getattr(cfg, "local_model_path", "")

        if not path:
            path = str(adapter_path_for(name))

        meta = SPECTRENET_MODELS.get(name, {})
        base = meta.get("base_model", "mistralai/Mistral-7B-Instruct-v0.3")
        return cls(adapter_path=path, base_model=base)
