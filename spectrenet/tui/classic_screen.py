from __future__ import annotations
import asyncio
import logging
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input, RichLog, Button
from textual.suggester import SuggestFromList
from textual.containers import Horizontal
from spectrenet import APP_NAME, __version__
from spectrenet.theme import CYAN, CYAN_DIM, NAVY, NAVY_DEEP, NAVY_LIGHT, GREY, WHITE, SUCCESS, WARNING
from spectrenet.tui.findings_panel import FindingsPanel
from spectrenet.tui.network_map import NetworkMapWidget
from spectrenet.tui.cheat_sheets import CHEATSHEETS, SCAN_PROFILES, parse_nmap_text, suggest_followups
from spectrenet.workspace import Workspace
from spectrenet.loot import LootVault
from spectrenet.scope import ScopeEnforcer
from spectrenet.knowledge.cve_enricher import CVEEnricher
from spectrenet.engines.post_ex import PostExEngine

log = logging.getLogger("spectrenet")

_DIRECT_TOOLS = {
    "nmap", "masscan", "sqlmap", "nikto", "nuclei", "msfvenom",
    "gobuster", "hydra", "enum4linux", "whatweb", "searchsploit", "crackmapexec",
    "shodan", "subfinder",
}

_COMPLETIONS = sorted(_DIRECT_TOOLS | {
    "scan", "msf", "loot", "scope", "report", "note", "workspace",
    "sessions", "session", "postex", "explain", "ai", "tools", "help",
    "clear", "quit", "exit",
    "scan quick", "scan full", "scan stealth", "scan web", "scan udp", "scan vuln", "scan os",
    "loot add", "loot clear", "scope add", "scope strict",
    "report html",
    "workspace save", "workspace load", "workspace new",
    "postex sessions", "postex enum", "postex pivot", "postex loot",
    "msf connect", "msf use", "msf run", "msf info", "msf sessions", "msf back",
    "help nmap", "help masscan", "help sqlmap", "help msfvenom", "help nikto",
    "help nuclei", "help gobuster", "help hydra", "help msfconsole",
    "help enum4linux", "help whatweb", "help searchsploit", "help crackmapexec",
    "help shodan", "help subfinder",
})


def _tool_status(registry) -> str:
    parts = []
    for name in sorted(registry._wrappers.keys()):
        w = registry._wrappers[name]
        if w.is_available():
            parts.append(f"[{SUCCESS}]{name}[/] [dim]✓[/]")
        else:
            parts.append(f"[{GREY}]{name}[/] [dim]✗[/]")
    return "  ".join(parts) if parts else f"[{GREY}]no tools registered[/]"


