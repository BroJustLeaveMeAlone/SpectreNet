# SpectreNet Phase 3 — Goal-Directed AI Loop & Session Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add autonomous goal-directed AI loop, MSF session interaction, and a fully redesigned TUI with real-time styled activity feed and natural-language `ai>` CLI.

**Architecture:** `MsfConsole` wraps pymetasploit3's RPC console API; `SessionInteractor` wraps active MSF sessions for post-ex commands; `GoalEngine` runs an async loop using `StepReasoner` to plan, `ExploitEngine` to execute, and `SessionInteractor` for post-ex — accumulating state and feeding it back for the next reasoning cycle. The TUI gets a `GoalPanel` widget, a styled activity feed with event blocks, and an `ai>` input that routes to `GoalEngine` when running or a classic command parser when stopped.

**Tech Stack:** Python 3.13, Textual, pymetasploit3 (optional, injectable), pytest, pytest-asyncio 1.3

---

## File Map

**New files:**
- `spectrenet/msf/console.py` — `MsfConsole`: send commands via RPC console, poll for output
- `spectrenet/msf/session_interactor.py` — `SessionInteractor`: run commands in active MSF sessions
- `spectrenet/ai/goal_engine.py` — `GoalEngine`: async autonomous goal-directed loop
- `spectrenet/tui/goal_panel.py` — `GoalPanel`: Textual Static widget showing goal + AI status
- `spectrenet/tui/session_panel.py` — `SessionPanel`: session interaction widget (terminal + menu mode)
- `tests/test_msf_console.py`
- `tests/test_session_interactor.py`
- `tests/test_goal_engine.py`

**Modified files:**
- `spectrenet/msf/bridge.py` — add `get_session_interactor(session_id)` factory
- `spectrenet/tui/app.py` — new layout + activity feed + ai> routing + GoalEngine integration

---

## Task 1: MsfConsole

**Files:**
- Create: `spectrenet/msf/console.py`
- Test: `tests/test_msf_console.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_msf_console.py
import pytest
from spectrenet.msf.console import MsfConsole


class FakeConsoleObj:
    """Simulates a pymetasploit3 console object."""
    def __init__(self, responses: list[dict]):
        self._responses = iter(responses)
        self.written: list[str] = []
        self.destroyed = False

    def write(self, text: str) -> None:
        self.written.append(text)

    def read(self) -> dict:
        return next(self._responses)

    def destroy(self) -> None:
        self.destroyed = True


class FakeConsoles:
    def __init__(self, console_obj: FakeConsoleObj):
        self._console = console_obj

    def console(self) -> FakeConsoleObj:
        return self._console


class FakeClient:
    def __init__(self, console_obj: FakeConsoleObj):
        self.consoles = FakeConsoles(console_obj)


def test_open_returns_true_with_injected_client():
    obj = FakeConsoleObj([])
    con = MsfConsole(client=FakeClient(obj))
    assert con.open() is True


def test_open_returns_false_on_exception():
    class BrokenClient:
        class consoles:
            @staticmethod
            def console():
                raise RuntimeError("no daemon")
    con = MsfConsole(client=BrokenClient())
    assert con.open() is False


def test_send_returns_output_when_not_busy():
    obj = FakeConsoleObj([
        {"data": "msf output\n", "busy": False},
    ])
    con = MsfConsole(client=FakeClient(obj))
    con.open()
    result = con.send("version")
    assert result == "msf output\n"
    assert "version\n" in obj.written


def test_send_polls_until_not_busy():
    obj = FakeConsoleObj([
        {"data": "partial...", "busy": True},
        {"data": "done\n", "busy": False},
    ])
    con = MsfConsole(client=FakeClient(obj), poll_interval=0)
    con.open()
    result = con.send("use exploit/multi/handler")
    assert result == "partial...done\n"


def test_close_destroys_console():
    obj = FakeConsoleObj([])
    con = MsfConsole(client=FakeClient(obj))
    con.open()
    con.close()
    assert obj.destroyed is True


def test_send_before_open_returns_empty():
    obj = FakeConsoleObj([])
    con = MsfConsole(client=FakeClient(obj))
    result = con.send("anything")
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_msf_console.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectrenet.msf.console'`

- [ ] **Step 3: Write the implementation**

