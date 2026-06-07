"""Loot vault — persistent store for credentials, hashes, files, and secrets."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_DEFAULT_PATH = ".spectrenet_loot.json"


class LootVault:
    TYPES = ("cred", "hash", "file", "secret")

    def __init__(self, path: str = _DEFAULT_PATH) -> None:
        self._path    = Path(path)
        self._entries: list[dict] = []
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._entries = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                self._entries = []

    def save(self) -> None:
        self._path.write_text(json.dumps(self._entries, indent=2), encoding="utf-8")

    def add(self, loot_type: str, text: str) -> None:
        self._entries.append({
            "type": loot_type,
            "text": text,
            "t":    datetime.now().isoformat(),
        })
        self.save()

    def all(self) -> list[dict]:
        return list(self._entries)

    def by_type(self, loot_type: str) -> list[dict]:
        return [e for e in self._entries if e["type"] == loot_type]

    def clear(self) -> None:
        self._entries = []
        self.save()

    def summary(self) -> str:
        counts = {t: len(self.by_type(t)) for t in self.TYPES}
        parts  = [f"{t}: {n}" for t, n in counts.items() if n > 0]
        return ", ".join(parts) if parts else "empty"
