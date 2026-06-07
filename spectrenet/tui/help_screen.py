from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static
from textual.containers import Container
from spectrenet.theme import CYAN, NAVY, GREY, WHITE

_CLASSIC_HELP = f"""\
[bold {CYAN}]── RECON ─────────────────────────────────────────────────────────────────[/]
  [bold {WHITE}]nmap[/] [dim]<any args>[/]                    [cyan]nmap 10.0.0.1 -sV -p 22,80,443[/]
  [bold {WHITE}]masscan[/] [dim]<any args>[/]                 [cyan]masscan 10.0.0.0/24 -p 1-1000 --rate 5000[/]
  [bold {WHITE}]scan[/] [dim]<profile> <target>[/]            [cyan]scan quick 10.0.0.1[/]
    Profiles: quick  full  stealth  web  udp  vuln  os

[bold {CYAN}]── WEB ───────────────────────────────────────────────────────────────────[/]
  [bold {WHITE}]nikto[/] [dim]<args>[/]                       [cyan]nikto -h http://10.0.0.1[/]
  [bold {WHITE}]nuclei[/] [dim]<args>[/]                      [cyan]nuclei -u http://10.0.0.1 -t cves/[/]
  [bold {WHITE}]gobuster[/] [dim]<args>[/]                    [cyan]gobuster dir -u http://10.0.0.1 -w common.txt[/]
  [bold {WHITE}]sqlmap[/] [dim]<args>[/]                      [cyan]sqlmap -u "http://10.0.0.1/page?id=1" --dbs[/]

[bold {CYAN}]── EXPLOITATION ──────────────────────────────────────────────────────────[/]
  [bold {WHITE}]msf[/]                                  Enter interactive MSF console mode
  [bold {WHITE}]msf[/] [dim]<command>[/]                      [cyan]msf use exploit/windows/smb/ms17_010_eternalblue[/]
  [bold {WHITE}]msfvenom[/] [dim]<args>[/]                    [cyan]msfvenom -p windows/x64/shell_reverse_tcp ...[/]
  [bold {WHITE}]hydra[/] [dim]<args>[/]                       [cyan]hydra -l root -P rockyou.txt ssh://10.0.0.1[/]

[bold {CYAN}]── SHELL & AI ────────────────────────────────────────────────────────────[/]
  [bold {WHITE}]![/][dim]<command>[/]                          Run any shell command: [cyan]!ls -la /tmp[/]
  [bold {WHITE}]explain[/]                              Switch to AI mode for output analysis
  [bold {WHITE}]ai[/]                                   Switch to AI mode

[bold {CYAN}]── CHEAT SHEETS ──────────────────────────────────────────────────────────[/]
  [bold {WHITE}]help[/] [dim]<tool>[/]                         [cyan]help nmap[/]  [cyan]help sqlmap[/]  [cyan]help hydra[/]  [cyan]help msfconsole[/]
    Available: nmap  masscan  sqlmap  msfvenom  nikto  nuclei  gobuster  hydra

[bold {CYAN}]── SESSION & WORKSPACE ───────────────────────────────────────────────────[/]
  [bold {WHITE}]sessions[/]                             List active MSF sessions
  [bold {WHITE}]session[/] [dim]<id>[/]                        Interact with session
  [bold {WHITE}]note[/] [dim]<text>[/]                         Add a note to current workspace
  [bold {WHITE}]workspace[/]                            Show workspace status
  [bold {WHITE}]workspace save[/] / [bold {WHITE}]load[/] / [bold {WHITE}]new[/]       Persist session across runs

[bold {CYAN}]── NAVIGATION ────────────────────────────────────────────────────────────[/]
  [bold {WHITE}]↑ / ↓[/]                                Command history navigation
  [bold {WHITE}]F1[/]  [dim]/ help[/]                         This screen
  [bold {WHITE}]F2[/]                                   Toggle host/findings panel
  [bold {WHITE}]Ctrl+L[/]  [dim]/ clear[/]                    Clear output feed
  [bold {WHITE}]tools[/]                                Show registered tool status
  [bold {WHITE}]quit[/]  [dim]/ exit[/]                        Exit SpectreNet
"""

_AI_HELP = f"""\
[bold {CYAN}]── AI COMMANDS ───────────────────────────────────────────────────────────[/]
  [bold {WHITE}]goal[/] [dim]<objective>[/]                    [cyan]goal compromise 192.168.1.45[/]
  [bold {WHITE}]stop[/]                                Stop the running AI mission
  [bold {WHITE}]explain[/]                              Explain last tool output with AI
  [bold {WHITE}]explain[/] [dim]<text>[/]                       Explain specific text

[bold {CYAN}]── APPROVAL GATE ─────────────────────────────────────────────────────────[/]
  [bold {WHITE}]Y[/]  Approve    [bold {WHITE}]N[/]  Deny    [bold {WHITE}]S[/]  Skip

[bold {CYAN}]── TOOLS (direct, same as classic) ──────────────────────────────────────[/]
  [bold {WHITE}]nmap  masscan  nikto  nuclei  gobuster  sqlmap  msfvenom  hydra[/]
  [bold {WHITE}]scan[/] [dim]<profile> <target>[/]  quick  full  stealth  web  udp  vuln  os
  [bold {WHITE}]![/][dim]<command>[/]               Shell passthrough: [cyan]!ls /tmp[/]

[bold {CYAN}]── CHEAT SHEETS ──────────────────────────────────────────────────────────[/]
  [bold {WHITE}]help[/] [dim]<tool>[/]               [cyan]help nmap[/]  [cyan]help sqlmap[/]  [cyan]help msfconsole[/]

[bold {CYAN}]── WORKSPACE & NOTES ─────────────────────────────────────────────────────[/]
  [bold {WHITE}]note[/] [dim]<text>[/]               Add a note to current workspace
  [bold {WHITE}]workspace[/] / save / load / new

[bold {CYAN}]── NAVIGATION ────────────────────────────────────────────────────────────[/]
  [bold {WHITE}]↑ / ↓[/]      History    [bold {WHITE}]classic[/]  Back to Classic mode
  [bold {WHITE}]F1[/] / help   This screen  [bold {WHITE}]Ctrl+L[/] / clear  Clear feed
  [bold {WHITE}]quit[/]        Exit SpectreNet
"""


class HelpScreen(ModalScreen):
    """Full command reference overlay. Press ESC or Q to close."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("q",      "dismiss", "Close"),
        ("f1",     "dismiss", "Close"),
    ]

    DEFAULT_CSS = f"""
    HelpScreen {{
        align: center middle;
    }}
    #help-outer {{
        width: 80;
        height: auto;
        max-height: 92%;
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