```python
# spectrenet/msf/console.py
import logging
import time

log = logging.getLogger("spectrenet")


class MsfConsole:
    """Wraps pymetasploit3's RPC console API. Client is injectable for tests."""

    def __init__(self, client=None, poll_interval: float = 0.5):
        self._client = client
        self._console = None
        self._poll_interval = poll_interval

    def open(self) -> bool:
        try:
            self._console = self._client.consoles.console()
            return True
        except Exception as e:
            log.warning("Failed to open MSF console: %s", e)
            return False

    def send(self, command: str) -> str:
        if self._console is None:
            return ""
        self._console.write(command + "\n")
        output = ""
        while True:
            result = self._console.read()
            output += result.get("data", "")
            if not result.get("busy", True):
                break
            if self._poll_interval > 0:
                time.sleep(self._poll_interval)
        return output

    def close(self) -> None:
        if self._console is not None:
            self._console.destroy()
            self._console = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_msf_console.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add spectrenet/msf/console.py tests/test_msf_console.py
git commit -m "feat: add MsfConsole RPC console wrapper"
```

---

## Task 2: SessionInteractor + MsfBridge factory

**Files:**
- Create: `spectrenet/msf/session_interactor.py`
- Modify: `spectrenet/msf/bridge.py`
- Test: `tests/test_session_interactor.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_session_interactor.py
import pytest
from spectrenet.msf.session_interactor import SessionInteractor


class FakeMeterpreterSession:
    type = "meterpreter"

    def __init__(self, outputs: list[str]):
        self._outputs = iter(outputs)

    def run_with_output(self, command: str) -> str:
        return next(self._outputs)


class FakeShellSession:
    type = "shell"

    def __init__(self, outputs: list[str]):
        self._outputs = iter(outputs)
        self.written: list[str] = []

    def write(self, text: str) -> None:
        self.written.append(text)

    def read(self) -> str:
        return next(self._outputs)


class FakeSessions:
    def __init__(self, session_obj):
        self._session = session_obj

    def session(self, sid: str):
        return self._session


class FakeClient:
    def __init__(self, session_obj):
        self.sessions = FakeSessions(session_obj)


def test_session_type_meterpreter():
    s = SessionInteractor(FakeClient(FakeMeterpreterSession([])), "1")
    assert s.session_type() == "meterpreter"


def test_session_type_shell():
    s = SessionInteractor(FakeClient(FakeShellSession([])), "2")
    assert s.session_type() == "shell"


def test_run_meterpreter_returns_output():
    sess = FakeMeterpreterSession(["NT AUTHORITY\\SYSTEM"])
    s = SessionInteractor(FakeClient(sess), "1")
    assert s.run("getuid") == "NT AUTHORITY\\SYSTEM"


def test_run_shell_returns_output():
    sess = FakeShellSession(["root\n"])
    s = SessionInteractor(FakeClient(sess), "1")
    result = s.run("id")
    assert result == "root\n"
    assert "id\n" in sess.written


def test_run_handles_exception_gracefully():
    class BrokenSession:
        type = "meterpreter"
        def run_with_output(self, cmd):
            raise RuntimeError("session dead")

    s = SessionInteractor(FakeClient(BrokenSession()), "1")
    result = s.run("getuid")
    assert "error" in result.lower() or result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_session_interactor.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the SessionInteractor implementation**

```python
# spectrenet/msf/session_interactor.py
import logging

log = logging.getLogger("spectrenet")


class SessionInteractor:
    """Send commands to and read output from an active Metasploit session."""

    def __init__(self, client, session_id: str):
        self._client = client
        self._session_id = session_id

    def session_type(self) -> str:
        return self._client.sessions.session(self._session_id).type

    def run(self, command: str) -> str:
        try:
            sess = self._client.sessions.session(self._session_id)
            if sess.type == "meterpreter":
                return sess.run_with_output(command)
            else:
                sess.write(command + "\n")
                return sess.read()
        except Exception as e:
            log.error("Session %s command failed: %s", self._session_id, e)
            return f"[error: {e}]"
```

- [ ] **Step 4: Add `get_session_interactor()` to `MsfBridge`**

Read `spectrenet/msf/bridge.py` first, then append this method to the `MsfBridge` class (after the `get_sessions` method):

```python
    def get_session_interactor(self, session_id: str) -> "SessionInteractor":
        from spectrenet.msf.session_interactor import SessionInteractor
        return SessionInteractor(self._client, session_id)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_session_interactor.py tests/test_msf_bridge.py -v`
Expected: all pass (5 new + 6 existing)

- [ ] **Step 6: Commit**

```bash
git add spectrenet/msf/session_interactor.py spectrenet/msf/bridge.py tests/test_session_interactor.py
git commit -m "feat: add SessionInteractor and MsfBridge.get_session_interactor()"
```

---

## Task 3: GoalEngine

**Files:**
- Create: `spectrenet/ai/goal_engine.py`
- Test: `tests/test_goal_engine.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_goal_engine.py
import asyncio
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_goal_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the GoalEngine implementation**

