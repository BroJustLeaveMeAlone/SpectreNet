"""
Extracts training pairs from SpectreNet SQLite session logs.

Session logs store tool + params + output_hash. The extractor builds
instruction-following examples from logged action sequences so real
operator usage becomes training signal over time.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from spectrenet.training.seed_data import SYSTEM_PROMPT


class SessionLogExtractor:
    """Reads a SpectreNet session DB and yields chat-format training examples."""

    def extract(self, db_path: Path) -> list[dict]:
        if not db_path.exists():
            return []
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        examples = []
        try:
            sessions = conn.execute("SELECT * FROM sessions ORDER BY id").fetchall()
            for session in sessions:
                sid = session["id"]
                actions = conn.execute(
                    "SELECT * FROM actions WHERE session_id=? ORDER BY id", (sid,)
                ).fetchall()
                approvals = conn.execute(
                    "SELECT * FROM approvals WHERE session_id=? ORDER BY id", (sid,)
                ).fetchall()
                examples.extend(self._session_to_examples(dict(session), actions, approvals))
        finally:
            conn.close()
        return examples

    def _session_to_examples(
        self,
        session: dict,
        actions: list,
        approvals: list,
    ) -> list[dict]:
        examples = []

        # Example 1: tool sequence recap
        # "Given this session's action log, summarise what happened."
        if len(actions) >= 3:
            action_list = []
            for a in actions:
                params = json.loads(a["params"] or "{}")
                action_list.append(f"- {a['tool']}: {json.dumps(params)}")
            user_msg = (
                f"Session '{session['name']}' (mode: {session['mode']}) ran these tools:\n"
                + "\n".join(action_list)
                + "\n\nSummarise the engagement and suggest what to do next."
            )
            tool_names = [a["tool"] for a in actions]
            assistant_msg = (
                f"This {session['mode']} session executed {len(actions)} actions: "
                + ", ".join(tool_names)
                + ". "
                "Based on the sequence, the operator completed initial reconnaissance and "
                "is ready to move into exploitation. Recommend reviewing findings in the "
                "Findings Panel (F2) and running targeted vulnerability scans against "
                "services identified during recon."
            )
            examples.append(_make_example(user_msg, assistant_msg))

        # Example 2: approval gate decisions
        for approval in approvals:
            if approval["result"] == "approved":
                user_msg = (
                    f"Should I execute {approval['action']} against {approval['target']}? "
                    f"Risk level: {approval['risk']}."
                )
                assistant_msg = (
                    f"Yes. {approval['action']} against {approval['target']} is the correct "
                    f"next step given current findings. Risk is {approval['risk']} — "
                    "ensure listener is running before execution."
                )
                examples.append(_make_example(user_msg, assistant_msg))
            elif approval["result"] == "denied":
                user_msg = (
                    f"Should I execute {approval['action']} against {approval['target']}? "
                    f"Risk level: {approval['risk']}."
                )
                assistant_msg = (
                    f"Hold. The operator denied {approval['action']} against {approval['target']} "
                    f"at risk level {approval['risk']}. Replan from current state — consider "
                    "lower-risk enumeration steps before attempting intrusive actions."
                )
                examples.append(_make_example(user_msg, assistant_msg))

        return examples


def _make_example(user: str, assistant: str) -> dict:
    return {
        "messages": [
            {"role": "system",    "content": SYSTEM_PROMPT},
            {"role": "user",      "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }
