#!/usr/bin/env python3
"""
SpectreBot training pipeline — Together.ai

Steps this script automates:
  1. Build JSONL dataset from seed data + optional session DB files
  2. Upload dataset to Together.ai Files API
  3. Start a fine-tune job on Llama 3.1 70B (or configured base model)
  4. Poll until complete and print the resulting model ID

Usage:
    python scripts/train_spectre.py --api-key <TOGETHER_KEY>
    python scripts/train_spectre.py --api-key <TOGETHER_KEY> --db spectrenet.db --db other.db
    python scripts/train_spectre.py --api-key <TOGETHER_KEY> --base-model meta-llama/Meta-Llama-3.1-70B

After training completes, add to config.yaml:
    model_backend: spectre
    together_api_key: <TOGETHER_KEY>
    together_model: <printed model ID>
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Make sure spectrenet package is importable when run from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from spectrenet.training.dataset_builder import DatasetBuilder


# Together.ai base model ID for fine-tuning.
# Llama 3.1 70B is the recommended base — strong reasoning, permissive license,
# minimal built-in refusals compared to instruct-tuned variants.
DEFAULT_BASE_MODEL = "meta-llama/Meta-Llama-3.1-70B"

# Together.ai fine-tune hyperparameters
DEFAULT_N_EPOCHS    = 3
DEFAULT_BATCH_SIZE  = 16
DEFAULT_LR          = 1e-5
DEFAULT_WARMUP      = 100


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build dataset and launch SpectreBot fine-tune on Together.ai"
    )
    parser.add_argument("--api-key",    required=True, metavar="KEY",
                        help="Together.ai API key (get one at api.together.xyz)")
    parser.add_argument("--db",         action="append", default=[], metavar="PATH",
                        help="SpectreNet session DB to include (can repeat)")
    parser.add_argument("--output",     default="spectrenet_train", metavar="PREFIX",
                        help="Output JSONL file prefix (default: spectrenet_train)")
    parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL, metavar="MODEL",
                        help=f"Together.ai base model ID (default: {DEFAULT_BASE_MODEL})")
    parser.add_argument("--epochs",     type=int,   default=DEFAULT_N_EPOCHS)
    parser.add_argument("--batch-size", type=int,   default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--lr",         type=float, default=DEFAULT_LR)
    parser.add_argument("--dry-run",    action="store_true",
                        help="Build dataset only — do not upload or train")
    args = parser.parse_args()

    # ── 1. Build dataset ────────────────────────────────────────────────────
    print("[1/4] Building dataset...")
    db_paths = [Path(p) for p in args.db]
    builder  = DatasetBuilder()
    out      = Path(args.output)
    train_n, val_n = builder.build(out, db_paths=db_paths)
    train_file = out.with_suffix(".train.jsonl")
    val_file   = out.with_suffix(".val.jsonl")
    print(f"      Train: {train_n} examples → {train_file}")
    print(f"      Val:   {val_n} examples → {val_file}")

    if args.dry_run:
        print("[dry-run] Stopping here — dataset written, no upload.")
        return

    # ── 2. Upload files ─────────────────────────────────────────────────────
    try:
        import httpx
    except ImportError:
        print("ERROR: httpx is required — pip install httpx")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {args.api_key}",
    }

    print("[2/4] Uploading training file to Together.ai...")
    train_file_id = _upload_file(httpx, headers, train_file, "train")
    print(f"      Training file ID: {train_file_id}")

    val_file_id = None
    if val_n > 0:
        print("      Uploading validation file...")
        val_file_id = _upload_file(httpx, headers, val_file, "val")
        print(f"      Validation file ID: {val_file_id}")

    # ── 3. Start fine-tune job ───────────────────────────────────────────────
    print("[3/4] Starting fine-tune job...")
    job_payload: dict = {
        "training_file":   train_file_id,
        "model":           args.base_model,
        "n_epochs":        args.epochs,
        "batch_size":      args.batch_size,
        "learning_rate":   args.lr,
        "warmup_ratio":    0.1,
        "suffix":          "spectre",
    }
    if val_file_id:
        job_payload["validation_file"] = val_file_id

    resp = httpx.post(
        "https://api.together.xyz/v1/fine-tunes",
        json=job_payload,
        headers={**headers, "Content-Type": "application/json"},
        timeout=60,
    )
    resp.raise_for_status()
    job = resp.json()
    job_id = job["id"]
    print(f"      Job ID: {job_id}")
    print(f"      Base model: {args.base_model}")
    print(f"      Epochs: {args.epochs}, Batch: {args.batch_size}, LR: {args.lr}")

    # ── 4. Poll until done ───────────────────────────────────────────────────
    print("[4/4] Waiting for training to complete (this takes 30–120 min for 70B)...")
    model_id = _poll_job(httpx, headers, job_id)
    print()
    print("=" * 60)
    print("SpectreBot training complete!")
    print(f"Model ID: {model_id}")
    print()
    print("Add to config.yaml:")
    print("  model_backend: spectre")
    print(f"  together_api_key: {args.api_key[:8]}...")
    print(f"  together_model: {model_id}")
    print("=" * 60)


def _upload_file(httpx, headers: dict, path: Path, purpose: str) -> str:
    with path.open("rb") as f:
        resp = httpx.post(
            "https://api.together.xyz/v1/files",
            headers=headers,
            files={"file": (path.name, f, "application/jsonl")},
            data={"purpose": purpose},
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()["id"]


def _poll_job(httpx, headers: dict, job_id: str) -> str:
    interval = 30
    while True:
        resp = httpx.get(
            f"https://api.together.xyz/v1/fine-tunes/{job_id}",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data   = resp.json()
        status = data.get("status", "unknown")

        # Print progress
        trained = data.get("trained_tokens", 0)
        total   = data.get("total_tokens", 0)
        pct     = f"{trained/total*100:.1f}%" if total else "—"
        print(f"\r      Status: {status:<20} Tokens: {trained:,}/{total:,} ({pct})", end="", flush=True)

        if status == "completed":
            return data["output_name"]
        if status in ("failed", "cancelled", "error"):
            print()
            print(f"ERROR: Job {status}. Check https://api.together.xyz/playground/fine-tuning/{job_id}")
            sys.exit(1)

        time.sleep(interval)


if __name__ == "__main__":
    main()