```python
# spectrenet/ai/goal_engine.py
import asyncio
import logging
from typing import Any, Callable

from spectrenet.ai.step_reasoner import StepReasoner
from spectrenet.model.interface import ModelInterface

log = logging.getLogger("spectrenet")

POST_EX_COMMANDS = ["getuid", "sysinfo"]


class GoalEngine:
    """Autonomous goal-directed AI loop. Runs as a Textual background worker."""

    def __init__(
        self,
        model: ModelInterface,
        exploit_engine: Any,
        msf_bridge: Any,
        on_event: Callable[[dict], None] | None = None,
        session_poll_timeout: int = 60,
        auto_approve: bool = False,
    ):
        self._model = model
        self._exploit_engine = exploit_engine
        self._msf_bridge = msf_bridge
        self._on_event = on_event or (lambda e: None)
        self._session_poll_timeout = session_poll_timeout
        self._auto_approve = auto_approve
        self._goal: str = ""
        self._state: dict = {}
        self._running: bool = False
        self._no_progress_count: int = 0
        self._skip_current: bool = False
        self._approval_event = asyncio.Event()
        self._approval_result: str | None = None
        self._reasoner = StepReasoner(model)

    def set_goal(self, goal: str) -> None:
        self._goal = goal.strip()
        self._state = {"goal": self._goal, "sessions": [], "failed_steps": []}
        self._no_progress_count = 0

    def stop(self) -> None:
        self._running = False

    def set_approval_result(self, result: str) -> None:
        self._approval_result = result
        self._approval_event.set()

    def handle_input(self, text: str) -> None:
        t = text.strip().lower()
        if t == "stop":
            self.stop()
        elif " to " in t and ("goal" in t or "change" in t):
            new_goal = t.split(" to ", 1)[1].strip()
            self.set_goal(new_goal)
            self._emit("goal_changed", goal=self._goal)
        elif t in ("skip", "skip this step", "skip this"):
            self._skip_current = True
        elif t in ("?", "status", "what are you doing", "what are you doing?"):
            self._emit("ai_thinking", text=f"Goal: {self._goal}. No-progress count: {self._no_progress_count}/3.")
        else:
            self._state["operator_guidance"] = text
            self._emit("ai_thinking", text=f"Got it: {text}")

    async def start(self) -> None:
        self._running = True
        self._emit("mission_start", goal=self._goal)

        while self._running and self._goal:
            self._skip_current = False
            step = self._reasoner.next_step(self._state)

            if step is None:
                self._emit("success", goal=self._goal)
                break

            self._emit("step", step_id=step.step_id, action_type=step.action_type,
                       tool=step.tool, target=step.target)

            if step.requires_approval:
                self._emit("approval_required", step_id=step.step_id,
                           action=step.action_type, tool=step.tool,
                           target=step.target, risk=step.risk_level,
                           reason=step.rationale)
                if not self._auto_approve:
                    await self._wait_for_approval()
                    result = self._approval_result
                    self._approval_result = None
                    if result != "Y":
                        self._emit("step_skipped", step_id=step.step_id)
                        self._no_progress_count += 1
                        if self._no_progress_count >= 3:
                            self._emit("dead_end", suggestion="Try a different attack vector or change goal.")
                            break
                        continue

            if self._skip_current:
                self._emit("step_skipped", step_id=step.step_id)
                continue

            if step.action_type == "recon":
                self._state.setdefault("recon", []).append(
                    {"tool": step.tool, "target": step.target}
                )
                self._emit("step_complete", step_id=step.step_id, output=f"recon queued: {step.tool} → {step.target}")
                self._no_progress_count = 0
            else:
                await self._run_exploit_step(step)

            if self._no_progress_count >= 3:
                self._emit("dead_end", suggestion="Try a different attack vector or change goal.")
                break

        self._running = False

    async def _run_exploit_step(self, step) -> None:
        prev_ids = {s.id for s in self._msf_bridge.get_sessions()}
        options = {"RHOSTS": step.target, **step.params}
        result = self._exploit_engine.run_msf(step.tool, options)

        if not result.get("success"):
            self._emit("step_failed", step_id=step.step_id, error=result.get("error", "unknown"))
            self._no_progress_count += 1
            self._state.setdefault("failed_steps", []).append(step.step_id)
            return

        new_session = await self._poll_for_session(prev_ids)
        if new_session is None:
            self._emit("step_failed", step_id=step.step_id, error="no session opened within timeout")
            self._no_progress_count += 1
            self._state.setdefault("failed_steps", []).append(step.step_id)
            return

        self._no_progress_count = 0
        self._state["sessions"].append(new_session.id)
        self._emit("session_opened", session_id=new_session.id, session_type=new_session.type)
        await self._run_post_ex(new_session)

    async def _poll_for_session(self, prev_ids: set[str]):
        if self._session_poll_timeout == 0:
            return None
        iterations = self._session_poll_timeout // 2
        for _ in range(max(iterations, 1)):
            await asyncio.sleep(2)
            current = self._msf_bridge.get_sessions()
            new = [s for s in current if s.id not in prev_ids]
            if new:
                return new[0]
        return None

    async def _run_post_ex(self, session) -> None:
        interactor = self._msf_bridge.get_session_interactor(session.id)
        for cmd in POST_EX_COMMANDS:
            try:
                output = interactor.run(cmd)
                self._state.setdefault("post_ex", []).append({"cmd": cmd, "output": output})
                self._emit("post_ex", command=cmd, output=output, session_id=session.id)
            except Exception as e:
                self._emit("post_ex_error", command=cmd, error=str(e), session_id=session.id)

    async def _wait_for_approval(self) -> None:
        self._approval_event.clear()
        self._approval_result = None
        await self._approval_event.wait()

    def _emit(self, event_type: str, **data) -> None:
        self._on_event({"type": event_type, **data})
```

