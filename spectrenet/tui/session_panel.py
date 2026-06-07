from textual.app import ComposeResult
from textual.widgets import Static, Input, RichLog
from textual.containers import Vertical
from spectrenet.theme import CYAN

_MENU_ACTIONS = [
    ("getuid",   "Who am I?"),
    ("sysinfo",  "System info"),
    ("hashdump", "Dump password hashes"),
    ("ps",       "List processes"),
    ("pwd",      "Print working directory"),
    ("ls",       "List files"),
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
        self.run_worker(self._exec_command(cmd), exclusive=False)

    async def _exec_command(self, cmd: str) -> None:
        import asyncio
        loop = asyncio.get_event_loop()
        try:
            output = await loop.run_in_executor(None, lambda: self._interactor.run(cmd))
            self._log.write(output or "[dim](no output)[/]")
        except Exception as e:
            self._log.write(f"[red]error: {e}[/]")
