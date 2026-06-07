from __future__ import annotations
import asyncio
import logging
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input, RichLog
from textual.containers import Horizontal
from spectrenet import __version__
from spectrenet.theme import CYAN, CYAN_DIM, NAVY, NAVY_DEEP, NAVY_LIGHT, GREY, WHITE, SUCCESS, WARNING, ERROR, RISK_HIGH
from spectrenet.tui.approval_gate import ActionCard, ApprovalResult, format_action_card
from spectrenet.tui.goal_panel import GoalPanel

log = logging.getLogger("spectrenet")

_DIRECT_TOOLS = {"nmap", "masscan", "sqlmap", "nikto", "nuclei", "msfvenom"}


class AIScreen(Screen):
    """AI mode — autonomous goal-directed execution with approval gate."""

    BINDINGS = [
        ("f1", "show_help", "Help"),
        ("ctrl+l", "clear_feed", "Clear"),
    ]

    DEFAULT_CSS = f"""
    AIScreen {{
        background: {NAVY_DEEP};
        layout: vertical;
    }}
    GoalPanel {{
        background: {NAVY};
        border-bottom: solid {CYAN};
        height: 1;
        padding: 0 1;
    }}
    #feed {{
        background: {NAVY_DEEP};
        height: 1fr;
        padding: 0 1;
        border: none;
    }}
    #input-bar {{
        height: 3;
        background: {NAVY};
        border-top: solid {NAVY_LIGHT};
        padding: 0 1;
        align: left middle;
    }}
    #prompt-label {{
        color: {CYAN};
        text-style: bold;
        width: auto;
        height: 1;
        margin-right: 1;
    }}
    Input {{
        border: none;
        background: {NAVY};
        color: {WHITE};
        height: 1;
        width: 1fr;
    }}
    Input:focus {{
        border: none;
    }}
    """

    def __init__(self, model, registry, recon, msf_bridge=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._model = model
        self._registry = registry
        self._recon = recon
        self._msf_bridge = msf_bridge
        self._goal_engine = None
        self._approval_event: asyncio.Event | None = None
        self._approval_result: str | None = None

    def compose(self) -> ComposeResult:
        self.goal_panel = GoalPanel()
        yield self.goal_panel
        self.feed = RichLog(highlight=True, markup=True, id="feed", wrap=True)
        yield self.feed
        with Horizontal(id="input-bar"):
            yield Static("ai»", id="prompt-label")
            yield Input(
                placeholder="goal <objective>  |  stop  |  help  |  classic  |  quit",
                id="ai-input",
            )

    def on_mount(self) -> None:
        self.feed.write(f"[bold {CYAN}]SpectreNet[/] v{__version__} — AI Mode")
        backend_name = type(self._model).__name__.replace("Backend", "").lower()
        self.feed.write(f"[{GREY}]Backend: {backend_name}  —  type [bold]goal <objective>[/] to begin a mission.[/]")
        self.feed.write("")
        self.query_one("#ai-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.value = ""
        if not raw:
            return

        # Approval gate — only Y/N/S accepted while pending
        if self._approval_event is not None:
            key = raw.upper()
            if key in ("Y", "N", "S"):
                self._approval_result = key
                if self._goal_engine is not None:
                    self._goal_engine.set_approval_result(key)
                self._approval_event.set()
                self._approval_event = None
            else:
                self.feed.write(f"[{WARNING}]Approval pending — enter Y (approve) / N (deny) / S (skip)[/]")
            return

        parts = raw.split()
        verb = parts[0].lower()

        # Hard-wired commands that must never reach GoalEngine
        if verb in ("help", "?"):
            self.action_show_help()
            return
        if verb in ("quit", "exit"):
            self.app.exit()
            return
        if verb == "clear":
            self.action_clear_feed()
            return
        if verb == "classic":
            self.app.pop_screen()
            return
        if verb == "sessions":
            self._show_sessions()
            return
        if verb in _DIRECT_TOOLS:
            self.run_worker(self._run_tool(verb, parts[1:]), exclusive=False)
            return
        if verb == "stop":
            if self._goal_engine:
                self._goal_engine.stop()
                self.goal_panel.update_goal(self._goal_engine._goal, "STOPPED")
                self.feed.write(f"[{CYAN}]◈ Mission stopped.[/]")
            return

        # Route to GoalEngine while running (operator guidance, skip, etc.)
        if self._goal_engine is not None and self._goal_engine._running:
            self._goal_engine.handle_input(raw)
            return

        # goal command
        if verb == "goal" and len(parts) > 1:
            self._start_goal(" ".join(parts[1:]))
            return

        # Fallback: unknown
        self.feed.write(
            f"[{GREY}]Unknown: [bold]{verb}[/]  —  type [bold {CYAN}]help[/] or [bold {CYAN}]goal <objective>[/][/]"
        )

    def _start_goal(self, objective: str) -> None:
        from spectrenet.ai.goal_engine import GoalEngine
        from spectrenet.ai.output_interpreter import OutputInterpreter
        from spectrenet.engines.exploit import ExploitEngine
        from spectrenet.engines.exploit_modules.registry import ExploitModuleRegistry

        mod_reg = ExploitModuleRegistry()
        mod_reg.discover()
        exploit_engine = ExploitEngine(mod_reg, self._msf_bridge)
        interpreter = OutputInterpreter(model=self._model)

        self._goal_engine = GoalEngine(
            model=self._model,
            exploit_engine=exploit_engine,
            msf_bridge=self._msf_bridge,
            recon_engine=self._recon,
            output_interpreter=interpreter,
            on_event=self._on_goal_event,
        )
        self._goal_engine.set_goal(objective)
        self.goal_panel.update_goal(objective, "RUNNING")
        self.run_worker(self._goal_engine.start(), exclusive=True)

    def _on_goal_event(self, event: dict) -> None:
        etype = event["type"]

        if etype == "mission_start":
            self.feed.write(f"\n  [bold {CYAN}]◈ MISSION ACTIVE[/] {'─' * 44}")
            self.feed.write(f"  [{CYAN}]Goal:[/] {event.get('goal', '')}")

        elif etype == "step":
            action = event.get("action_type", "")
            tool = event.get("tool", "")
            target = event.get("target", "")
            color = {
                "recon": CYAN, "exploit": RISK_HIGH,
                "payload_delivery": RISK_HIGH, "lateral_movement": WARNING,
            }.get(action, WHITE)
            self.feed.write(f"\n  [bold {color}]▸ {action.upper():<14}[/] {tool} → {target}  [dim]⟳[/]")

        elif etype == "step_complete":
            self.feed.write(f"    [{GREY}]{event.get('output', '')}[/]  [{CYAN}]✓[/]")

        elif etype == "step_failed":
            self.feed.write(f"    [{ERROR}]✗ {event.get('error', 'failed')}[/]")

        elif etype == "step_skipped":
            self.feed.write(f"    [{WARNING}]⊘ step {event.get('step_id')} skipped[/]")

        elif etype == "recon_complete":
            count = event.get("count", 0)
            findings = event.get("findings", [])
            self.feed.write(f"    [{CYAN}]◈ RECON COMPLETE[/] — {count} findings")
            for f in findings[:6]:
                ip = f.get("ip", "")
                port = f.get("port", "")
                svc = f.get("service", "")
                ver = f.get("version", "")
                self.feed.write(f"      [dim]├─ {ip}:{port}  {svc} {ver}[/]")
            if count > 6:
                self.feed.write(f"      [dim]└─ … and {count - 6} more[/]")

        elif etype == "replanning":
            self.feed.write(f"  [{WARNING}]◈ REPLANNING[/] — {event.get('reason', '')}")

        elif etype == "session_opened":
            sid = event.get("session_id", "?")
            stype = event.get("session_type", "unknown")
            self.feed.write(f"    [{SUCCESS}]► Session {sid} opened  [{stype}][/]")

        elif etype == "post_ex":
            cmd = event.get("command", "")
            output = event.get("output", "").strip()
            self.feed.write(f"  [dim]┌─ POST-EX  {cmd}[/]")
            self.feed.write(f"  [dim]│[/]  [{WHITE}]{output}[/]")
            self.feed.write(f"  [dim]└{'─' * 42}[/]")

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
            self.feed.write(f"\n  [{CYAN}]◈[/] [{SUCCESS}]MISSION COMPLETE[/bold] — goal achieved")
            if self._goal_engine:
                self.goal_panel.update_goal(self._goal_engine._goal, "SUCCESS")
            self._maybe_write_report()

        elif etype == "dead_end":
            self.feed.write(f"\n  [{WARNING}]◈ DEAD END[/] — {event.get('suggestion', '')}")
            if self._goal_engine:
                self.goal_panel.update_goal(self._goal_engine._goal, "DEAD END")

        elif etype == "ai_thinking":
            self.feed.write(f"  [dim italic {CYAN}]◈  {event.get('text', '')}[/]")

        elif etype == "goal_changed":
            new_goal = event.get("goal", "")
            self.goal_panel.update_goal(new_goal, "RUNNING")
            self.feed.write(f"  [{CYAN}]◈ Goal updated:[/] {new_goal}")

    def _maybe_write_report(self) -> None:
        if self._goal_engine is None:
            return
        findings = self._goal_engine._state.get("findings", [])
        if not findings:
            return
        self.run_worker(self._write_report(findings), exclusive=False)

    async def _write_report(self, findings: list[dict]) -> None:
        try:
            from spectrenet.ai.report_writer import ReportWriter

            class _NoStore:
                def actions_for(self, sid): return []
                def approvals_for(self, sid): return []

            writer = ReportWriter(self._model)
            report = writer.generate(_NoStore(), session_id=0, findings=findings)
            path = "spectrenet_report.md"
            with open(path, "w", encoding="utf-8") as f:
                f.write(report)
            self.feed.write(f"\n  [{CYAN}]◈ Report saved →[/] [bold]{path}[/]")
        except Exception as exc:
            log.warning("Report generation failed: %s", exc)

    async def _run_tool(self, tool: str, args: list[str]) -> None:
        cmd_display = f"{tool} {' '.join(args)}".strip()
        self.feed.write(f"\n[bold {CYAN}]▸ {cmd_display}[/]")
        try:
            proc = await asyncio.create_subprocess_exec(
                tool, *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if stdout:
                self.feed.write(stdout.decode(errors="replace"))
            if stderr:
                t = stderr.decode(errors="replace").strip()
                if t:
                    self.feed.write(f"[{GREY}]{t}[/]")
        except FileNotFoundError:
            self.feed.write(f"[red]'{tool}' not found on PATH.[/]")
        except Exception as exc:
            self.feed.write(f"[red]Error: {exc}[/]")

    def _show_sessions(self) -> None:
        if self._msf_bridge is None or not self._msf_bridge.is_connected():
            self.feed.write(f"[{GREY}]No MSF connection.[/]")
            return
        sessions = self._msf_bridge.get_sessions()
        if not sessions:
            self.feed.write(f"[{GREY}]No active sessions.[/]")
            return
        for s in sessions:
            self.feed.write(f"  [{SUCCESS}]{s.id}[/]  {getattr(s, 'type', '?')}")

    def action_show_help(self) -> None:
        from spectrenet.tui.help_screen import HelpScreen
        self.app.push_screen(HelpScreen("ai"))

    def action_clear_feed(self) -> None:
        self.feed.clear()