- [ ] **Step 4: Add `asyncio_mode` to pyproject.toml**

Read `pyproject.toml`, then add `asyncio_mode = "auto"` under `[tool.pytest.ini_options]` so `@pytest.mark.asyncio` tests run without needing `asyncio_default_fixture_loop_scope`. The section should look like:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v"
asyncio_mode = "auto"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_goal_engine.py -v`
Expected: 9 passed

- [ ] **Step 6: Run full suite to confirm no regressions**

Run: `python -m pytest tests/ -v`
Expected: all prior tests still pass

- [ ] **Step 7: Commit**

```bash
git add spectrenet/ai/goal_engine.py tests/test_goal_engine.py pyproject.toml
git commit -m "feat: add GoalEngine autonomous goal-directed AI loop"
```

---

## Task 4: GoalPanel TUI Widget

**Files:**
- Create: `spectrenet/tui/goal_panel.py`

- [ ] **Step 1: Write the implementation**

No unit tests — smoke-verified in Task 6. Write directly:

```python
# spectrenet/tui/goal_panel.py
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
```

- [ ] **Step 2: Commit**

```bash
git add spectrenet/tui/goal_panel.py
git commit -m "feat: add GoalPanel Textual widget"
```

---

## Task 5: SessionPanel TUI Widget

**Files:**
- Create: `spectrenet/tui/session_panel.py`

- [ ] **Step 1: Write the implementation**

```python
# spectrenet/tui/session_panel.py
from textual.app import ComposeResult
from textual.widgets import Static, Input, RichLog
from textual.containers import Vertical
from spectrenet.theme import CYAN

_MENU_ACTIONS = [
    ("getuid",    "Who am I?"),
    ("sysinfo",   "System info"),
    ("hashdump",  "Dump password hashes"),
    ("ps",        "List processes"),
    ("pwd",       "Print working directory"),
    ("ls",        "List files"),
]


