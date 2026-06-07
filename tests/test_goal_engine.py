import asyncio
import json
import pytest
from spectrenet.ai.goal_engine import GoalEngine
from spectrenet.ai.mission_planner import PlanStep
from spectrenet.model.interface import ModelInterface


# ── Fakes ────────────────────────────────────────────────────────────────────

class ScriptedModel(ModelInterface):
    """Returns preset JSON responses in order, then signals done."""
    def __init__(self, responses: list[str]):
        self._responses = iter(responses)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        try:
            return next(self._responses)
        except StopIteration:
            return '{"done": true, "rationale": "goal achieved"}'


RECON_STEP_JSON = """{
  "step_id": 1,
  "action_type": "recon",
  "tool": "nmap",
  "target": "10.0.0.1",
  "params": {},
  "risk_level": "LOW",
  "rationale": "discover open ports"
}"""

EXPLOIT_STEP_JSON = """{
  "step_id": 2,
  "action_type": "exploit",
  "tool": "ms17_010_eternalblue",
  "target": "10.0.0.1",
  "params": {"LHOST": "10.0.0.2"},
  "risk_level": "HIGH",
  "rationale": "port 445 open"
}"""


class FakeMsfBridge:
    def __init__(self, sessions=None):
        self._sessions = sessions or []
        self._connected = True

    def is_connected(self) -> bool:
        return self._connected

    def get_sessions(self):
        return self._sessions

    def get_session_interactor(self, session_id: str):
        from spectrenet.msf.session_interactor import SessionInteractor
        class FakeClient:
            class sessions:
                @staticmethod
                def session(sid):
                    class S:
                        type = "meterpreter"
                        def run_with_output(self, cmd):
                            return f"output of {cmd}"
                    return S()
        return SessionInteractor(FakeClient(), session_id)


class FakeExploitEngine:
    def __init__(self, msf_result=None):
        self._result = msf_result or {"success": True, "job_id": "42"}

    def run_msf(self, module_path: str, options: dict) -> dict:
        return self._result


# ── Tests ────────────────────────────────────────────────────────────────────

def test_set_goal_updates_goal():
    engine = GoalEngine(ScriptedModel([]), FakeExploitEngine(), FakeMsfBridge())
    engine.set_goal("compromise 10.0.0.1")
    assert engine._goal == "compromise 10.0.0.1"


def test_stop_sets_running_false():
    engine = GoalEngine(ScriptedModel([]), FakeExploitEngine(), FakeMsfBridge())
    engine._running = True
    engine.stop()
    assert engine._running is False


def test_handle_input_stop():
    engine = GoalEngine(ScriptedModel([]), FakeExploitEngine(), FakeMsfBridge())
    engine._running = True
    engine.handle_input("stop")
    assert engine._running is False


def test_handle_input_change_goal():
    engine = GoalEngine(ScriptedModel([]), FakeExploitEngine(), FakeMsfBridge())
    engine.set_goal("old goal")
    engine.handle_input("change goal to new goal")
    assert engine._goal == "new goal"


def test_handle_input_injects_guidance():
    events = []
    engine = GoalEngine(
        ScriptedModel([]), FakeExploitEngine(), FakeMsfBridge(),
        on_event=events.append
    )
    engine.handle_input("focus on credential dumping")
    assert engine._state.get("operator_guidance") == "focus on credential dumping"


@pytest.mark.asyncio
async def test_goal_engine_emits_success_on_done():
    events = []
    engine = GoalEngine(
        ScriptedModel([]),  # immediately returns done
        FakeExploitEngine(),
        FakeMsfBridge(),
        on_event=events.append,
    )
    engine.set_goal("test goal")
    await engine.start()
    types = [e["type"] for e in events]
    assert "success" in types


@pytest.mark.asyncio
async def test_goal_engine_executes_recon_step():
    events = []
    engine = GoalEngine(
        ScriptedModel([RECON_STEP_JSON]),
        FakeExploitEngine(),
        FakeMsfBridge(),
        on_event=events.append,
    )
    engine.set_goal("recon test")
    await engine.start()
    types = [e["type"] for e in events]
    assert "step" in types
    assert "success" in types


