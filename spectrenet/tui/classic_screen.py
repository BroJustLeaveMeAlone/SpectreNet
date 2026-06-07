from __future__ import annotations
import asyncio
import logging
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input, RichLog
from textual.containers import Vertical, Horizontal
from spectrenet import APP_NAME, __version__
from spectrenet.theme import CYAN, CYAN_DIM, NAVY, NAVY_DEEP, NAVY_LIGHT, GREY, WHITE, SUCCESS

log = logging.getLogger("spectrenet")

_DIRECT_TOOLS = {"nmap", "masscan", "sqlmap", "nikto", "nuclei", "msfvenom"}


def _tool_status(registry) -> str:
    """One-line tool availability summary."""
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
        ("f1", "show_help", "Help"),
        ("ctrl+l", "clear_feed", "Clear"),
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
    #feed {{
        border: none;
        background: {NAVY_DEEP};
        height: 1fr;
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
        self._registry = registry
        self._recon = recon
        self._msf_bridge = msf_bridge

    def compose(self) -> ComposeResult:
        yield Static("", id="statusbar")
        self.feed = RichLog(highlight=True, markup=True, id="feed", wrap=True)
        yield self.feed
        with Horizontal(id="input-bar"):
            yield Static("»", id="prompt-label")
            yield Input(placeholder="nmap 10.0.0.1 -sV  |  help  |  ai  |  quit", id="cmd-input")

    def on_mount(self) -> None:
        status = f"[bold {CYAN}]SpectreNet[/] v{__version__}  Classic Mode    {_tool_status(self._registry)}"
        msf_status = ""
        if self._msf_bridge:
            msf_status = f"  MSF: [{SUCCESS}]connected[/]" if self._msf_bridge.is_connected() else f"  MSF: [{GREY}]disconnected[/]"
        self.query_one("#statusbar", Static).update(status + msf_status)
        self._welcome()
        self.query_one("#cmd-input", Input).focus()

    def _welcome(self) -> None:
        self.feed.write(f"[bold {CYAN}]SpectreNet[/] v{__version__} — Classic Mode")
        self.feed.write(f"[{GREY}]Type any tool name directly, or [bold]help[/] for the command reference.[/]")
        self.feed.write("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.value = ""
        if not raw:
            return
        self._dispatch(raw)

    def _dispatch(self, raw: str) -> None:
        parts = raw.split()
        verb = parts[0].lower()
        rest = parts[1:]

        if verb in ("help", "?"):
            self.action_show_help()
        elif verb in ("quit", "exit"):
            self.app.exit()
        elif verb == "clear":
            self.action_clear_feed()
        elif verb == "ai":
            from spectrenet.tui.startup_screen import AIConfigScreen
            self.app.push_screen(AIConfigScreen())
        elif verb == "wrappers" or verb == "tools":
            self._show_tools()
        elif verb == "sessions":
            self._show_sessions()
        elif verb == "session" and rest:
            self._open_session(rest[0])
        elif verb in _DIRECT_TOOLS:
            self.run_worker(self._run_tool(verb, rest), exclusive=False)
        elif verb == "msf" and rest:
            self.run_worker(self._run_msf_command(" ".join(rest)), exclusive=False)
        else:
            self.feed.write(
                f"[{GREY}]Unknown: [bold]{verb}[/]  —  type [bold {CYAN}]help[/] for commands "
                f"or run any tool directly (nmap, masscan, sqlmap, nikto, nuclei)[/]"
            )

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
                stderr_text = stderr.decode(errors="replace").strip()
                if stderr_text:
                    self.feed.write(f"[{GREY}]{stderr_text}[/]")
            if proc.returncode and proc.returncode != 0:
                self.feed.write(f"[{GREY}]Exit code: {proc.returncode}[/]")
        except FileNotFoundError:
            self.feed.write(
                f"[red]'{tool}' not found on PATH.[/]\n"
                f"[{GREY}]Install it and make sure it's accessible from the terminal.[/]"
            )
        except Exception as exc:
            self.feed.write(f"[red]Error running {tool}: {exc}[/]")

    async def _run_msf_command(self, command: str) -> None:
        if self._msf_bridge is None or not self._msf_bridge.is_connected():
            self.feed.write(f"[red]MSF bridge not connected.[/] Start msfrpcd first.")
            return
        self.feed.write(f"\n[bold {CYAN}]▸ msf {command}[/]")
        try:
            con = self._msf_bridge.get_console()
            output = con.send(command)
            self.feed.write(output or "[dim](no output)[/]")
        except Exception as exc:
            self.feed.write(f"[red]MSF error: {exc}[/]")

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
            self.feed.write(f"  [{SUCCESS}]{s.id:<4}[/]  {getattr(s, 'type', '?')}  {getattr(s, 'target_host', '')}")

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

    def action_show_help(self) -> None:
        from spectrenet.tui.help_screen import HelpScreen
        self.app.push_screen(HelpScreen("classic"))

    def action_clear_feed(self) -> None:
        self.feed.clear()
