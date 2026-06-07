# tests/test_mission_planner.py
from spectrenet.ai.mission_planner import MissionPlanner, PlanStep, MissionPlan, INTRUSIVE_ACTIONS
from spectrenet.model.interface import ModelInterface


class EchoModel(ModelInterface):
    """Returns a canned JSON plan."""
    def __init__(self, response: str): self._response = response
    def complete(self, system_prompt, user_prompt): return self._response


VALID_PLAN_JSON = """
{
  "steps": [
    {
      "step_id": 1,
      "action_type": "recon",
      "tool": "nmap",
      "target": "10.0.0.1",
      "params": {"flags": "-sV"},
      "risk_level": "LOW",
      "rationale": "discover open ports"
    },
    {
      "step_id": 2,
      "action_type": "exploit",
      "tool": "ms17_010_eternalblue",
      "target": "10.0.0.1",
      "params": {"LHOST": "10.0.0.2", "LPORT": "4444"},
      "risk_level": "HIGH",
      "rationale": "SMB port open"
    }
  ]
}
"""


def test_mission_planner_returns_mission_plan():
    planner = MissionPlanner(EchoModel(VALID_PLAN_JSON))
    plan = planner.plan("compromise 10.0.0.1")
    assert isinstance(plan, MissionPlan)
    assert len(plan.steps) == 2


def test_mission_planner_parses_steps_correctly():
    planner = MissionPlanner(EchoModel(VALID_PLAN_JSON))
    plan = planner.plan("compromise 10.0.0.1")
    step1, step2 = plan.steps
    assert step1.step_id == 1
    assert step1.action_type == "recon"
    assert step1.tool == "nmap"
    assert step1.target == "10.0.0.1"
    assert step1.params == {"flags": "-sV"}
    assert step1.risk_level == "LOW"
    assert step2.action_type == "exploit"
    assert step2.risk_level == "HIGH"


def test_mission_planner_marks_intrusive_steps_for_approval():
    planner = MissionPlanner(EchoModel(VALID_PLAN_JSON))
    plan = planner.plan("compromise 10.0.0.1")
    recon_step = plan.steps[0]
    exploit_step = plan.steps[1]
    assert recon_step.requires_approval is False
    assert exploit_step.requires_approval is True


def test_mission_planner_returns_empty_plan_on_bad_json():
    planner = MissionPlanner(EchoModel("not valid json at all"))
    plan = planner.plan("do something")
    assert isinstance(plan, MissionPlan)
    assert plan.steps == []


def test_mission_planner_strips_markdown_fences():
    fenced = "```json\n" + VALID_PLAN_JSON.strip() + "\n```"
    planner = MissionPlanner(EchoModel(fenced))
    plan = planner.plan("test")
    assert len(plan.steps) == 2


def test_mission_planner_strips_fences_with_preamble():
    """Model output that has text with triple-backtick before the JSON block."""
    preamble = "Use ```code``` formatting. Here is the plan:\n"
    fenced = preamble + "```json\n" + VALID_PLAN_JSON.strip() + "\n```"
    planner = MissionPlanner(EchoModel(fenced))
    plan = planner.plan("test")
    assert len(plan.steps) == 2
