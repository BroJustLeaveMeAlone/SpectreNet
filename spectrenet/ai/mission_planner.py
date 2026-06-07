# spectrenet/ai/mission_planner.py
import json
import logging
import re
from dataclasses import dataclass, field
from spectrenet.model.interface import ModelInterface

log = logging.getLogger("spectrenet")

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)

INTRUSIVE_ACTIONS = {"exploit", "payload_delivery", "lateral_movement", "persistence"}

SYSTEM_PROMPT = """You are an expert penetration tester. Given a mission and optional recon results, produce a structured attack plan as JSON.

Output ONLY valid JSON in this exact format:
{
  "steps": [
    {
      "step_id": 1,
      "action_type": "recon|exploit|payload_delivery|lateral_movement|post_ex",
      "tool": "tool_name",
      "target": "ip_or_hostname",
      "params": {},
      "risk_level": "LOW|MED|HIGH",
      "rationale": "brief reason for this step"
    }
  ]
}

Rules:
- action_type must be one of: recon, exploit, payload_delivery, lateral_movement, persistence, post_ex
- risk_level HIGH for: exploit, payload_delivery, lateral_movement, persistence
- risk_level LOW for passive recon; MED for active recon
- params must be a flat dict with string keys and string or integer values
- target must be a specific IP address or hostname"""


@dataclass
class PlanStep:
    step_id: int
    action_type: str
    tool: str
    target: str
    params: dict[str, str | int] = field(default_factory=dict)
    risk_level: str = "LOW"
    requires_approval: bool = False
    rationale: str = ""


@dataclass
class MissionPlan:
    mission: str
    steps: list[PlanStep] = field(default_factory=list)


class MissionPlanner:
    """Converts a natural-language mission into a structured, ordered attack plan."""

    def __init__(self, model: ModelInterface):
        self.model = model

    def plan(self, mission: str, recon_results: dict | None = None) -> MissionPlan:
        context = f"Mission: {mission}"
        if recon_results:
            context += f"\nRecon results: {json.dumps(recon_results, indent=2)}"
        raw = self.model.complete(SYSTEM_PROMPT, context)
        steps = self._parse(raw)
        for step in steps:
            if step.action_type in INTRUSIVE_ACTIONS:
                step.requires_approval = True
        return MissionPlan(mission=mission, steps=steps)

    def _parse(self, raw: str) -> list[PlanStep]:
        try:
            text = raw.strip()
            matches = _FENCE_RE.findall(text)
            if matches:
                text = matches[-1].strip()
            data = json.loads(text)
            return [
                PlanStep(
                    step_id=item["step_id"],
                    action_type=item["action_type"],
                    tool=item["tool"],
                    target=item["target"],
                    params=item.get("params", {}),
                    risk_level=item.get("risk_level", "LOW"),
                    rationale=item.get("rationale", ""),
                )
                for item in data.get("steps", [])
            ]
        except Exception as e:
            log.error("Failed to parse mission plan: %s | raw: %.200s", e, raw)
            return []
