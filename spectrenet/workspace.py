"""SpectreNet workspace — persist session state (commands, notes, targets, findings)."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

_DEFAULT_PATH = ".spectrenet_workspace.json"


class Workspace:
    def __init__(self, path: str = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self._data: dict = self._blank()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def _blank() -> dict:
        return {
            "created":  datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
            "commands": [],
            "notes":    [],
            "targets":  [],
            "findings": [],
        }

    @property
    def exists(self) -> bool:
        return self._path.exists()

    def load(self) -> bool:
        if not self._path.exists():
            return False
        try:
            self._data = json.loads(self._path.read_text(encoding="utf-8"))
            return True
        except Exception:
            return False

    def save(self) -> None:
        self._data["modified"] = datetime.now().isoformat()
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def reset(self) -> None:
        self._data = self._blank()

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add_command(self, cmd: str) -> None:
        self._data["commands"].append({"t": datetime.now().isoformat(), "cmd": cmd})

    def add_note(self, text: str) -> None:
        self._data["notes"].append({"t": datetime.now().isoformat(), "text": text})

    def add_target(self, target: str) -> None:
        if target and target not in self._data["targets"]:
            self._data["targets"].append(target)

    def add_finding(self, finding: dict) -> None:
        self._data["findings"].append(finding)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def commands(self) -> list[dict]:
        return self._data.get("commands", [])

    @property
    def notes(self) -> list[dict]:
        return self._data.get("notes", [])

    @property
    def targets(self) -> list[str]:
        return self._data.get("targets", [])

    @property
    def findings(self) -> list[dict]:
        return self._data.get("findings", [])

    def summary(self) -> str:
        return (
            f"[dim]path:[/] {self._path}  "
            f"[dim]cmds:[/] {len(self.commands)}  "
            f"[dim]notes:[/] {len(self.notes)}  "
            f"[dim]targets:[/] {len(self.targets)}  "
            f"[dim]findings:[/] {len(self.findings)}"
        )
