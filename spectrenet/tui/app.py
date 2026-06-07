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

        # Approval gate intercept — only Y/N/S accepted while a gate is pending
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

        # Route to GoalEngine while it is running
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
        from spectrenet.ai.output_interpreter import OutputInterpreter
        from spectrenet.engines.exploit import ExploitEngine
        from spectrenet.engines.exploit_modules.registry import ExploitModuleRegistry

        module_registry = ExploitModuleRegistry()
        module_registry.discover()
        exploit_engine = ExploitEngine(module_registry, self.msf_bridge)
        output_interpreter = OutputInterpreter(model=self.model)

        self._goal_engine = GoalEngine(
            model=self.model,
            exploit_engine=exploit_engine,
            msf_bridge=self.msf_bridge,
            recon_engine=self.recon,
            output_interpreter=output_interpreter,
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

        elif etype == "recon_complete":
            count = event.get("count", 0)
            findings = event.get("findings", [])
            self.feed.write(f"    [{CYAN}]◈ RECON COMPLETE[/] — {count} findings")
            for f in findings[:5]:
                ip = f.get("ip", "")
                port = f.get("port", "")
                svc = f.get("service", "")
                ver = f.get("version", "")
                self.feed.write(f"      [dim]├─ {ip}:{port}  {svc} {ver}[/]")
            if count > 5:
                self.feed.write(f"      [dim]└─ ... and {count - 5} more[/]")

        elif etype == "replanning":
            reason = event.get("reason", "")
            self.feed.write(f"  [yellow]◈ REPLANNING[/] — {reason}")

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
