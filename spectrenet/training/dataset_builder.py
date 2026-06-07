"""
Combines seed data and session-log extracts into a JSONL training file
ready for upload to Together.ai.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from spectrenet.training.seed_data import SEED_EXAMPLES, SYSTEM_PROMPT
from spectrenet.training.data_extractor import SessionLogExtractor


class DatasetBuilder:
    def __init__(self, seed: int = 42):
        self._seed = seed

    def build(
        self,
        output: Path,
        db_paths: list[Path] | None = None,
        val_split: float = 0.1,
    ) -> tuple[int, int]:
        """
        Build train + validation JSONL files.

        Returns (train_count, val_count).
        """
        examples = self._collect(db_paths or [])
        rng = random.Random(self._seed)
        rng.shuffle(examples)

        split = max(1, int(len(examples) * val_split))
        val_examples   = examples[:split]
        train_examples = examples[split:]

        train_path = output.with_suffix(".train.jsonl")
        val_path   = output.with_suffix(".val.jsonl")

        _write_jsonl(train_path, train_examples)
        _write_jsonl(val_path,   val_examples)

        return len(train_examples), len(val_examples)

    def _collect(self, db_paths: list[Path]) -> list[dict]:
        # Seed examples → chat format
        examples = [
            {
                "messages": [
                    {"role": "system",    "content": SYSTEM_PROMPT},
                    {"role": "user",      "content": ex["user"]},
                    {"role": "assistant", "content": ex["assistant"]},
                ]
            }
            for ex in SEED_EXAMPLES
        ]

        # Session log examples
        extractor = SessionLogExtractor()
        for db_path in db_paths:
            examples.extend(extractor.extract(db_path))

        return examples


def _write_jsonl(path: Path, examples: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