class SessionPanel(Vertical):
    """Overlay for interacting with an active session.

    Two modes:
      - terminal (default): raw command input → SessionInteractor.run()
      - menu: numbered list of common post-ex actions, selected by number
    """

    DEFAULT_CSS = f"""
    SessionPanel {{
        border: round {CYAN};
        height: 16;
        margin: 1;
    }}
    """

    def __init__(self, interactor, **kwargs):
        super().__init__(**kwargs)
        self._interactor = interactor
        self._menu_mode = False

    def compose(self) -> ComposeResult:
        self._log = RichLog(highlight=True, markup=True)
        yield self._log
        yield Input(placeholder="cmd> (type ? for menu, /exit to close)")

    def on_mount(self) -> None:
        stype = self._interactor.session_type()
        self._log.write(f"[{CYAN}]Session opened ({stype}). Type ? to toggle menu mode.[/]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.value = ""
        if not raw:
            return
        if raw == "?":
            self._toggle_menu()
            return
        if raw == "/exit":
            self.remove()
            return
        if self._menu_mode:
            self._handle_menu_input(raw)
        else:
            self._handle_terminal_input(raw)

    def _toggle_menu(self) -> None:
        self._menu_mode = not self._menu_mode
        if self._menu_mode:
            lines = [f"[{CYAN}]── Post-Ex Menu ──[/]"]
            for i, (cmd, label) in enumerate(_MENU_ACTIONS, 1):
                lines.append(f"  [{CYAN}]{i}[/] {label}  [{cmd}]")
            lines.append("  Enter a number or type ? to return to terminal mode.")
            self._log.write("\n".join(lines))
        else:
            self._log.write(f"[{CYAN}]Terminal mode.[/]")

    def _handle_menu_input(self, raw: str) -> None:
        try:
            idx = int(raw) - 1
            cmd, _ = _MENU_ACTIONS[idx]
            self._run_command(cmd)
        except (ValueError, IndexError):
            self._log.write("[red]Invalid selection.[/]")

    def _handle_terminal_input(self, raw: str) -> None:
        self._run_command(raw)

    def _run_command(self, cmd: str) -> None:
        self._log.write(f"[dim]> {cmd}[/]")
        try:
            output = self._interactor.run(cmd)
            self._log.write(output or "[dim](no output)[/]")
        except Exception as e:
            self._log.write(f"[red]error: {e}[/]")
```

- [ ] **Step 2: Commit**

```bash
git add spectrenet/tui/session_panel.py
git commit -m "feat: add SessionPanel with terminal and menu mode"
```

---

## Task 6: TUI Integration

**Files:**
- Modify: `spectrenet/tui/app.py` (full rewrite)

- [ ] **Step 1: Read the current `spectrenet/tui/app.py`** to get exact content

Run: `python -c "import spectrenet.tui.app; print('imports ok')"` to confirm current state.

- [ ] **Step 2: Write the updated `spectrenet/tui/app.py`**

```python
# spectrenet/tui/app.py
import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
from textual.containers import Vertical
from spectrenet import APP_NAME, TAGLINE, __version__
from spectrenet.theme import BANNER, CYAN, NAVY_DEEP
from spectrenet.tui.command_parser import parse_command
from spectrenet.tui.approval_gate import ActionCard, ApprovalResult, format_action_card
from spectrenet.tui.goal_panel import GoalPanel


class SpectreNetApp(App):
    CSS = f"""
    Screen {{ background: {NAVY_DEEP}; }}
    GoalPanel {{ background: {NAVY_DEEP}; border-bottom: solid {CYAN}; padding: 0 1; height: 1; }}
    RichLog {{ border: round {CYAN}; height: 1fr; }}
    Input {{ border: round {CYAN}; }}
    """
    TITLE = APP_NAME
    SUB_TITLE = TAGLINE

    def __init__(self, registry, recon, model=None, msf_bridge=None, **kwargs):
        super().__init__(**kwargs)
        self.registry = registry
        self.recon = recon
        self.model = model
        self.msf_bridge = msf_bridge
        self._goal_engine = None
        self._approval_event: asyncio.Event | None = None
        self._approval_result: ApprovalResult | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        self.goal_panel = GoalPanel()
        yield self.goal_panel
        with Vertical():
            self.feed = RichLog(highlight=True, markup=True, id="feed")
            yield self.feed
            yield Input(placeholder="ai> goal <objective> | scan <target> | stop | help | quit")
        yield Footer()

    def on_mount(self) -> None:
        self.feed.write(f"[bold {CYAN}]{BANNER}[/]")
        self.feed.write(f"[{CYAN}]{APP_NAME} v{__version__}[/] — {TAGLINE}")
        self.feed.write(f"Wrappers: {', '.join(self.registry.available()) or 'none'}")
        ai_status = "active" if self.model else "inactive (classic mode)"
        self.feed.write(f"AI: {ai_status}")
        self.feed.write(f"[dim]Set a goal: goal <objective>  |  scan <target>  |  help[/]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.value = ""
        if not raw:
            return

        # Approval gate intercept
        if self._approval_event is not None:
            key = raw.upper()
            if key in ("Y", "N", "S"):
                self._approval_result = ApprovalResult(key)
                if self._goal_engine is not None:
                    self._goal_engine.set_approval_result(key)
                self._approval_event.set()
            else:
                self.feed.write("[yellow]Approval pending — enter Y (approve), N (deny), or S (skip)[/]")
            return

        # Route to GoalEngine when running
        if self._goal_engine is not None and self._goal_engine._running:
            self._goal_engine.handle_input(raw)
            return

        # Classic command parser
        if raw.lower().startswith("goal "):
            objective = raw[5:].strip()
            if not objective:
                self.feed.write("[red]usage: goal <objective>[/]")
                return
            self._start_goal(objective)
            return

        cmd = parse_command(raw)
        if cmd is None:
            return
        if cmd.verb in ("quit", "exit"):
            self.exit()
        elif cmd.verb == "stop":
            if self._goal_engine:
                self._goal_engine.stop()
                self.goal_panel.update_goal(self._goal_engine._goal, "STOPPED")
                self.feed.write(f"[{CYAN}]AI stopped.[/]")
        elif cmd.verb == "help":
            self.feed.write(
                "Commands: goal <objective>, scan <target> [--tool nmap|masscan], "
                "stop, wrappers, help, quit"
            )
        elif cmd.verb == "wrappers":
            self.feed.write("Registered: " + ", ".join(self.registry.names()))
        elif cmd.verb == "scan":
            self._do_scan(cmd)
        else:
            self.feed.write(f"[red]Unknown command:[/] {cmd.verb}")

    def _start_goal(self, objective: str) -> None:
        if self.model is None:
            self.feed.write("[red]AI mode not active.[/] Start with --model ollama to enable.")
            return
        from spectrenet.ai.goal_engine import GoalEngine
        from spectrenet.engines.exploit import ExploitEngine
        from spectrenet.engines.exploit_modules.registry import ExploitModuleRegistry

        module_registry = ExploitModuleRegistry()
        module_registry.discover()
        exploit_engine = ExploitEngine(module_registry, self.msf_bridge)

        self._goal_engine = GoalEngine(
            model=self.model,
            exploit_engine=exploit_engine,
            msf_bridge=self.msf_bridge,
            on_event=self._on_goal_event,
        )
        self._goal_engine.set_goal(objective)
        self.goal_panel.update_goal(objective, "RUNNING")
        self.run_worker(self._goal_engine.start(), exclusive=True)

    def _on_goal_event(self, event: dict) -> None:
        etype = event["type"]

        if etype == "mission_start":
            self.feed.write(f"\n  [{CYAN}]◈ MISSION ACTIVE[/] ─────────────────────────────")
            self.feed.write(f"  [{CYAN}]Goal:[/] {event.get('goal', '')}")

        elif etype == "step":
            action = event.get("action_type", "")
            tool = event.get("tool", "")
            target = event.get("target", "")
            color = {"recon": CYAN, "exploit": "yellow", "payload_delivery": "red"}.get(action, "white")
            self.feed.write(f"\n  [bold {color}]▸ {action.upper():<10}[/] {tool} → {target}  [dim]⟳[/]")

        elif etype == "step_complete":
            output = event.get("output", "")
            self.feed.write(f"    [dim]{output}[/]  [{CYAN}]✓[/]")

        elif etype == "step_failed":
            self.feed.write(f"    [red]✗ {event.get('error', 'failed')}[/]")

        elif etype == "step_skipped":
            self.feed.write(f"    [yellow]⊘ step {event.get('step_id')} skipped[/]")

        elif etype == "session_opened":
            sid = event.get("session_id", "?")
            stype = event.get("session_type", "unknown")
            self.feed.write(f"    [green]► Session {sid} opened [{stype}][/]")

        elif etype == "post_ex":
            cmd = event.get("command", "")
            output = event.get("output", "").strip()
            self.feed.write(f"  [dim]┌─ POST-EX[/]")
            self.feed.write(f"  [dim]│[/] {cmd:<12}→  [white]{output}[/]")
            self.feed.write(f"  [dim]└{'─' * 40}[/]")

        elif etype == "approval_required":
            card = ActionCard(
                action=f"{event.get('action')}/{event.get('tool')}",
                target=event.get("target", ""),
                module=event.get("tool", ""),
                risk=event.get("risk", "HIGH"),
                reason=event.get("reason", "AI-planned intrusive action"),
            )
            self._approval_event = asyncio.Event()
            self.feed.write(format_action_card(card))

        elif etype == "success":
            self.feed.write(f"\n  [{CYAN}]◈[/] [green bold]MISSION COMPLETE[/] — goal achieved")
            self.goal_panel.update_goal(self._goal_engine._goal, "SUCCESS")

        elif etype == "dead_end":
            suggestion = event.get("suggestion", "")
            self.feed.write(f"\n  [yellow]◈ DEAD END[/] — {suggestion}")
            self.goal_panel.update_goal(self._goal_engine._goal, "DEAD END")

        elif etype == "ai_thinking":
            text = event.get("text", "")
            self.feed.write(f"  [dim italic {CYAN}]◈ AI  {text}[/]")

        elif etype == "goal_changed":
            new_goal = event.get("goal", "")
            self.goal_panel.update_goal(new_goal, "RUNNING")
            self.feed.write(f"  [{CYAN}]◈ Goal updated:[/] {new_goal}")

    def _do_scan(self, cmd) -> None:
        if not cmd.args:
            self.feed.write("[red]scan requires a target[/]")
            return
        tool = cmd.flags.get("tool", "nmap")
        target = cmd.args[0]
        try:
            result = self.recon.scan(tool=tool, target=target)
            self.feed.write(f"\n  [{CYAN}]▸ RECON      {tool} → {target}[/]")
            for host in result["hosts"]:
                for p in host["ports"]:
                    self.feed.write(f"    ├─ {p['port']}/tcp  open")
        except Exception as e:
            self.feed.write(f"[red]scan failed:[/] {e}")
```

- [ ] **Step 3: Update `spectrenet/cli.py`** to pass `msf_bridge` to the TUI:

Read `spectrenet/cli.py` first, then replace the full file with:

```python
# spectrenet/cli.py
import argparse
from pathlib import Path
from spectrenet.config import load_config
from spectrenet.logging_setup import setup_logging
from spectrenet.wrappers.registry import WrapperRegistry
from spectrenet.engines.recon import ReconEngine
from spectrenet.tui.app import SpectreNetApp


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="spectrenet", description="SpectreNet — Always one step ahead"
    )
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--model", choices=["ollama", "none"], default=None,
                        help="AI model backend (overrides config)")
    parser.add_argument("--msf-host", default="127.0.0.1", help="msfrpcd host")
    parser.add_argument("--msf-port", type=int, default=55553, help="msfrpcd port")
    parser.add_argument("--msf-password", default="msf", help="msfrpcd password")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    log = setup_logging(cfg.log_level)
    log.info("Starting SpectreNet (operator=%s)", cfg.operator_name)

    registry = WrapperRegistry()
    registry.discover()
    recon = ReconEngine(registry)

    model = None
    backend = args.model or cfg.model_backend
    if backend == "ollama":
        try:
            from spectrenet.model.ollama_backend import OllamaBackend
            model = OllamaBackend(model=cfg.model_name, url=cfg.ollama_url)
            log.info("AI mode: Ollama (%s)", cfg.model_name)
        except Exception as e:
            log.warning("Failed to initialise Ollama backend: %s — running in Classic mode", e)

    msf_bridge = None
    try:
        from spectrenet.msf.bridge import MsfBridge
        msf_bridge = MsfBridge(
            host=args.msf_host,
            port=args.msf_port,
            password=args.msf_password,
        )
        msf_bridge.connect()
    except Exception as e:
        log.warning("MSF bridge unavailable: %s", e)

    SpectreNetApp(registry=registry, recon=recon, model=model, msf_bridge=msf_bridge).run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Smoke-verify the updated TUI constructs**

