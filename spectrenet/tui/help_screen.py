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
  [bold {WHITE}]shodan[/] [dim]<ip>[/]                        [cyan]shodan 10.0.0.1[/]
  [bold {WHITE}]subfinder[/] [dim]<domain>[/]                 [cyan]subfinder example.com[/]

[bold {CYAN}]── WEB ───────────────────────────────────────────────────────────────────[/]
  [bold {WHITE}]nikto[/] [dim]<args>[/]                       [cyan]nikto -h http://10.0.0.1[/]
  [bold {WHITE}]nuclei[/] [dim]<args>[/]                      [cyan]nuclei -u http://10.0.0.1 -t cves/[/]
  [bold {WHITE}]gobuster[/] [dim]<args>[/]                    [cyan]gobuster dir -u http://10.0.0.1 -w common.txt[/]
  [bold {WHITE}]sqlmap[/] [dim]<args>[/]                      [cyan]sqlmap -u "http://10.0.0.1/page?id=1" --dbs[/]
  [bold {WHITE}]whatweb[/] [dim]<url>[/]                      [cyan]whatweb http://10.0.0.1[/]

[bold {CYAN}]── SMB / AD ──────────────────────────────────────────────────────────────[/]
  [bold {WHITE}]enum4linux[/] [dim]<ip>[/]                    [cyan]enum4linux 10.0.0.1[/]
  [bold {WHITE}]crackmapexec[/] [dim]<proto> <ip> [opts][/]   [cyan]crackmapexec smb 10.0.0.1 -u admin -p pass[/]
    Protocols: smb  ssh  winrm  rdp  ldap  mssql

[bold {CYAN}]── EXPLOITATION ──────────────────────────────────────────────────────────[/]
  [bold {WHITE}]msf[/]                                  Enter interactive MSF console mode
  [bold {WHITE}]msf[/] [dim]<command>[/]                      [cyan]msf use exploit/windows/smb/ms17_010_eternalblue[/]
  [bold {WHITE}]msfvenom[/] [dim]<args>[/]                    [cyan]msfvenom -p windows/x64/shell_reverse_tcp ...[/]
  [bold {WHITE}]hydra[/] [dim]<args>[/]                       [cyan]hydra -l root -P rockyou.txt ssh://10.0.0.1[/]
  [bold {WHITE}]searchsploit[/] [dim]<query>[/]               [cyan]searchsploit apache 2.4.49[/]

[bold {CYAN}]── LOOT & SCOPE ──────────────────────────────────────────────────────────[/]
  [bold {WHITE}]loot[/]                                 Show all captured loot
  [bold {WHITE}]loot add[/] [dim]<type> <text>[/]             [cyan]loot add cred admin:password[/]
    Types: cred  hash  file  secret
  [bold {WHITE}]loot clear[/]                           Clear loot vault
  [bold {WHITE}]scope[/]                                Show current scope
  [bold {WHITE}]scope add[/] [dim]<cidr>[/]                   [cyan]scope add 10.0.0.0/24[/]
  [bold {WHITE}]scope strict[/]                         Block out-of-scope targets
  [bold {WHITE}]report[/]                               Generate Markdown pentest report
  [bold {WHITE}]report html[/]                          Generate self-contained HTML report

[bold {CYAN}]── SHELL & AI ────────────────────────────────────────────────────────────[/]
  [bold {WHITE}]![/][dim]<command>[/]                          Run any shell command: [cyan]!ls -la /tmp[/]
  [bold {WHITE}]explain[/]                              Switch to AI mode for output analysis
  [bold {WHITE}]ai[/]                                   Switch to AI mode

[bold {CYAN}]── CHEAT SHEETS ──────────────────────────────────────────────────────────[/]
  [bold {WHITE}]help[/] [dim]<tool>[/]                         [cyan]help nmap[/]  [cyan]help sqlmap[/]  [cyan]help hydra[/]  [cyan]help msfconsole[/]
    Available: nmap  masscan  sqlmap  msfvenom  nikto  nuclei  gobuster  hydra
               enum4linux  whatweb  searchsploit  crackmapexec  msfconsole
               shodan  subfinder

[bold {CYAN}]── SESSION & WORKSPACE ───────────────────────────────────────────────────[/]
  [bold {WHITE}]sessions[/]                             List active MSF sessions
  [bold {WHITE}]session[/] [dim]<id>[/]                        Interact with session
  [bold {WHITE}]postex sessions[/]                      List registered post-ex sessions
  [bold {WHITE}]postex register[/] [dim]<host> [platform] [user][/]   Register a shell session
  [bold {WHITE}]postex enum[/] [dim]<id>[/]                    Print auto-enum commands for session
  [bold {WHITE}]postex pivot[/] [dim]<id>[/]                   Suggest pivot routes from session
  [bold {WHITE}]postex loot[/] [dim]<id> <cmd output>[/]       Extract creds/hashes from output
  [bold {WHITE}]note[/] [dim]<text>[/]                         Add a note to current workspace
  [bold {WHITE}]workspace[/]                            Show workspace status
  [bold {WHITE}]workspace save[/] / [bold {WHITE}]load[/] / [bold {WHITE}]new[/]       Persist session across runs

