from textual.reactive import reactive
from textual.widgets import Static
from spectrenet.theme import CYAN

_STATUS_COLORS = {
    "RUNNING":  CYAN,
    "SUCCESS":  "green",
    "DEAD END": "yellow",
    "STOPPED":  "dim",
}


class GoalPanel(Static):
    """Single-line widget showing current goal and AI status."""

    goal: reactive[str] = reactive("No goal set")
    status: reactive[str] = reactive("STOPPED")

    def render(self) -> str:
        color = _STATUS_COLORS.get(self.status, "dim")
        return f"[{color}][AI: {self.status}][/]  Goal: {self.goal}"

    def update_goal(self, goal: str, status: str) -> None:
        self.goal = goal
        self.status = status
