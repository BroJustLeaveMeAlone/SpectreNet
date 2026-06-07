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
        recon_engine: Any = None,
        output_interpreter: Any = None,
        on_event: Callable[[dict], None] | None = None,
        session_poll_timeout: int = 60,
        auto_approve: bool = False,
    ):
        self._model = model
        self._exploit_engine = exploit_engine
        self._msf_bridge = msf_bridge
        self._recon_engine = recon_engine
        self._interpreter = output_interpreter
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
                if self._recon_engine is not None:
                    try:
                        result = self._recon_engine.scan(
                            tool=step.tool, target=step.target, **(step.params or {})
                        )
                        if self._interpreter is not None:
                            findings = self._interpreter.from_recon(result)
                        else:
                            findings = []
                            for host in result.get("hosts", []):
                                for p in host.get("ports", []):
                                    findings.append({
                                        "type": "open_port", "ip": host.get("ip", ""),
                                        "port": p.get("port"), "service": p.get("service", ""),
                                        "version": p.get("version", ""), "severity": "INFO",
                                        "detail": f"port {p.get('port')}", "raw": str(p),
                                    })
                        self._state.setdefault("findings", []).extend(findings)
                        self._emit("recon_complete", findings=findings, count=len(findings))
                        self._no_progress_count = 0
                    except Exception as exc:
                        self._state.setdefault("failed_steps_detail", []).append({
                            "step_id": step.step_id, "tool": step.tool,
                            "target": step.target, "error": str(exc),
                        })
                        self._emit("step_failed", step_id=step.step_id, error=str(exc))
                        self._no_progress_count += 1
                else:
                    self._state.setdefault("recon", []).append(
                        {"tool": step.tool, "target": step.target}
                    )
                    self._emit("step_complete", step_id=step.step_id,
                               output=f"recon queued: {step.tool} → {step.target}")
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
            err = result.get("error", "unknown")
            self._state.setdefault("failed_steps_detail", []).append({
                "step_id": step.step_id, "tool": step.tool,
                "target": step.target, "error": err,
            })
            self._emit("step_failed", step_id=step.step_id, error=err)
            self._no_progress_count += 1
            self._state.setdefault("failed_steps", []).append(step.step_id)
            return

        new_session = await self._poll_for_session(prev_ids)
        if new_session is None:
            err = "no session opened within timeout"
            self._state.setdefault("failed_steps_detail", []).append({
                "step_id": step.step_id, "tool": step.tool,
                "target": step.target, "error": err,
            })
            self._emit("step_failed", step_id=step.step_id, error=err)
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
