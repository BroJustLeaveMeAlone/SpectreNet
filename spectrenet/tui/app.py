# spectrenet/tui/app.py
import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
from textual.containers import Vertical
from spectrenet import APP_NAME, TAGLINE, __version__
from spectrenet.theme import BANNER, CYAN, NAVY_DEEP
from spectrenet.tui.command_parser import parse_command
from spectrenet.tui.approval_gate import (
    ActionCard, ApprovalResult, format_action_card
)

class SpectreNetApp(App):
    CSS = f"""
    Screen {{ background: {NAVY_DEEP}; }}
    RichLog {{ border: round {CYAN}; height: 1fr; }}
    Input {{ border: round {CYAN}; }}
    """
    TITLE = APP_NAME
    SUB_TITLE = TAGLINE

    def __init__(self, registry, recon, model=None, **kwargs):
        super().__init__(**kwargs)
        self.registry = registry
        self.recon = recon
        self.model = model
        self._approval_event: asyncio.Event | None = None
        self._approval_result: ApprovalResult | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            self.log_view = RichLog(highlight=True, markup=True)
            yield self.log_view
            yield Input(placeholder="snet> scan | wrappers | mission <target> <desc> | help | quit")
        yield Footer()

    def on_mount(self) -> None:
        self.log_view.write(f"[bold {CYAN}]{BANNER}[/]")
        self.log_view.write(f"[{CYAN}]{APP_NAME} v{__version__}[/] — {TAGLINE}")
        self.log_view.write(f"Wrappers available: {', '.join(self.registry.available()) or 'none'}")
        ai_status = "active" if self.model else "inactive (classic mode)"
        self.log_view.write(f"AI: {ai_status}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.value = ""
        if not raw:
            return

        # Approval gate intercept — if a gate is pending, only accept Y/N/S
        if self._approval_event is not None:
            key = raw.upper()
            if key in ("Y", "N", "S"):
                self._approval_result = ApprovalResult(key)
                self._approval_event.set()
            else:
                self.log_view.write(
                    f"[yellow]Approval pending — enter Y (approve), N (deny), or S (skip)[/]"
                )
            return

        cmd = parse_command(raw)
        if cmd is None:
            return
        if cmd.verb in ("quit", "exit"):
            self.exit()
        elif cmd.verb == "help":
            self.log_view.write(
                "Commands: scan <target> [--tool nmap|masscan], "
                "mission <target> <description>, wrappers, help, quit"
            )
        elif cmd.verb == "wrappers":
            self.log_view.write("Registered: " + ", ".join(self.registry.names()))
        elif cmd.verb == "scan":
            self._do_scan(cmd)
        elif cmd.verb == "mission":
            self._do_mission(cmd)
        else:
            self.log_view.write(f"[red]Unknown command:[/] {cmd.verb}")

    def _do_scan(self, cmd) -> None:
        if not cmd.args:
            self.log_view.write("[red]scan requires a target[/]")
            return
        tool = cmd.flags.get("tool", "nmap")
        target = cmd.args[0]
        try:
            result = self.recon.scan(tool=tool, target=target)
            for host in result["hosts"]:
                ports = ", ".join(str(p["port"]) for p in host["ports"])
                self.log_view.write(f"[{CYAN}]{host['ip']}[/]  ports: {ports}")
        except Exception as e:
            self.log_view.write(f"[red]scan failed:[/] {e}")

    def _do_mission(self, cmd) -> None:
        if self.model is None:
            self.log_view.write(
                "[red]AI mode not active.[/] Start with --model ollama to enable."
            )
            return
        if len(cmd.args) < 2:
            self.log_view.write("[red]usage: mission <target> <description words...>[/]")
            return
        target = cmd.args[0]
        description = " ".join(cmd.args[1:])
        self.run_worker(self._run_mission_pipeline(target, description), exclusive=True)

    async def _run_mission_pipeline(self, target: str, description: str) -> None:
        from spectrenet.ai.mission_planner import MissionPlanner
        planner = MissionPlanner(self.model)
        self.log_view.write(f"[{CYAN}]▶ Planning:[/] {description}")
        plan = planner.plan(description, recon_results={"target": target})
        if not plan.steps:
            self.log_view.write("[red]Planner returned an empty plan.[/]")
            return
        self.log_view.write(f"[{CYAN}]{len(plan.steps)} steps planned:[/]")
        for step in plan.steps:
            approval_flag = " [APPROVAL REQUIRED]" if step.requires_approval else ""
            self.log_view.write(
                f"  {step.step_id}. {step.action_type} → {step.tool} @ {step.target}{approval_flag}"
            )

        for step in plan.steps:
            if step.requires_approval:
                card = ActionCard(
                    action=f"{step.action_type}/{step.tool}",
                    target=step.target,
                    module=step.tool,
                    risk=step.risk_level,
                    reason=step.rationale or "AI-planned intrusive action",
                )
                result = await self._request_approval(card)
                if result == ApprovalResult.DENIED:
                    self.log_view.write(f"[yellow]Step {step.step_id} denied.[/]")
                    continue
                if result == ApprovalResult.SKIPPED:
                    self.log_view.write(f"[yellow]Step {step.step_id} skipped.[/]")
                    continue

            await self._execute_step(step)

        self.log_view.write(f"[{CYAN}]✓ Mission pipeline complete.[/]")

    async def _request_approval(self, card: ActionCard) -> ApprovalResult:
        self._approval_event = asyncio.Event()
        self._approval_result = None
        self.log_view.write(format_action_card(card))
        await self._approval_event.wait()
        self._approval_event = None
        return self._approval_result

    async def _execute_step(self, step) -> None:
        if step.action_type == "recon":
            try:
                result = self.recon.scan(tool=step.tool, target=step.target, **step.params)
                for host in result.get("hosts", []):
                    ports = ", ".join(str(p["port"]) for p in host["ports"])
                    self.log_view.write(f"[{CYAN}]{host['ip']}[/]  ports: {ports}")
            except Exception as e:
                self.log_view.write(f"[red]Step {step.step_id} failed:[/] {e}")
        else:
            self.log_view.write(
                f"[yellow]Step {step.step_id}:[/] {step.action_type} via {step.tool} "
                f"@ {step.target} — dispatched"
            )
