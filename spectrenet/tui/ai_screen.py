from __future__ import annotations
import asyncio
import logging
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input, RichLog, Button
from textual.suggester import SuggestFromList
from textual.containers import Horizontal
from spectrenet import __version__
from spectrenet.theme import CYAN, CYAN_DIM, NAVY, NAVY_DEEP, NAVY_LIGHT, GREY, WHITE, SUCCESS, WARNING, ERROR, RISK_HIGH
from spectrenet.tui.approval_gate import ActionCard, ApprovalResult, format_action_card
from spectrenet.tui.goal_panel import GoalPanel
from spectrenet.tui.cheat_sheets import CHEATSHEETS, SCAN_PROFILES, parse_nmap_text, suggest_followups
from spectrenet.workspace import Workspace
from spectrenet.loot import LootVault
from spectrenet.scope import ScopeEnforcer
from spectrenet.knowledge.cve_enricher import CVEEnricher

log = logging.getLogger("spectrenet")

_DIRECT_TOOLS = {
    "nmap", "masscan", "sqlmap", "nikto", "nuclei", "msfvenom",
    "gobuster", "hydra", "enum4linux", "whatweb", "searchsploit", "crackmapexec",
    "shodan", "subfinder",
}

_COMPLETIONS = sorted(_DIRECT_TOOLS | {
    "goal", "stop", "explain", "scan", "loot", "scope", "report", "postex",
    "note", "workspace", "classic", "help", "clear", "quit",
    "tools", "tools install",
    "scan quick", "scan full", "scan stealth", "scan web", "scan udp", "scan vuln", "scan os",
    "loot add", "loot clear", "scope add", "scope strict",
    "report html",
    "postex sessions", "postex register", "postex enum", "postex pivot", "postex loot",
    "help nmap", "help masscan", "help sqlmap", "help msfvenom", "help nikto",
    "help nuclei", "help gobuster", "help hydra", "help msfconsole",
    "help enum4linux", "help whatweb", "help searchsploit", "help crackmapexec",
    "help shodan", "help subfinder",
})