```python
# Save as _smoke_p3.py and run: python _smoke_p3.py
from spectrenet.wrappers.registry import WrapperRegistry
from spectrenet.engines.recon import ReconEngine
from spectrenet.tui.app import SpectreNetApp
from spectrenet.tui.goal_panel import GoalPanel
from spectrenet.tui.session_panel import SessionPanel
from spectrenet.ai.goal_engine import GoalEngine

r = WrapperRegistry()
r.discover()
app = SpectreNetApp(registry=r, recon=ReconEngine(r), model=None)
print("app constructed (classic mode)")

gp = GoalPanel()
gp.update_goal("test goal", "RUNNING")
print(f"goal panel render: {gp.render()}")
assert "RUNNING" in gp.render()
print("goal panel: ok")
print("Phase 3 smoke: PASS")
```

Run: `python _smoke_p3.py`
Expected output: `app constructed (classic mode)`, `goal panel: ok`, `Phase 3 smoke: PASS`
Delete `_smoke_p3.py` after.

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add spectrenet/tui/app.py spectrenet/cli.py
git commit -m "feat: redesign TUI with goal panel, activity feed, and GoalEngine integration"
```

---

## Task 7: Phase 3 DoD + Full Suite

**Files:** No new files — verification only.

- [ ] **Step 1: Run full suite with coverage**

Run: `python -m pytest tests/ --cov=spectrenet --cov-report=term-missing`
Expected: all tests pass; `msf/console.py`, `msf/session_interactor.py`, `ai/goal_engine.py`, `tui/goal_panel.py` show high coverage.

- [ ] **Step 2: DoD — MsfConsole round-trip**

```python
# _dod_p3.py
from spectrenet.msf.console import MsfConsole