class ClassicScreen(Screen):
    """Classic mode — direct tool control, no AI."""

    BINDINGS = [
        ("f1",     "show_help",        "Help"),
        ("f2",     "toggle_findings",  "Findings"),
        ("f3",     "toggle_netmap",    "Network Map"),
        ("ctrl+l", "clear_feed",       "Clear"),
    ]

    DEFAULT_CSS = f"""
    ClassicScreen {{
        background: {NAVY_DEEP};
        layout: vertical;
    }}
    #statusbar {{
        height: 1;
        background: {NAVY};
        color: {GREY};
        padding: 0 1;
        border-bottom: solid {NAVY_LIGHT};
    }}
    #main-area {{
        height: 1fr;
    }}
    #feed {{
        border: none;
        background: {NAVY_DEEP};
        width: 1fr;
        padding: 0 1;
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

    def __init__(self, registry, recon, msf_bridge=None, config=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._registry   = registry
        self._recon      = recon
        self._msf_bridge = msf_bridge
        self._config     = config
        self._history:     list[str] = []
        self._history_idx: int       = -1
        self._last_output: str       = ""
        self._msf_mode:    bool      = False
        self._workspace  = Workspace()
        self._loot       = LootVault()
        self._scope      = ScopeEnforcer(
            getattr(config, "scope", None) or [],
            getattr(config, "scope_strict", False),
        )
        self._enricher   = CVEEnricher()
        self._post_ex    = PostExEngine(loot=self._loot)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static("", id="statusbar")
        with Horizontal(id="main-area"):
            self.feed = RichLog(highlight=True, markup=True, id="feed", wrap=True)
            yield self.feed
            self.findings_panel = FindingsPanel(id="findings")
            yield self.findings_panel
            self.network_map = NetworkMapWidget(id="netmap")
            self.network_map.display = False
            yield self.network_map
        with Horizontal(id="input-bar"):
            yield Static("»", id="prompt-label")
            yield Input(
                placeholder="nmap 10.0.0.1 -sV  |  scan quick 10.0.0.1  |  help nmap  |  !cmd",
                id="cmd-input",
                suggester=SuggestFromList(_COMPLETIONS, case_sensitive=False),
            )
            yield Button("CLR", id="clear-btn")

    def on_mount(self) -> None:
        status = f"[bold {CYAN}]SpectreNet[/] v{__version__}  Classic Mode    {_tool_status(self._registry)}"
        if self._msf_bridge:
            msf_s = f"  [{SUCCESS}]MSF ✓[/]" if self._msf_bridge.is_connected() else f"  [{GREY}]MSF ✗[/]"
            status += msf_s
        status += f"  [{GREY}]F2 findings  F3 netmap  F1 help[/]"
        self.query_one("#statusbar", Static).update(status)
        self.feed.write(f"[bold {CYAN}]SpectreNet[/] v{__version__} — Classic Mode")
        self.feed.write(
            f"[{GREY}]Type any tool directly, [bold]help[/] for commands, "
            f"[bold]help nmap[/] for tool cheat sheets, or [bold]![/] to run shell commands.[/]"
        )
        self.feed.write("")
        self.query_one("#cmd-input", Input).focus()

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def on_key(self, event) -> None:
        focused = self.focused
        if not isinstance(focused, Input) or focused.id != "cmd-input":
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

        # Save to history (avoid duplicate consecutive entries)
        if not self._history or self._history[-1] != raw:
            self._history.append(raw)
        self._history_idx = -1

        # Log to workspace
        self._workspace.add_command(raw)

        # MSF console mode: route everything to MSF
        if self._msf_mode:
            if raw.lower() in ("exit", "back", "quit"):
                self._msf_mode = False
                self.query_one("#prompt-label", Static).update("»")
                self.feed.write(f"[{GREY}]Exited MSF console mode.[/]")
            else:
                self.run_worker(self._run_msf_command(raw), exclusive=False)
            return

        self._dispatch(raw)

    def _dispatch(self, raw: str) -> None:
        parts = raw.split()
        verb  = parts[0].lower()
        rest  = parts[1:]

        # Shell passthrough
        if raw.startswith("!"):
            shell_cmd = raw[1:].strip()
            if shell_cmd:
                self.run_worker(self._run_shell(shell_cmd), exclusive=False)
            return

        # Help / cheat sheets
        if verb in ("help", "?"):
            if rest:
                self._show_cheatsheet(rest[0].lower())
            else:
                self.action_show_help()
            return

        if verb in ("quit", "exit"):
            self.app.exit()
            return

        if verb == "clear":
            self.action_clear_feed()
            return

        if verb == "ai":
            from spectrenet.tui.startup_screen import AIConfigScreen
            self.app.push_screen(AIConfigScreen())
            return

        # Scan profiles
        if verb == "scan":
            self._handle_scan(rest)
            return

        # Direct tool invocation
        if verb in _DIRECT_TOOLS:
            self.run_worker(self._run_tool(verb, rest), exclusive=False)
            return

        # MSF commands
        if verb == "msf":
            if not rest:
                self._enter_msf_mode()
            elif rest[0].lower() == "connect":
                self._msf_connect(rest[1:])
            else:
                self.run_worker(self._run_msf_command(" ".join(rest)), exclusive=False)
            return

        # explain (needs AI — redirect)
        if verb == "explain":
            self.feed.write(
                f"[{GREY}]'explain' requires an AI model. "
                f"Type [bold {CYAN}]ai[/] to switch to AI mode, then use [bold]explain[/] there.[/]"
            )
            return

        # note <text>
        if verb == "note" and rest:
            text = " ".join(rest)
            self._workspace.add_note(text)
            self.feed.write(f"[{CYAN}]◈ Note saved:[/] {text}")
            return

        # workspace commands
        if verb == "workspace":
            self._handle_workspace(rest)
            return

        # loot vault
        if verb == "loot":
            self._handle_loot(rest)
            return

        # scope enforcement
        if verb == "scope":
            self._handle_scope(rest)
            return

        # report export
        if verb == "report":
            if rest and rest[0].lower() == "html":
                self._generate_report_html()
            else:
                self._generate_report()
            return

        # post-exploitation engine
        if verb == "postex":
            self._handle_postex(rest)
            return

        # tools / wrappers
        if verb in ("tools", "wrappers"):
            self._show_tools()
            return

        # sessions
        if verb == "sessions":
            self._show_sessions()
            return

        if verb == "session" and rest:
            self._open_session(rest[0])
            return

        self.feed.write(
            f"[{GREY}]Unknown: [bold]{verb}[/]  —  "
            f"[bold {CYAN}]help[/] for commands  "
            f"[bold {CYAN}]help nmap[/] for tool cheat sheets  "
            f"[bold {CYAN}]!cmd[/] to run any shell command[/]"
        )

    # ------------------------------------------------------------------
    # Scan profiles
    # ------------------------------------------------------------------

    def _handle_scan(self, rest: list[str]) -> None:
        if not rest:
            profiles = "  ".join(SCAN_PROFILES.keys())
            self.feed.write(
                f"[{GREY}]Usage: [bold]scan <profile> <target>[/]\n"
                f"Profiles: [bold {CYAN}]{profiles}[/][/]"
            )
            return
        profile = rest[0].lower()
        target  = rest[1] if len(rest) > 1 else ""
        if profile not in SCAN_PROFILES:
            self.feed.write(
                f"[{GREY}]Unknown profile [bold]{profile}[/]. "
                f"Available: {', '.join(SCAN_PROFILES)}[/]"
            )
            return
        if not target:
            self.feed.write(f"[{GREY}]Usage: scan {profile} <target>[/]")
            return
        flags = SCAN_PROFILES[profile].split()
        self.feed.write(
            f"[{GREY}]→ nmap {' '.join(flags)} {target}[/]"
        )
        self.run_worker(self._run_tool("nmap", [*flags, target]), exclusive=False)

    # ------------------------------------------------------------------
    # MSF console mode
    # ------------------------------------------------------------------

    def _enter_msf_mode(self) -> None:
        if self._msf_bridge is None or not self._msf_bridge.is_connected():
            self.feed.write(
                f"[red]MSF bridge not connected.[/] "
                f"Start msfrpcd or use [bold]msf <command>[/] for single commands."
            )
            return
        self._msf_mode = True
        self.query_one("#prompt-label", Static).update(f"[bold {CYAN}]msf>[/]")
        self.feed.write(
            f"\n[bold {CYAN}]◈ MSF Console Mode[/]  "
            f"[{GREY}]Type MSF commands directly. [bold]exit[/] or [bold]back[/] to return.[/]"
        )
        self.feed.write(f"[{GREY}]  help nmap   — SpectreNet tool cheat sheets still work outside this mode.[/]")

    def _msf_connect(self, args: list[str]) -> None:
        if self._msf_bridge is None:
            from spectrenet.msf.bridge import MsfBridge
            self._msf_bridge = MsfBridge()
        if len(args) > 0:
            self._msf_bridge.host = args[0]
        if len(args) > 1:
            try:
                self._msf_bridge.port = int(args[1])
            except ValueError:
                self.feed.write(f"[red]Invalid port: {args[1]}[/]")
                return
        if len(args) > 2:
            self._msf_bridge.password = args[2]
        self.feed.write(
            f"[{GREY}]Connecting to msfrpcd at "
            f"{self._msf_bridge.host}:{self._msf_bridge.port}…[/]"
        )
        self.run_worker(self._do_msf_connect(), exclusive=False)

    async def _do_msf_connect(self) -> None:
        loop = asyncio.get_event_loop()
        ok = await loop.run_in_executor(None, self._msf_bridge.connect)
        if ok:
            self.feed.write(
                f"[{SUCCESS}]◈ MSF connected ✓[/] — "
                f"type [bold {CYAN}]msf[/] to enter console mode or "
                f"[bold {CYAN}]sessions[/] to list active sessions."
            )
        else:
            self.feed.write(
                f"[red]MSF connection failed.[/]\n"
                f"[{GREY}]Is msfrpcd running? Start with:  msfrpcd -P msf -S[/]"
            )

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
            if proc.returncode and proc.returncode not in (0, None):
                self.feed.write(f"[{GREY}]Exit: {proc.returncode}[/]")

            self._last_output = output_text or stderr.decode(errors="replace") if stderr else ""

            # Populate findings panel from nmap/masscan output + CVE enrichment
            if tool in ("nmap", "masscan") and output_text:
                parsed = parse_nmap_text(output_text)
                if parsed:
                    self.findings_panel.add_hosts(parsed)
                    self.network_map.update_hosts(self.findings_panel._hosts)
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
            if output_text:
                suggestions = suggest_followups(tool, output_text, args)
                if suggestions:
                    self.feed.write(f"\n[dim {CYAN}]◈ Suggested follow-ups:[/]")
                    for s in suggestions:
                        self.feed.write(f"  [{GREY}]▸[/] [dim]{s}[/]")

        except FileNotFoundError:
            self.feed.write(
                f"[red]'{tool}' not found on PATH.[/]\n"
                f"[{GREY}]Install it and make sure it's accessible from the terminal.[/]"
            )
        except Exception as exc:
            self.feed.write(f"[red]Error running {tool}: {exc}[/]")

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
            if proc.returncode and proc.returncode not in (0, None):
                self.feed.write(f"[{GREY}]Exit: {proc.returncode}[/]")
        except Exception as exc:
            self.feed.write(f"[red]Shell error: {exc}[/]")

    # ------------------------------------------------------------------
    # MSF command runner (non-blocking via executor)
    # ------------------------------------------------------------------

    async def _run_msf_command(self, command: str) -> None:
        if self._msf_bridge is None or not self._msf_bridge.is_connected():
            self.feed.write(
                f"[red]MSF bridge not connected.[/] "
                f"Start msfrpcd or type [bold {CYAN}]msf connect[/] to retry."
            )
            return
        if self._msf_mode:
            self.feed.write(f"[{GREY}]msf> {command}[/]")
        else:
            self.feed.write(f"\n[bold {CYAN}]▸ msf {command}[/]")
        try:
            con = self._msf_bridge.get_console()
            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(None, lambda: con.send(command))
            if output:
                self.feed.write(output.rstrip())
        except Exception as exc:
            self.feed.write(f"[red]MSF error: {exc}[/]")

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
                self.feed.write(f"[{GREY}]No workspace file found at {self._workspace._path}[/]")
        elif sub == "new":
            self._workspace.reset()
            self.feed.write(f"[{CYAN}]◈ New workspace started.[/]")
        else:
            self.feed.write(f"[{CYAN}]◈ Workspace[/]  {self._workspace.summary()}")
            self.feed.write(
                f"[{GREY}]  workspace save  |  workspace load  |  workspace new[/]"
            )

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
                self.feed.write(
                    f"  [{SUCCESS}]{e['type']:<8}[/]  {e['text']}  [dim]{ts}[/]"
                )
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
        import ipaddress
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
        hosts    = getattr(self.findings_panel, "_hosts", {})
        operator = getattr(self._config, "operator_name", "operator") if self._config else "operator"
        md   = generate_report(self._workspace, self._loot, hosts, operator)
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
        hosts    = getattr(self.findings_panel, "_hosts", {})
        operator = getattr(self._config, "operator_name", "operator") if self._config else "operator"
        html = generate_report_html(self._workspace, self._loot, hosts, operator)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"spectrenet_report_{ts}.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        self.feed.write(
            f"[{CYAN}]◈ HTML report saved →[/] [bold]{path}[/]  "
            f"[{GREY}]open in browser, Ctrl+P → Save as PDF[/]"
        )

    # ------------------------------------------------------------------
    # Post-exploitation engine
    # ------------------------------------------------------------------

    def _handle_postex(self, rest: list[str]) -> None:
        sub = rest[0].lower() if rest else ""

        if not sub or sub == "sessions":
            summary = self._post_ex.session_summary()
            self.feed.write(f"\n[bold {CYAN}]◈ PostEx Sessions[/]")
            self.feed.write(summary if summary != "no active sessions" else f"[{GREY}]no active sessions[/]")
            self.feed.write(f"[{GREY}]  postex register <host>  |  postex enum <id>  |  postex pivot <id>[/]")
            return

        if sub == "register" and len(rest) >= 2:
            host     = rest[1]
            platform = rest[2] if len(rest) > 2 else "linux"
            user     = rest[3] if len(rest) > 3 else ""
            s = self._post_ex.register_session(host, platform, user)
            self.feed.write(f"[{CYAN}]◈ Session [{s.id}] registered:[/] {host}  platform={platform}  user={user or '?'}")
            return

        if sub == "enum" and len(rest) >= 2:
            try:
                sid  = int(rest[1])
                sess = self._post_ex.get_session(sid)
                if not sess:
                    self.feed.write(f"[red]Session {sid} not found.[/]")
                    return
                cmds = self._post_ex.auto_enum_commands(sess.platform)
                self.feed.write(f"\n[bold {CYAN}]◈ Auto-enum commands for session [{sid}] ({sess.host})[/]")
                for cmd in cmds:
                    self.feed.write(f"  [{GREY}]▸[/] [dim]{cmd}[/]")
            except ValueError:
                self.feed.write(f"[red]Usage: postex enum <session_id>[/]")
            return

        if sub == "pivot" and len(rest) >= 2:
            try:
                sid   = int(rest[1])
                sess  = self._post_ex.get_session(sid)
                if not sess:
                    self.feed.write(f"[red]Session {sid} not found.[/]")
                    return
                known_hosts = list(self.findings_panel._hosts.keys())
                suggestions = self._post_ex.suggest_pivot(sess, known_hosts)
                self.feed.write(f"\n[bold {CYAN}]◈ Pivot suggestions from session [{sid}] ({sess.host})[/]")
                for s in suggestions:
                    self.feed.write(f"  [{GREY}]▸[/] [dim]{s}[/]")
            except ValueError:
                self.feed.write(f"[red]Usage: postex pivot <session_id>[/]")
            return

        if sub == "loot" and len(rest) >= 3:
            # postex loot <session_id> <shell_cmd> — run cmd locally + extract creds
            try:
                sid    = int(rest[1])
                cmd    = " ".join(rest[2:])
                output = self._post_ex.run_local(cmd)
                self.feed.write(f"\n[bold {CYAN}]◈ PostEx:[/] {cmd}")
                self.feed.write(output)
                creds  = self._post_ex.extract_creds(output)
                hashes = self._post_ex.extract_hashes(output)
                if creds or hashes:
                    self.feed.write(f"[{CYAN}]◈ Auto-loot:[/] {len(creds)} creds, {len(hashes)} hashes extracted")
            except ValueError:
                self.feed.write(f"[red]Usage: postex loot <session_id> <command>[/]")
            return

        self.feed.write(f"[{GREY}]postex sessions  |  postex register <host> [platform] [user]  |  postex enum <id>  |  postex pivot <id>[/]")

    # ------------------------------------------------------------------
    # Info helpers
    # ------------------------------------------------------------------

    def _show_tools(self) -> None:
        self.feed.write(f"\n[bold {CYAN}]Registered Tools[/]")
        for name in sorted(self._registry._wrappers.keys()):
            w = self._registry._wrappers[name]
            status = f"[{SUCCESS}]available[/]" if w.is_available() else f"[{GREY}]not on PATH[/]"
            self.feed.write(f"  [bold {WHITE}]{name:<12}[/] {status}")

    def _show_sessions(self) -> None:
        if self._msf_bridge is None or not self._msf_bridge.is_connected():
            self.feed.write(f"[{GREY}]No MSF connection — sessions unavailable.[/]")
            return
        sessions = self._msf_bridge.get_sessions()
        if not sessions:
            self.feed.write(f"[{GREY}]No active sessions.[/]")
            return
        self.feed.write(f"\n[bold {CYAN}]Active Sessions[/]")
        for s in sessions:
            self.feed.write(
                f"  [{SUCCESS}]{s.id:<4}[/]  {getattr(s, 'type', '?')}  {getattr(s, 'tunnel_peer', '')}"
            )

    def _open_session(self, session_id: str) -> None:
        if self._msf_bridge is None:
            self.feed.write(f"[red]No MSF bridge.[/]")
            return
        try:
            from spectrenet.tui.session_panel import SessionPanel
            interactor = self._msf_bridge.get_session_interactor(session_id)
            self.mount(SessionPanel(interactor))
        except Exception as exc:
            self.feed.write(f"[red]Could not open session: {exc}[/]")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "clear-btn":
            self.feed.clear()
            self.query_one("#cmd-input", Input).focus()

    def action_show_help(self) -> None:
        from spectrenet.tui.help_screen import HelpScreen
        self.app.push_screen(HelpScreen("classic"))

    def action_clear_feed(self) -> None:
        self.feed.clear()

    def action_toggle_findings(self) -> None:
        self.findings_panel.display = not self.findings_panel.display

    def action_toggle_netmap(self) -> None:
        self.network_map.display = not self.network_map.display
