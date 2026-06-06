# spectrenet/tui/app.py
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
from textual.containers import Vertical
from spectrenet import APP_NAME, TAGLINE, __version__
from spectrenet.theme import BANNER, CYAN, NAVY_DEEP
from spectrenet.tui.command_parser import parse_command

class SpectreNetApp(App):
    CSS = f"""
    Screen {{ background: {NAVY_DEEP}; }}
    RichLog {{ border: round {CYAN}; height: 1fr; }}
    Input {{ border: round {CYAN}; }}
    """
    TITLE = APP_NAME
    SUB_TITLE = TAGLINE

    def __init__(self, registry, recon, **kwargs):
        super().__init__(**kwargs)
        self.registry = registry
        self.recon = recon

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            self.log_view = RichLog(highlight=True, markup=True)
            yield self.log_view
            yield Input(placeholder="snet> type a command (scan, wrappers, help, quit)")
        yield Footer()

    def on_mount(self) -> None:
        self.log_view.write(f"[bold {CYAN}]{BANNER}[/]")
        self.log_view.write(f"[{CYAN}]{APP_NAME} v{__version__}[/] — {TAGLINE}")
        self.log_view.write(f"Wrappers available: {', '.join(self.registry.available()) or 'none'}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = parse_command(event.value)
        event.input.value = ""
        if cmd is None:
            return
        if cmd.verb in ("quit", "exit"):
            self.exit()
        elif cmd.verb == "help":
            self.log_view.write("Commands: scan <target> --tool <name>, wrappers, help, quit")
        elif cmd.verb == "wrappers":
            self.log_view.write("Registered: " + ", ".join(self.registry.names()))
        elif cmd.verb == "scan":
            self._do_scan(cmd)
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