class FakeConsoleObj:
    def __init__(self): self.written = []
    def write(self, t): self.written.append(t)
    def read(self): return {"data": "Metasploit 6.x\n", "busy": False}
    def destroy(self): pass

class FakeConsoles:
    def __init__(self, obj): self._obj = obj
    def console(self): return self._obj

class FakeClient:
    def __init__(self, obj): self.consoles = FakeConsoles(obj)

obj = FakeConsoleObj()
con = MsfConsole(client=FakeClient(obj), poll_interval=0)
assert con.open() is True
output = con.send("version")
assert "Metasploit" in output
con.close()
print("MsfConsole: PASS")
```

Run: `python _dod_p3.py`

- [ ] **Step 3: DoD — GoalEngine stop + goal change**

```python
from spectrenet.ai.goal_engine import GoalEngine
from spectrenet.model.interface import ModelInterface

class M(ModelInterface):
    def complete(self, s, u): return '{"done": true, "rationale": "test"}'

class FakeBridge:
    def is_connected(self): return False
    def get_sessions(self): return []
    def get_session_interactor(self, sid): pass

class FakeEngine:
    def run_msf(self, m, o): return {"success": False, "error": "not connected"}

e = GoalEngine(M(), FakeEngine(), FakeBridge())
e.set_goal("test goal")
assert e._goal == "test goal"
e.handle_input("change goal to new goal")
assert e._goal == "new goal"
e.handle_input("stop")
assert e._running is False
print("GoalEngine controls: PASS")
```

Run: `python _dod_p3.py` (append to the same file)

- [ ] **Step 4: DoD — SessionInteractor type detection**

```python
from spectrenet.msf.session_interactor import SessionInteractor