[bold {CYAN}]── AI PROVIDERS & MODELS ─────────────────────────────────────────────────[/]
  [bold {WHITE}]providers[/]                            Open the providers & models panel
  [bold {WHITE}]model list[/]                           List available SpectreBot variants
  [bold {WHITE}]model download[/] [dim]<name>[/]               [cyan]model download spectrenet-7b[/]
  [bold {WHITE}]model status[/]                         Show downloaded models + disk usage
  [bold {WHITE}]model remove[/] [dim]<name>[/]                  Delete a downloaded adapter

  Providers (configure in config.yaml):
    [bold {WHITE}]ollama[/]       Local — [dim]ollama_url: http://localhost:11434[/]
    [bold {WHITE}]openai[/]       openai.com — [dim]openai_api_key: sk-...[/]
    [bold {WHITE}]anthropic[/]    console.anthropic.com — [dim]anthropic_api_key: sk-ant-...[/]
    [bold {WHITE}]groq[/]         console.groq.com (free) — [dim]groq_api_key: gsk_...[/]
    [bold {WHITE}]openrouter[/]   openrouter.ai — [dim]openrouter_api_key: sk-or-...[/]
    [bold {WHITE}]spectre[/]      SpectreBot on Together.ai — [dim]together_api_key: ...[/]
    [bold {WHITE}]local[/]        Downloaded SpectreBot — [dim]local_model_name: spectrenet-7b[/]

  SpectreBot variants (snet model download <name>):
    [bold {WHITE}]spectrenet-mini[/]   3.8B Phi-3  — 4 GB+ VRAM or CPU
    [bold {WHITE}]spectrenet-7b[/]     7B Mistral  — 8 GB+ VRAM   (recommended)
    [bold {WHITE}]spectrenet-8b[/]     8B Llama 3.1 — 10 GB+ VRAM

  Training your own SpectreBot:
    1. [dim]snet train export --output training_data[/]
    2. Upload [dim]training_data.train.jsonl[/] to Kaggle as a Dataset
    3. Open [dim]notebooks/spectrenet_finetune.ipynb[/] on Kaggle (free T4 GPU)
    4. Run all cells → download adapter → [dim]snet model status[/]

[bold {CYAN}]── TOOLS & SETUP ─────────────────────────────────────────────────────────[/]
  [bold {WHITE}]tools[/]                                Show tool availability (OK / --)
  [bold {WHITE}]tools install[/]                        Show install commands for missing tools
  [dim](Full install commands also available outside SpectreNet: snet tools install)[/]

[bold {CYAN}]── NAVIGATION ────────────────────────────────────────────────────────────[/]
  [bold {WHITE}]↑ / ↓[/]                                Command history navigation
  [bold {WHITE}]F1[/]  [dim]/ help[/]                         This screen
  [bold {WHITE}]F2[/]                                   Toggle host/findings panel
  [bold {WHITE}]F3[/]                                   Toggle network map
  [bold {WHITE}]Ctrl+L[/]  [dim]/ clear[/]                    Clear output feed
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
  [bold {WHITE}]enum4linux  whatweb  searchsploit  crackmapexec  shodan  subfinder[/]
  [bold {WHITE}]scan[/] [dim]<profile> <target>[/]  quick  full  stealth  web  udp  vuln  os
  [bold {WHITE}]![/][dim]<command>[/]               Shell passthrough: [cyan]!ls /tmp[/]

[bold {CYAN}]── LOOT & SCOPE ──────────────────────────────────────────────────────────[/]
  [bold {WHITE}]loot[/]                    Show all loot    [bold {WHITE}]loot add[/] [dim]<type> <text>[/]
  [bold {WHITE}]scope[/]                   Show scope       [bold {WHITE}]scope add[/] [dim]<cidr>[/]
  [bold {WHITE}]report[/]                  Generate Markdown report
  [bold {WHITE}]report html[/]             Generate self-contained HTML report

[bold {CYAN}]── POST-EXPLOITATION ─────────────────────────────────────────────────────[/]
  [bold {WHITE}]postex sessions[/]         List registered sessions
  [bold {WHITE}]postex register[/] [dim]<host>[/]   Register a new session
  [bold {WHITE}]postex enum[/] [dim]<id>[/]         Print auto-enum commands
  [bold {WHITE}]postex pivot[/] [dim]<id>[/]        Suggest pivot routes

[bold {CYAN}]── CHEAT SHEETS ──────────────────────────────────────────────────────────[/]
  [bold {WHITE}]help[/] [dim]<tool>[/]               [cyan]help nmap[/]  [cyan]help sqlmap[/]  [cyan]help msfconsole[/]
    Also: enum4linux  whatweb  searchsploit  crackmapexec  shodan  subfinder

[bold {CYAN}]── WORKSPACE & NOTES ─────────────────────────────────────────────────────[/]
  [bold {WHITE}]note[/] [dim]<text>[/]               Add a note to current workspace
  [bold {WHITE}]workspace[/] / save / load / new

[bold {CYAN}]── AI PROVIDERS & MODELS ─────────────────────────────────────────────────[/]
  [bold {WHITE}]providers[/]               Open the providers & models panel
  [bold {WHITE}]model list[/]              List available SpectreBot variants
  [bold {WHITE}]model download[/] [dim]<name>[/]    [cyan]model download spectrenet-7b[/]
  [bold {WHITE}]model status[/]            Show downloaded models + disk usage
    Providers: ollama · openai · anthropic · groq · openrouter · spectre · local
    SpectreBot: spectrenet-mini (3.8B)  spectrenet-7b (7B)  spectrenet-8b (8B)
    See [bold {WHITE}]help models[/] for full setup guide (config keys, Kaggle training)

[bold {CYAN}]── TOOLS & SETUP ─────────────────────────────────────────────────────────[/]
  [bold {WHITE}]tools[/]                   Show tool availability (OK / --)
  [bold {WHITE}]tools install[/]           Show install commands for missing tools
  [dim](Full install commands also available outside SpectreNet: snet tools install)[/]

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
