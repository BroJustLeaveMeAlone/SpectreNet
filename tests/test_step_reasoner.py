from spectrenet.ai.step_reasoner import StepReasoner
from spectrenet.ai.mission_planner import PlanStep, INTRUSIVE_ACTIONS
from spectrenet.model.interface import ModelInterface


class EchoModel(ModelInterface):
    def __init__(self, response: str): self._response = response
    def complete(self, system_prompt, user_prompt): return self._response


NEXT_STEP_JSON = """{
  "step_id": 3,
  "action_type": "exploit",
  "tool": "ms17_010_eternalblue",
  "target": "10.0.0.1",
  "params": {"LHOST": "10.0.0.2"},
  "risk_level": "HIGH",
  "rationale": "port 445 open and unpatched"
}"""

DONE_JSON = '{"done": true, "rationale": "all targets compromised"}'


def test_step_reasoner_returns_plan_step():
    reasoner = StepReasoner(EchoModel(NEXT_STEP_JSON))
    state = {"hosts": [{"ip": "10.0.0.1", "ports": [{"port": 445}]}]}
    step = reasoner.next_step(state)
    assert isinstance(step, PlanStep)
    assert step.step_id == 3
    assert step.tool == "ms17_010_eternalblue"
    assert step.target == "10.0.0.1"


def test_step_reasoner_marks_intrusive_step_for_approval():
    reasoner = StepReasoner(EchoModel(NEXT_STEP_JSON))
    step = reasoner.next_step({})
    assert step.requires_approval is True  # exploit is intrusive


def test_step_reasoner_returns_none_when_done():
    reasoner = StepReasoner(EchoModel(DONE_JSON))
    step = reasoner.next_step({"completed": True})
    assert step is None


def test_step_reasoner_returns_none_on_bad_json():
    reasoner = StepReasoner(EchoModel("garbage response"))
    step = reasoner.next_step({})
    assert step is None


def test_step_reasoner_strips_markdown_fences():
    fenced = "```json\n" + NEXT_STEP_JSON + "\n```"
    reasoner = StepReasoner(EchoModel(fenced))
    step = reasoner.next_step({})
    assert step is not None
    assert step.tool == "ms17_010_eternalblue"
