from __future__ import annotations
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static
from spectrenet.theme import CYAN, GREY, WHITE, WARNING, SUCCESS, NAVY, NAVY_LIGHT


class FindingsPanel(Widget):
    """Sidebar host/port tracker. Toggle visibility with F2."""

    DEFAULT_CSS = f"""
    FindingsPanel {{
        width: 30;
        background: {NAVY};
        border-left: solid {NAVY_LIGHT};
        padding: 0 1;
        display: none;
    }}
    #fp-header {{
        color: {CYAN};
        text-style: bold;
        height: 2;
        border-bottom: solid {NAVY_LIGHT};
        padding-bottom: 1;
    }}
    #fp-body {{
        height: 1fr;
        color: {WHITE};
        overflow-y: auto;
        padding-top: 1;
    }}
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._hosts: dict[str, list[dict]] = {}

    def compose(self) -> ComposeResult:
        yield Static("", id="fp-header")
        yield Static("", id="fp-body")

    def on_mount(self) -> None:
        self._refresh()

    def add_hosts(self, hosts: dict[str, list[dict]]) -> None:
        for ip, ports in hosts.items():
            if ip not in self._hosts:
                self._hosts[ip] = list(ports)
            else:
                existing = {p["port"] for p in self._hosts[ip]}
                for p in ports:
                    if p["port"] not in existing:
                        self._hosts[ip].append(p)
        self._refresh()

    def clear_hosts(self) -> None:
        self._hosts.clear()
        self._refresh()

    def _refresh(self) -> None:
        header_w = self.query_one("#fp-header", Static)
        body_w   = self.query_one("#fp-body",   Static)

        if not self._hosts:
            header_w.update(f"[bold {CYAN}]Hosts  [dim {GREY}]F2 hide[/][/]")
            body_w.update(f"[{GREY}]No hosts yet.\n\nRun a scan to\npopulate.[/]")
            return

        total_ports = sum(len(p) for p in self._hosts.values())
        header_w.update(
            f"[bold {CYAN}]Hosts ({len(self._hosts)})[/]  [{GREY}]{total_ports} ports  F2 hide[/]"
        )

        lines: list[str] = []
        for ip, ports in self._hosts.items():
            lines.append(f"[bold {WHITE}]{ip}[/]")
            for p in sorted(ports, key=lambda x: x["port"])[:12]:
                port_num = p.get("port", "")
                svc      = p.get("service", "?")
                ver      = (p.get("version") or "")[:10]
                if svc in ("http", "https", "http-proxy", "http-alt"):
                    color = SUCCESS
                elif svc in ("ssh", "ftp", "telnet"):
                    color = WARNING
                elif svc in ("msrpc", "netbios-ssn", "microsoft-ds"):
                    color = WARNING
                else:
                    color = GREY
                ver_str = f" [dim]{ver}[/]" if ver else ""
                lines.append(f"  [{color}]:{port_num}[/] [{GREY}]{svc[:9]}[/]{ver_str}")
            if len(ports) > 12:
                lines.append(f"  [{GREY}]… +{len(ports) - 12} more[/]")
            lines.append("")

        body_w.update("\n".join(lines).rstrip())
