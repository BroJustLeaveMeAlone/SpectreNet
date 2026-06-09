"""
SpectreBot QLoRA fine-tuning script.

Designed to run on Kaggle (free T4 GPU) or any CUDA machine.
Generated notebook: notebooks/spectrenet_finetune.ipynb

Usage (standalone):
    python -m spectrenet.training.trainer \\
        --dataset training_data.train.jsonl \\
        --model-size 12b \\
        --output ./spectrenet-adapter \\
        --hf-repo YourOrg/spectrenet-12b   # optional: push to HuggingFace Hub

Model sizes:
    mini  → microsoft/Phi-3-mini-4k-instruct        (3.8B  — ~4 GB VRAM)
    7b    → mistralai/Mistral-7B-Instruct-v0.3      (7B    — ~8 GB VRAM)
    8b    → meta-llama/Llama-3.1-8B-Instruct        (8B    — ~10 GB VRAM)
    12b   → mistralai/Mistral-Nemo-Instruct-2407    (12B   — ~14 GB VRAM, recommended)

Hardware guide:
    Kaggle free (T4 x2, 32 GB): all sizes including 12b
    Single T4 (16 GB):          mini, 7b, 8b
    Single A100 (40 GB):        all sizes including 70B class with QLoRA
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

log = logging.getLogger("spectrenet.training")

BASE_MODELS = {
    "mini": "microsoft/Phi-3-mini-4k-instruct",
    "7b":   "mistralai/Mistral-7B-Instruct-v0.3",
    "8b":   "meta-llama/Llama-3.1-8B-Instruct",
    "12b":  "mistralai/Mistral-Nemo-Instruct-2407",
}

LORA_CONFIG = {
    "r":              16,
    "lora_alpha":     32,
    "lora_dropout":   0.05,
    "bias":           "none",
    "task_type":      "CAUSAL_LM",
    "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
}

TRAINING_ARGS = {
    "num_train_epochs":            3,
    "per_device_train_batch_size": 2,
    "gradient_accumulation_steps": 4,
    "learning_rate":               2e-4,
    "fp16":                        True,
    "logging_steps":               10,
    "save_steps":                  100,
    "warmup_ratio":                0.03,
    "lr_scheduler_type":           "cosine",
    "report_to":                   "none",
}

# Per-size overrides applied on top of TRAINING_ARGS.
# 12b reduces batch size and doubles accumulation steps to fit T4 VRAM
# while keeping the same effective batch size (1 * 8 = 2 * 4 = 8).
TRAINING_ARGS_OVERRIDES: dict[str, dict] = {
    "12b": {
        "per_device_train_batch_size": 1,
        "gradient_accumulation_steps": 8,
    },
}


def _check_imports() -> None:
    missing = []
    for pkg in ("transformers", "peft", "trl", "torch", "datasets"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        raise ImportError(
            f"Missing packages: {', '.join(missing)}\n"
            "Install with: pip install transformers peft trl torch datasets bitsandbytes accelerate"
        )


def train(
    dataset_path: Path,
    model_size: str,
    output_dir: Path,
    hf_repo: str | None = None,
    hf_token: str | None = None,
    val_path: Path | None = None,
) -> None:
    _check_imports()

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TrainingArguments,
    )
    from trl import SFTTrainer, DataCollatorForCompletionOnlyLM

    base_model = BASE_MODELS.get(model_size)
    if base_model is None:
        raise ValueError(f"Unknown model size '{model_size}'. Choose: {list(BASE_MODELS)}")

    log.info("Base model : %s", base_model)
    log.info("Dataset    : %s", dataset_path)
    log.info("Output     : %s", output_dir)

    # ── Load dataset ─────────────────────────────────────────────────────────
    examples = []
    with dataset_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))

    def format_chat(ex: dict) -> str:
        parts = []
        for msg in ex["messages"]:
            role, content = msg["role"], msg["content"]
            if role == "system":
                parts.append(f"<|system|>\n{content}</s>")
            elif role == "user":
                parts.append(f"<|user|>\n{content}</s>")
            elif role == "assistant":
                parts.append(f"<|assistant|>\n{content}</s>")
        return "\n".join(parts)

    texts = [format_chat(ex) for ex in examples]
    dataset = Dataset.from_dict({"text": texts})
    log.info("Training examples: %d", len(dataset))

    # ── Load model + tokenizer ────────────────────────────────────────────────
    quant_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )

    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=quant_cfg,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    # ── LoRA ──────────────────────────────────────────────────────────────────
    lora_cfg = LoraConfig(**LORA_CONFIG)
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    # ── Training ──────────────────────────────────────────────────────────────
    effective_args = {**TRAINING_ARGS, **TRAINING_ARGS_OVERRIDES.get(model_size, {})}
    if effective_args != TRAINING_ARGS:
        log.info("Applied training overrides for %s: %s",
                 model_size, TRAINING_ARGS_OVERRIDES[model_size])
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        **effective_args,
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        args=training_args,
        dataset_text_field="text",
        max_seq_length=2048,
        tokenizer=tokenizer,
    )

    log.info("Starting training …")
    trainer.train()

    # ── Save adapter ──────────────────────────────────────────────────────────
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    log.info("Adapter saved to %s", output_dir)

    # ── Push to HuggingFace Hub (optional) ───────────────────────────────────
    if hf_repo:
        log.info("Pushing adapter to HuggingFace Hub: %s", hf_repo)
        model.push_to_hub(hf_repo, token=hf_token)
        tokenizer.push_to_hub(hf_repo, token=hf_token)
        log.info("Upload complete.")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description="SpectreBot QLoRA fine-tuning")
    p.add_argument("--dataset",    required=True, type=Path, help="Path to .train.jsonl")
    p.add_argument("--model-size", default="12b", choices=list(BASE_MODELS),
                   help="mini | 7b | 8b | 12b (default: 12b)")
    p.add_argument("--output",     default=Path("spectrenet-adapter"), type=Path)
    p.add_argument("--hf-repo",    default=None, help="HuggingFace repo to push adapter (optional)")
    p.add_argument("--hf-token",   default=None, help="HuggingFace token for push")
    args = p.parse_args()

    train(
        dataset_path=args.dataset,
        model_size=args.model_size,
        output_dir=args.output,
        hf_repo=args.hf_repo,
        hf_token=args.hf_token,
    )


if __name__ == "__main__":
    main()