class FakeSess:
    type = "meterpreter"
    def run_with_output(self, cmd): return f"result:{cmd}"

class FakeSessions:
    def session(self, sid): return FakeSess()

class FC:
    sessions = FakeSessions()

s = SessionInteractor(FC(), "1")
assert s.session_type() == "meterpreter"
assert s.run("getuid") == "result:getuid"
print("SessionInteractor: PASS")
```

Run: `python _dod_p3.py`

- [ ] **Step 5: Delete temp files**

```bash
del _dod_p3.py
```

- [ ] **Step 6: Push to GitHub**

```bash
git push origin phase1-foundation
```

---

## Definition of Done (Phase 3)

- [ ] `python -m pytest tests/ -v` — all tests pass (Phase 1 + 2 + 3)
- [ ] `MsfConsole.open()` returns `True` with injected client; `send()` polls and returns output
- [ ] `SessionInteractor.run()` returns output from meterpreter and shell sessions
- [ ] `GoalEngine.set_goal()` initialises state; `stop()` halts loop; `handle_input("stop")` calls stop
- [ ] `GoalEngine` emits `success` event when `StepReasoner` returns `None`
- [ ] `GoalEngine` emits `dead_end` after 3 consecutive failed exploit steps
- [ ] `GoalPanel.render()` includes `[AI: RUNNING]` / `[AI: SUCCESS]` / `[AI: DEAD END]` / `[AI: STOPPED]`
- [ ] `SessionPanel` constructs in terminal mode; toggles to menu on `?`
- [ ] TUI smoke confirms `SpectreNetApp` constructs with `model=None` and `msf_bridge=None`
- [ ] `snet --help` shows `--msf-host`, `--msf-port`, `--model` flags

---

*SpectreNet Phase 3 — Goal-Directed AI Loop. Always one step ahead.*
