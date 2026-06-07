# spectrenet/tui/approval_gate.py
from dataclasses import dataclass
from enum import Enum


class ApprovalResult(Enum):
    APPROVED = "Y"
    DENIED = "N"
    SKIPPED = "S"


@dataclass
class ActionCard:
    action: str
    target: str
    module: str
    risk: str      # HIGH | MED | LOW
    reason: str


def format_action_card(card: ActionCard) -> str:
    w = 56  # inner content width
    def row(label: str, value: str) -> str:
        max_val = w - 13  # w=56 minus "  label   : " overhead (2 + 9 + 2 = 13)
        value = value if len(value) <= max_val else value[:max_val - 1] + "…"
        content = f"  {label:<9}: {value}"
        return f"│{content:<{w}}│"

    lines = [
        f"┌─ APPROVAL REQUIRED {'─' * (w - 20)}┐",
        row("Action", card.action),
        row("Target", card.target),
        row("Module", card.module),
        row("Risk", card.risk),
        row("Reason", card.reason),
        f"│{' ' * w}│",
        f"│  [Y] Approve    [N] Deny    [S] Skip mission step{' ' * (w - 50)}│",
        f"└{'─' * w}┘",
    ]
    return "\n".join(lines)