@pytest.mark.asyncio
async def test_goal_engine_emits_dead_end_after_three_failed_exploits():
    events = []
    # 3 exploit steps, no new sessions open → dead end
    engine = GoalEngine(
        ScriptedModel([EXPLOIT_STEP_JSON, EXPLOIT_STEP_JSON, EXPLOIT_STEP_JSON]),
        FakeExploitEngine({"success": True, "job_id": "1"}),
        FakeMsfBridge(sessions=[]),  # no sessions ever open
        on_event=events.append,
        session_poll_timeout=0,  # skip polling in tests
        auto_approve=True,  # bypass approval gate; focus on dead-end logic
    )
    engine.set_goal("dead end test")
    await engine.start()
    types = [e["type"] for e in events]
    assert "dead_end" in types


@pytest.mark.asyncio
async def test_goal_engine_pauses_for_approval_and_resumes():
    events = []
    engine = GoalEngine(
        ScriptedModel([EXPLOIT_STEP_JSON]),
        FakeExploitEngine({"success": False, "error": "failed"}),
        FakeMsfBridge(sessions=[]),
        on_event=events.append,
        session_poll_timeout=0,
    )
    engine.set_goal("approval test")

    async def deny_async() -> None:
        await asyncio.sleep(0)  # yield to let engine reach _wait_for_approval
        engine.set_approval_result("N")

    await asyncio.gather(engine.start(), deny_async())
    types = [e["type"] for e in events]
    assert "approval_required" in types
    assert "step_skipped" in types


# ── Phase 4: recon execution + replanning tests ───────────────────────────────

class FakeReconEngine:
    def __init__(self, result: dict):
        self._result = result
        self.calls: list[dict] = []

    def scan(self, tool: str, target: str, **kwargs) -> dict:
        self.calls.append({"tool": tool, "target": target})
        return self._result


@pytest.mark.asyncio
async def test_goal_engine_executes_recon_when_engine_injected():
    recon_result = {
        "hosts": [{"ip": "10.10.10.5", "ports": [
            {"port": 445, "service": "microsoft-ds", "version": "4.6"}
        ]}]
    }
    fake_recon = FakeReconEngine(recon_result)

    events: list[dict] = []
    engine = GoalEngine(
        model=ScriptedModel([RECON_STEP_JSON]),
        exploit_engine=FakeExploitEngine(),
        msf_bridge=FakeMsfBridge(sessions=[]),
        recon_engine=fake_recon,
        on_event=events.append,
        session_poll_timeout=0,
        auto_approve=True,
    )
    engine.set_goal("find hosts on 10.10.10.5")
    await engine.start()

    assert len(fake_recon.calls) == 1
    assert any(e["type"] == "recon_complete" for e in events)


@pytest.mark.asyncio
async def test_goal_engine_injects_failed_steps_detail_on_exploit_failure():
    events: list[dict] = []
    engine = GoalEngine(
        model=ScriptedModel([EXPLOIT_STEP_JSON]),
        exploit_engine=FakeExploitEngine({"success": False, "error": "module failed"}),
        msf_bridge=FakeMsfBridge(sessions=[]),
        on_event=events.append,
        session_poll_timeout=0,
        auto_approve=True,
    )
    engine.set_goal("exploit smb")
    await engine.start()

    assert "failed_steps_detail" in engine._state
    assert len(engine._state["failed_steps_detail"]) >= 1


@pytest.mark.asyncio
async def test_goal_engine_emits_recon_complete_with_count():
    recon_result = {
        "hosts": [{"ip": "192.168.1.1", "ports": [
            {"port": 80, "service": "http", "version": "Apache 2.4"}
        ]}]
    }
    fake_recon = FakeReconEngine(recon_result)

    events: list[dict] = []
    engine = GoalEngine(
        model=ScriptedModel([RECON_STEP_JSON]),
        exploit_engine=FakeExploitEngine(),
        msf_bridge=FakeMsfBridge(sessions=[]),
        recon_engine=fake_recon,
        on_event=events.append,
        session_poll_timeout=0,
        auto_approve=True,
    )
    engine.set_goal("recon 192.168.1.1")
    await engine.start()

    rc = [e for e in events if e["type"] == "recon_complete"]
    assert rc
    assert rc[0]["count"] == 1