class AIScreen(Screen):
    """AI mode — autonomous goal-directed execution with approval gate."""

    BINDINGS = [
        ("f1",     "show_help",  "Help"),
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
    #clear-btn {{
        width: 5;
        min-width: 5;
        height: 1;
        background: {NAVY};
        color: {GREY};
        border: none;
        margin-left: 1;
    }}
    #clear-btn:hover {{
        background: {NAVY_LIGHT};
        color: {CYAN};
    }}
    """

    def __init__(self, model, registry, recon, msf_bridge=None, config=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._model    = model
        self._registry = registry
        self._recon    = recon
        self._msf_bridge = msf_bridge
        self._config     = config
        self._goal_engine = None
        self._approval_event:  asyncio.Event | None = None
        self._approval_result: str | None           = None
        self._history:     list[str] = []
        self._history_idx: int       = -1
        self._last_output: str       = ""
        self._workspace  = Workspace()
        self._loot       = LootVault()
        self._scope      = ScopeEnforcer(
            getattr(config, "scope", None) or [],
            getattr(config, "scope_strict", False),
        )
        self._enricher   = CVEEnricher()
        from spectrenet.engines.post_ex import PostExEngine
        self._post_ex    = PostExEngine(loot=self._loot)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        self.goal_panel = GoalPanel()
        yield self.goal_panel
        self.feed = RichLog(highlight=True, markup=True, id="feed", wrap=True)
        yield self.feed
        with Horizontal(id="input-bar"):
            yield Static("ai»", id="prompt-label")
            yield Input(
                placeholder="goal <objective>  |  explain  |  scan quick <ip>  |  !cmd  |  help",
                id="ai-input",
                suggester=SuggestFromList(_COMPLETIONS, case_sensitive=False),
            )
            yield Button("CLR", id="clear-btn")

    def on_mount(self) -> None:
        self.feed.write(f"[bold {CYAN}]SpectreNet[/] v{__version__} — AI Mode")
        backend_name = type(self._model).__name__.replace("Backend", "").lower()
        self.feed.write(
            f"[{GREY}]Backend: {backend_name}  —  type [bold]goal <objective>[/] to begin a mission.[/]"
        )
        self.feed.write("")
        self.query_one("#ai-input", Input).focus()

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def on_key(self, event) -> None:
        focused = self.focused
        if not isinstance(focused, Input) or focused.id != "ai-input":
            return
        if event.key == "up":
            if self._history:
                self._history_idx = min(self._history_idx + 1, len(self._history) - 1)
                focused.value = self._history[-(self._history_idx + 1)]
                focused.cursor_position = len(focused.value)
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            if self._history_idx > 0:
                self._history_idx -= 1
                focused.value = self._history[-(self._history_idx + 1)]
                focused.cursor_position = len(focused.value)
            elif self._history_idx == 0:
                self._history_idx = -1
                focused.value = ""
            event.prevent_default()
            event.stop()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.value = ""
        if not raw:
            return

        # History
        if not self._history or self._history[-1] != raw:
            self._history.append(raw)
        self._history_idx = -1

        self._workspace.add_command(raw)

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
        verb  = parts[0].lower()

        # Shell passthrough
        if raw.startswith("!"):
            shell_cmd = raw[1:].strip()
            if shell_cmd:
                self.run_worker(self._run_shell(shell_cmd), exclusive=False)
            return

        # Hard-wired commands that must never reach GoalEngine
        if verb in ("help", "?"):
            if len(parts) > 1:
                self._show_cheatsheet(parts[1].lower())
            else:
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

        # Scan profiles
        if verb == "scan":
            self._handle_scan(parts[1:])
            return

        # Direct tool invocation
        if verb in _DIRECT_TOOLS:
            self.run_worker(self._run_tool(verb, parts[1:]), exclusive=False)
            return

        # explain command
        if verb == "explain":
            context = " ".join(parts[1:]) if len(parts) > 1 else self._last_output
            if not context:
                self.feed.write(f"[{GREY}]Nothing to explain yet — run a tool first, or: explain <text>[/]")
            else:
                self.run_worker(self._explain(context), exclusive=False)
            return

        # note
        if verb == "note" and len(parts) > 1:
            text = " ".join(parts[1:])
            self._workspace.add_note(text)
            self.feed.write(f"[{CYAN}]◈ Note saved:[/] {text}")
            return

        # workspace
        if verb == "workspace":
            self._handle_workspace(parts[1:])
            return

        # loot vault
        if verb == "loot":
            self._handle_loot(parts[1:])
            return

        # scope enforcement
        if verb == "scope":
            self._handle_scope(parts[1:])
            return

        # report export
        if verb == "report":
            rest = parts[1:]
            if rest and rest[0].lower() == "html":
                self._generate_report_html()
            else:
                self._generate_report()
            return

        if verb == "postex":
            self._handle_postex(parts[1:])
            return

        if verb == "tools":
            self._show_tools(install_hint=bool(parts[1:] and parts[1] == "install"))
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

        self.feed.write(
            f"[{GREY}]Unknown: [bold]{verb}[/]  —  "
            f"[bold {CYAN}]help[/]  [bold {CYAN}]goal <objective>[/]  "
            f"[bold {CYAN}]help nmap[/]  [bold {CYAN}]!cmd[/][/]"
        )

    # ------------------------------------------------------------------
    # Scan profiles
    # ------------------------------------------------------------------

    def _handle_scan(self, rest: list[str]) -> None:
        if not rest:
            profiles = "  ".join(SCAN_PROFILES.keys())
            self.feed.write(
                f"[{GREY}]Usage: [bold]scan <profile> <target>[/]\nProfiles: [bold {CYAN}]{profiles}[/][/]"
            )
            return
        profile = rest[0].lower()
        target  = rest[1] if len(rest) > 1 else ""
        if profile not in SCAN_PROFILES:
            self.feed.write(f"[{GREY}]Unknown profile [bold]{profile}[/]. Available: {', '.join(SCAN_PROFILES)}[/]")
            return
        if not target:
            self.feed.write(f"[{GREY}]Usage: scan {profile} <target>[/]")
            return
        flags = SCAN_PROFILES[profile].split()
        self.feed.write(f"[{GREY}]→ nmap {' '.join(flags)} {target}[/]")
        self.run_worker(self._run_tool("nmap", [*flags, target]), exclusive=False)

    # ------------------------------------------------------------------
    # Goal engine
    # ------------------------------------------------------------------

    def _start_goal(self, objective: str) -> None:
        from spectrenet.ai.goal_engine import GoalEngine
        from spectrenet.ai.output_interpreter import OutputInterpreter
        from spectrenet.engines.exploit import ExploitEngine
        from spectrenet.engines.exploit_modules.registry import ExploitModuleRegistry

        mod_reg = ExploitModuleRegistry()
        mod_reg.discover()
        exploit_engine  = ExploitEngine(mod_reg, self._msf_bridge)
        interpreter     = OutputInterpreter(model=self._model)

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
            tool   = event.get("tool", "")
            target = event.get("target", "")
            color  = {
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
            count    = event.get("count", 0)
            findings = event.get("findings", [])
            self.feed.write(f"    [{CYAN}]◈ RECON COMPLETE[/] — {count} findings")
            for f in findings[:6]:
                ip  = f.get("ip", "")
                port = f.get("port", "")
                svc  = f.get("service", "")
                ver  = f.get("version", "")
                self.feed.write(f"      [dim]├─ {ip}:{port}  {svc} {ver}[/]")
            if count > 6:
                self.feed.write(f"      [dim]└─ … and {count - 6} more[/]")

        elif etype == "replanning":
            self.feed.write(f"  [{WARNING}]◈ REPLANNING[/] — {event.get('reason', '')}")

        elif etype == "session_opened":
            sid   = event.get("session_id", "?")
            stype = event.get("session_type", "unknown")
            self.feed.write(f"    [{SUCCESS}]► Session {sid} opened  [{stype}][/]")

        elif etype == "post_ex":
            cmd    = event.get("command", "")
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
            self.feed.write(f"\n  [{CYAN}]◈[/] [{SUCCESS}]MISSION COMPLETE[/] — goal achieved")
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

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

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
            path   = "spectrenet_report.md"
            with open(path, "w", encoding="utf-8") as f:
                f.write(report)
            self.feed.write(f"\n  [{CYAN}]◈ Report saved →[/] [bold]{path}[/]")
        except Exception as exc:
            log.warning("Report generation failed: %s", exc)

    # ------------------------------------------------------------------
    # explain
    # ------------------------------------------------------------------

    async def _explain(self, text: str) -> None:
        self.feed.write(f"\n[dim {CYAN}]◈ Analyzing…[/]")
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._model.complete(
                    "You are a penetration testing assistant. Interpret this tool output concisely: "
                    "what matters, what's interesting, what should be tried next.",
                    text[:3000],
                ),
            )
            self.feed.write(f"\n[bold {CYAN}]◈ Analysis[/]")
            self.feed.write(response)
        except Exception as exc:
            self.feed.write(f"[red]explain failed: {exc}[/]")

    # ------------------------------------------------------------------
    # Tool runner
    # ------------------------------------------------------------------

    async def _run_tool(self, tool: str, args: list[str]) -> None:
        # Scope check
        if self._scope.active:
            in_scope, out = self._scope.check_args(args)
            if not in_scope:
                ips_str = ", ".join(out)
                if self._scope._strict:
                    self.feed.write(f"[red]⊘ Scope violation:[/] {ips_str} not in scope. Blocked.")
                    return
                self.feed.write(f"[{WARNING}]⚠ Out-of-scope:[/] {ips_str} — proceeding (warn mode)")

        cmd_display = f"{tool} {' '.join(args)}".strip()
        self.feed.write(f"\n[bold {CYAN}]▸ {cmd_display}[/]")
        try:
            proc = await asyncio.create_subprocess_exec(
                tool, *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            output_text = ""
            if stdout:
                output_text = stdout.decode(errors="replace")
                self.feed.write(output_text)
            if stderr:
                t = stderr.decode(errors="replace").strip()
                if t:
                    self.feed.write(f"[{GREY}]{t}[/]")

            self._last_output = output_text

            # Populate findings + CVE enrichment for nmap/masscan
            if tool in ("nmap", "masscan") and output_text:
                parsed = parse_nmap_text(output_text)
                if parsed:
                    for ip in parsed:
                        self._workspace.add_target(ip)
                    alerts = self._enricher.enrich(parsed)
                    if alerts:
                        self.feed.write(f"\n[bold yellow]◈ CVE Alerts ({len(alerts)})[/]")
                        for a in alerts[:10]:
                            cvss_color = "red" if a["cvss"] >= 9.0 else WARNING
                            self.feed.write(
                                f"  [{cvss_color}]■[/] [{GREY}]{a['ip']}:{a['port']}[/]  "
                                f"[bold]{a['cve_id']}[/] CVSS {a['cvss']:.1f} — "
                                f"{a['description'][:90]}"
                            )
                        if len(alerts) > 10:
                            self.feed.write(f"  [{GREY}]… and {len(alerts)-10} more[/]")

            # Auto-suggest follow-ups
            if output_text and tool in ("nmap", "masscan", "nikto", "gobuster"):
                suggestions = suggest_followups(tool, output_text, args)
                if suggestions:
                    self.feed.write(f"\n[dim {CYAN}]◈ Suggested follow-ups:[/]")
                    for s in suggestions:
                        self.feed.write(f"  [{GREY}]▸[/] [dim]{s}[/]")

        except FileNotFoundError:
            self.feed.write(f"[red]'{tool}' not found on PATH.[/]")
        except Exception as exc:
            self.feed.write(f"[red]Error: {exc}[/]")

    # ------------------------------------------------------------------
    # Shell passthrough
    # ------------------------------------------------------------------

    async def _run_shell(self, cmd: str) -> None:
        self.feed.write(f"\n[bold {CYAN}]$ {cmd}[/]")
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if stdout:
                text = stdout.decode(errors="replace")
                self.feed.write(text)
                self._last_output = text
            if stderr:
                t = stderr.decode(errors="replace").strip()
                if t:
                    self.feed.write(f"[{GREY}]{t}[/]")
        except Exception as exc:
            self.feed.write(f"[red]Shell error: {exc}[/]")

    # ------------------------------------------------------------------
    # Cheat sheets
    # ------------------------------------------------------------------

    def _show_cheatsheet(self, tool: str) -> None:
        content = CHEATSHEETS.get(tool)
        if content:
            self.feed.write(content)
        else:
            available = "  ".join(sorted(CHEATSHEETS.keys()))
            self.feed.write(
                f"[{GREY}]No cheat sheet for [bold]{tool}[/]. "
                f"Available: [bold {CYAN}]{available}[/][/]"
            )

    # ------------------------------------------------------------------
    # Tools status
    # ------------------------------------------------------------------

    def _show_tools(self, install_hint: bool = False) -> None:
        if install_hint:
            self.feed.write(
                f"\n[bold {CYAN}]Tool Install Commands[/]\n"
                f"  [{GREY}]Run this in your terminal (outside SpectreNet):[/]\n"
                f"\n"
                f"  [bold {WHITE}]snet tools install[/]    [dim]# print install commands for all missing tools[/]\n"
                f"  [bold {WHITE}]snet tools[/]             [dim]# show full tool status[/]\n"
            )
            return
        from spectrenet.tools_installer import _TOOLS, _is_available
        self.feed.write(f"\n[bold {CYAN}]Tool Status[/]")
        missing = []
        for t in _TOOLS:
            ok = _is_available(t)
            if ok:
                self.feed.write(f"  [{SUCCESS}]OK[/]  [bold {WHITE}]{t.name:<14}[/]")
            else:
                self.feed.write(f"  [{GREY}]--[/]  [{GREY}]{t.name:<14}[/] [dim]not on PATH[/]")
                missing.append(t.name)
        if missing:
            self.feed.write(
                f"\n  [{GREY}]{len(missing)} tool(s) missing -- "
                f"run [bold]snet tools install[/] in a terminal for install commands.[/]"
            )

    # ------------------------------------------------------------------
    # Workspace
    # ------------------------------------------------------------------

    def _handle_workspace(self, rest: list[str]) -> None:
        sub = rest[0].lower() if rest else "status"
        if sub == "save":
            self._workspace.save()
            self.feed.write(f"[{CYAN}]◈ Workspace saved →[/] {self._workspace._path}")
        elif sub == "load":
            if self._workspace.load():
                self.feed.write(f"[{CYAN}]◈ Workspace loaded.[/]  {self._workspace.summary()}")
            else:
                self.feed.write(f"[{GREY}]No workspace file found.[/]")
        elif sub == "new":
            self._workspace.reset()
            self.feed.write(f"[{CYAN}]◈ New workspace started.[/]")
        else:
            self.feed.write(f"[{CYAN}]◈ Workspace[/]  {self._workspace.summary()}")
            self.feed.write(f"[{GREY}]  workspace save  |  workspace load  |  workspace new[/]")

    # ------------------------------------------------------------------
    # Loot vault
    # ------------------------------------------------------------------

    def _handle_loot(self, rest: list[str]) -> None:
        if not rest or rest[0].lower() in ("show", "ls"):
            entries = self._loot.all()
            if not entries:
                self.feed.write(f"[{GREY}]Loot vault empty.[/]")
                return
            self.feed.write(f"\n[bold {CYAN}]◈ Loot Vault[/]  [{GREY}]{self._loot.summary()}[/]")
            for e in entries:
                ts = e["t"][:16]
                self.feed.write(f"  [{SUCCESS}]{e['type']:<8}[/]  {e['text']}  [dim]{ts}[/]")
            return
        sub = rest[0].lower()
        if sub == "clear":
            self._loot.clear()
            self.feed.write(f"[{CYAN}]◈ Loot vault cleared.[/]")
            return
        if sub in LootVault.TYPES and len(rest) > 1:
            text = " ".join(rest[1:])
            self._loot.add(sub, text)
            self.feed.write(f"[{SUCCESS}]◈ Loot added:[/] [{sub}] {text}")
            return
        self.feed.write(
            f"[{GREY}]loot show  |  loot cred <text>  |  loot hash <text>  "
            f"|  loot file <text>  |  loot secret <text>  |  loot clear[/]"
        )

    # ------------------------------------------------------------------
    # Scope enforcement
    # ------------------------------------------------------------------

    def _handle_scope(self, rest: list[str]) -> None:
        if not rest:
            self.feed.write(f"[{CYAN}]◈ Scope:[/]  {self._scope.summary()}")
            self.feed.write(f"[{GREY}]  scope add <cidr>  |  scope check <ip>[/]")
            return
        sub = rest[0].lower()
        if sub == "add" and len(rest) > 1:
            if self._scope.add(rest[1]):
                self.feed.write(f"[{CYAN}]◈ Added to scope:[/] {rest[1]}")
            else:
                self.feed.write(f"[red]Invalid CIDR: {rest[1]}[/]")
            return
        if sub == "check" and len(rest) > 1:
            ip = rest[1]
            in_scope = self._scope.in_scope(ip)
            badge = f"[{SUCCESS}]in scope ✓[/]" if in_scope else f"[red]out of scope ✗[/]"
            self.feed.write(f"  {ip}: {badge}")
            return
        self.feed.write(f"[{GREY}]scope add <cidr>  |  scope check <ip>[/]")

    # ------------------------------------------------------------------
    # Report export
    # ------------------------------------------------------------------

    def _generate_report(self) -> None:
        from spectrenet.tui.report_exporter import generate_report
        from datetime import datetime
        operator = getattr(self._config, "operator_name", "operator") if self._config else "operator"
        md   = generate_report(self._workspace, self._loot, {}, operator)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"spectrenet_report_{ts}.md"
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        self.feed.write(
            f"[{CYAN}]◈ Report saved →[/] [bold]{path}[/]  "
            f"[{GREY}]({len(md.splitlines())} lines)[/]"
        )

    def _generate_report_html(self) -> None:
        from spectrenet.tui.report_exporter import generate_report_html
        from datetime import datetime
        operator = getattr(self._config, "operator_name", "operator") if self._config else "operator"
        html = generate_report_html(self._workspace, self._loot, {}, operator)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"spectrenet_report_{ts}.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        self.feed.write(
            f"[{CYAN}]◈ HTML report saved →[/] [bold]{path}[/]  "
            f"[{GREY}](open in browser, Ctrl+P → Save as PDF)[/]"
        )

    def _handle_postex(self, rest: list[str]) -> None:
        sub = rest[0].lower() if rest else "sessions"

        if sub == "sessions":
            summary = self._post_ex.session_summary()
            self.feed.write(f"\n[bold {CYAN}]◈ Post-Ex Sessions[/]")
            self.feed.write(summary or f"[{GREY}]No active sessions.[/]")
            return

        if sub == "register" and len(rest) >= 2:
            host     = rest[1]
            platform = rest[2] if len(rest) > 2 else "unknown"
            user     = rest[3] if len(rest) > 3 else "unknown"
            s = self._post_ex.register_session(host, platform, user)
            self.feed.write(
                f"[{SUCCESS}]◈ Session {s.id} registered[/]  "
                f"{host}  [{platform}]  user={user}"
            )
            return

        if sub == "enum" and len(rest) >= 2:
            try:
                sid = int(rest[1])
            except ValueError:
                self.feed.write(f"[red]postex enum <session_id>[/]")
                return
            s = self._post_ex.get_session(sid)
            if s is None:
                self.feed.write(f"[red]Session {sid} not found.[/]")
                return
            cmds = self._post_ex.auto_enum_commands(s.platform)
            self.feed.write(f"\n[bold {CYAN}]◈ Auto-enum for session {sid} ({s.platform})[/]")
            for c in cmds:
                self.feed.write(f"  [{GREY}]▸[/] [dim]{c}[/]")
            return

        if sub == "pivot" and len(rest) >= 2:
            try:
                sid = int(rest[1])
            except ValueError:
                self.feed.write(f"[red]postex pivot <session_id>[/]")
                return
            s = self._post_ex.get_session(sid)
            if s is None:
                self.feed.write(f"[red]Session {sid} not found.[/]")
                return
            targets = list(self._workspace._data.get("targets", []))
            suggestions = self._post_ex.suggest_pivot(s, targets)
            self.feed.write(f"\n[bold {CYAN}]◈ Pivot suggestions from session {sid}[/]")
            for sug in suggestions:
                self.feed.write(f"  [{GREY}]▸[/] [dim]{sug}[/]")
            return

        if sub == "loot" and len(rest) >= 3:
            try:
                sid = int(rest[1])
            except ValueError:
                self.feed.write(f"[red]postex loot <session_id> <output>[/]")
                return
            output_text = " ".join(rest[2:])
            creds  = self._post_ex.extract_creds(output_text)
            hashes = self._post_ex.extract_hashes(output_text)
            total  = len(creds) + len(hashes)
            self.feed.write(
                f"[{SUCCESS}]◈ Extracted {total} items[/] from session {sid} output  "
                f"({len(creds)} creds, {len(hashes)} hashes) → loot vault"
            )
            return

        self.feed.write(
            f"[{GREY}]postex sessions  |  postex register <host> [platform] [user]  |  "
            f"postex enum <id>  |  postex pivot <id>  |  postex loot <id> <output>[/]"
        )

    # ------------------------------------------------------------------
    # Info helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "clear-btn":
            self.feed.clear()
            self.query_one("#ai-input", Input).focus()

    def action_show_help(self) -> None:
        from spectrenet.tui.help_screen import HelpScreen
        self.app.push_screen(HelpScreen("ai"))

    def action_clear_feed(self) -> None:
        self.feed.clear()
