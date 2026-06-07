"""Live network map widget — renders discovered hosts as a Rich text panel."""
from __future__ import annotations

from rich.text import Text
from rich.panel import Panel
from textual.widget import Widget
from textual.reactive import reactive
from spectrenet.theme import CYAN, NAVY, GREY, WHITE, SUCCESS, WARNING


class NetworkMapWidget(Widget):
    """ASCII network map panel that updates as hosts are discovered."""

    DEFAULT_CSS = f"""
    NetworkMapWidget {{
        height: auto;
        min-height: 6;
        background: {NAVY};
        border: round {CYAN};
        padding: 0 1;
    }}
    """

    hosts: reactive[dict] = reactive({}, layout=True)

    def render(self) -> Panel:
        if not self.hosts:
            return Panel(
                Text("  No hosts discovered yet.", style=f"dim {GREY}"),
                title=f"[bold {CYAN}] Network Map [/]",
                border_style=CYAN,
            )

        lines: list[str] = []
        lines.append(f"[{GREY}]  [gateway][/]")
        lines.append(f"[{GREY}]      │[/]")

        for i, (ip, ports) in enumerate(sorted(self.hosts.items())):
            connector = "├─" if i < len(self.hosts) - 1 else "└─"
            open_ports = [str(p.get("port", "")) for p in ports if p.get("port")]
            service_tags = []
            for p in ports[:4]:
                svc = p.get("service", "")
                port_num = p.get("port", "")
                if svc:
                    service_tags.append(f"[{CYAN}]{port_num}/{svc}[/]")
                elif port_num:
                    service_tags.append(f"[{GREY}]{port_num}[/]")

            host_line = f"[{GREY}]  {connector}[/] [{WHITE}]{ip}[/]"
            if service_tags:
                host_line += "  " + "  ".join(service_tags)
            if len(ports) > 4:
                host_line += f"  [{GREY}]+{len(ports) - 4} more[/]"
            lines.append(host_line)

            if i < len(self.hosts) - 1:
                lines.append(f"[{GREY}]      │[/]")

        body = "\n".join(lines)
        title = f"[bold {CYAN}] Network Map — {len(self.hosts)} host{'s' if len(self.hosts) != 1 else ''} [/]"
        return Panel(body, title=title, border_style=CYAN)

    def update_hosts(self, hosts: dict) -> None:
        self.hosts = dict(hosts)
