from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static
from textual.containers import Container
from spectrenet.theme import CYAN, NAVY, NAVY_DEEP, GREY, WHITE

_CLASSIC_HELP = f"""\
[bold {CYAN}]── RECON ────────────────────────────────────────────────────────────────[/]
  [bold {WHITE}]nmap[/] [dim]<any nmap args>[/]         e.g. [cyan]nmap 10.0.0.1 -sV -p 80,443,445[/]
  [bold {WHITE}]masscan[/] [dim]<any masscan args>[/]   e.g. [cyan]masscan 10.0.0.0/24 -p 1-1000 --rate 5000[/]
  [bold {WHITE}]nikto[/] [dim]-h <target> [opts][/]     e.g. [cyan]nikto -h 10.0.0.1 -p 80[/]
  [bold {WHITE}]nuclei[/] [dim]-u <url> [opts][/]       e.g. [cyan]nuclei -u http://10.0.0.1 -t cves[/]

[bold {CYAN}]── WEB VULNERABILITIES ─────────────────────────────────────────────────[/]
  [bold {WHITE}]sqlmap[/] [dim]<any sqlmap args>[/]     e.g. [cyan]sqlmap -u "http://10.0.0.1/login" --dbs[/]

[bold {CYAN}]── EXPLOITATION ────────────────────────────────────────────────────────[/]
  [bold {WHITE}]msf[/] [dim]<console command>[/]        e.g. [cyan]msf use exploit/windows/smb/ms17_010_eternalblue[/]
  [bold {WHITE}]msfvenom[/] [dim]<args>[/]              e.g. [cyan]msfvenom -p windows/x64/shell_reverse_tcp ...[/]

[bold {CYAN}]── SESSION ─────────────────────────────────────────────────────────────[/]
  [bold {WHITE}]sessions[/]                             List all active sessions
  [bold {WHITE}]session[/] [dim]<id>[/]                 Interact with a session

[bold {CYAN}]── GENERAL ─────────────────────────────────────────────────────────────[/]
  [bold {WHITE}]help[/]  [dim]/ F1[/]                   Show this screen
  [bold {WHITE}]clear[/]                                Clear the output feed
  [bold {WHITE}]ai[/]                                   Switch to AI mode
  [bold {WHITE}]quit[/]  [dim]/ exit[/]                 Exit SpectreNet
"""

_AI_HELP = f"""\
[bold {CYAN}]── AI COMMANDS ─────────────────────────────────────────────────────────[/]
  [bold {WHITE}]goal[/] [dim]<objective>[/]             e.g. [cyan]goal compromise 192.168.1.45[/]
  [bold {WHITE}]stop[/]                                Stop the running AI mission
  [bold {WHITE}]skip[/]                                Skip the current AI step
  [bold {WHITE}]status[/]  [dim]/ ?[/]                 Show current AI state and progress
  [bold {WHITE}]change goal to[/] [dim]<new>[/]        Change objective mid-mission

[bold {CYAN}]── APPROVAL GATE ───────────────────────────────────────────────────────[/]
  When an approval prompt appears, respond with:
  [bold {WHITE}]Y[/]  Approve — action executes, AI continues
  [bold {WHITE}]N[/]  Deny    — action blocked, AI replans
  [bold {WHITE}]S[/]  Skip    — step skipped, AI advances

[bold {CYAN}]── ALL CLASSIC COMMANDS ALSO WORK IN AI MODE ───────────────────────────[/]
  [bold {WHITE}]nmap[/] / [bold {WHITE}]masscan[/] / [bold {WHITE}]sqlmap[/] / [bold {WHITE}]nikto[/] / [bold {WHITE}]nuclei[/]   Direct tool invocation
  [bold {WHITE}]classic[/]                             Switch back to Classic mode
  [bold {WHITE}]help[/]  [dim]/ F1[/]                  Show this screen
  [bold {WHITE}]quit[/]  [dim]/ exit[/]                Exit SpectreNet
"""


class HelpScreen(ModalScreen):
    """Full command reference overlay. Press ESC or Q to close."""

    BINDINGS = [("escape", "dismiss", "Close"), ("q", "dismiss", "Close"), ("f1", "dismiss", "Close")]

    DEFAULT_CSS = f"""
    HelpScreen {{
        align: center middle;
    }}
    #help-outer {{
        width: 78;
        height: auto;
        max-height: 90%;
        background: {NAVY};
        border: round {CYAN};
        padding: 1 2;
    }}
    #help-title {{
        color: {CYAN};
        text-style: bold;
        margin-bottom: 1;
        border-bottom: solid {CYAN};
        padding-bottom: 1;
    }}
    #help-body {{
        margin-bottom: 1;
    }}
    #help-footer {{
        color: {GREY};
        text-align: center;
    }}
    """

    def __init__(self, mode: str = "classic", **kwargs) -> None:
        super().__init__(**kwargs)
        self._mode = mode

    def compose(self) -> ComposeResult:
        with Container(id="help-outer"):
            yield Static("SpectreNet — Command Reference", id="help-title")
            body = _AI_HELP if self._mode == "ai" else _CLASSIC_HELP
            yield Static(body, id="help-body")
            yield Static("[dim]ESC / Q / F1  close[/]", id="help-footer")
