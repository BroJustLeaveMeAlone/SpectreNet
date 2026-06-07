import json
import logging
import re
from spectrenet.model.interface import ModelInterface
from spectrenet.ai.mission_planner import PlanStep, INTRUSIVE_ACTIONS

log = logging.getLogger("spectrenet")

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)

SYSTEM_PROMPT = """You are an expert penetration tester. Given the current state of an engagement, decide the single best next action.

Output ONLY valid JSON:
{
  "step_id": <integer>,
  "action_type": "recon|exploit|payload_delivery|lateral_movement|post_ex",
  "tool": "tool_name",
  "target": "ip_or_hostname",
  "params": {},
  "risk_level": "LOW|MED|HIGH",
  "rationale": "why this is the best next step"
}

If the engagement is complete or no viable next step exists, output:
{"done": true, "rationale": "reason engagement is complete"}"""


class StepReasoner:
    """Given current session state, decides the optimal next action."""

    def __init__(self, model: ModelInterface):
        self.model = model

    def next_step(self, session_state: dict) -> PlanStep | None:
        context = f"Current engagement state:\n{json.dumps(session_state, indent=2)}"
        raw = self.model.complete(SYSTEM_PROMPT, context)
        return self._parse(raw)

    def _parse(self, raw: str) -> PlanStep | None:
        try:
            text = raw.strip()
            matches = _FENCE_RE.findall(text)
            if matches:
                text = matches[-1].strip()
            data = json.loads(text)
            if data.get("done"):
                return None
            step = PlanStep(
                step_id=data["step_id"],
                action_type=data["action_type"],
                tool=data["tool"],
                target=data["target"],
                params=data.get("params", {}),
                risk_level=data.get("risk_level", "LOW"),
                rationale=data.get("rationale", ""),
            )
            if step.action_type in INTRUSIVE_ACTIONS:
                step.requires_approval = True
            return step
        except Exception as e:
            log.error("Failed to parse step reasoner output: %s | raw: %.200s", e, raw)
            return None
