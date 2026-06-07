from __future__ import annotations
import asyncio
import logging
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input, RichLog
from textual.containers import Horizontal
from spectrenet import APP_NAME, __version__
from spectrenet.theme import CYAN, CYAN_DIM, NAVY, NAVY_DEEP, NAVY_LIGHT, GREY, WHITE, SUCCESS, WARNING
from spectrenet.tui.findings_panel import FindingsPanel
from spectrenet.tui.cheat_sheets import CHEATSHEETS, SCAN_PROFILES, parse_nmap_text, suggest_followups
from spectrenet.workspace import Workspace

log = logging.getLogger("spectrenet")

_DIRECT_TOOLS = {"nmap", "masscan", "sqlmap", "nikto", "nuclei", "msfvenom", "gobuster", "hydra"}


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
    """

    def __init__(self, registry, recon, msf_bridge=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._registry   = registry
        self._recon      = recon
        self._msf_bridge = msf_bridge
        self._history:     list[str] = []
        self._history_idx: int       = -1
        self._last_output: str       = ""
        self._msf_mode:    bool      = False
        self._workspace  = Workspace()

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
        with Horizontal(id="input-bar"):
            yield Static("»", id="prompt-label")
            yield Input(
                placeholder="nmap 10.0.0.1 -sV  |  scan quick 10.0.0.1  |  help nmap  |  !cmd",
                id="cmd-input",
            )

    def on_mount(self) -> None:
        status = f"[bold {CYAN}]SpectreNet[/] v{__version__}  Classic Mode    {_tool_status(self._registry)}"
        if self._msf_bridge:
            msf_s = f"  [{SUCCESS}]MSF ✓[/]" if self._msf_bridge.is_connected() else f"  [{GREY}]MSF ✗[/]"
            status += msf_s
        status += f"  [{GREY}]F2 findings  F1 help[/]"
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

    # ------------------------------------------------------------------
    # Tool runner
    # ------------------------------------------------------------------

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

            # Populate findings panel from nmap/masscan output
            if tool in ("nmap", "masscan") and output_text:
                parsed = parse_nmap_text(output_text)
                if parsed:
                    self.findings_panel.add_hosts(parsed)
                    # Also record targets in workspace
                    for ip in parsed:
                        self._workspace.add_target(ip)

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
            self.feed.write(f"[red]MSF bridge not connected.[/] Start msfrpcd first.")
            return
        label = "msf>" if self._msf_mode else f"msf {command}"
        self.feed.write(f"\n[bold {CYAN}]▸ {label}[/]" if not self._msf_mode else "")
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

    def action_show_help(self) -> None:
        from spectrenet.tui.help_screen import HelpScreen
        self.app.push_screen(HelpScreen("classic"))

    def action_clear_feed(self) -> None:
        self.feed.clear()

    def action_toggle_findings(self) -> None:
        self.findings_panel.display = not self.findings_panel.display
