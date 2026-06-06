# spectrenet/wrappers/builtin/nmap.py
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from spectrenet.wrappers.base import ToolWrapper

class NmapWrapper(ToolWrapper):
    tool_name = "nmap"
    binary = "nmap"

    @property
    def schema(self) -> dict:
        return {"hosts": [{"ip": str, "ports": [{"port": int, "service": str, "version": str}]}]}

    def parse(self, xml_text: str) -> dict:
        root = ET.fromstring(xml_text)
        hosts = []
        for host in root.findall("host"):
            addr_el = host.find("address")
            ip = addr_el.get("addr") if addr_el is not None else ""
            ports = []
            for port in host.findall("./ports/port"):
                state = port.find("state")
                if state is None or state.get("state") != "open":
                    continue
                svc = port.find("service")
                ports.append({
                    "port": int(port.get("portid")),
                    "service": svc.get("name") if svc is not None else "",
                    "version": svc.get("version", "") if svc is not None else "",
                })
            hosts.append({"ip": ip, "ports": ports})
        return {"hosts": hosts}

    def run(self, target: str, flags: str = "-sV", **kwargs) -> dict:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "scan.xml"
            cmd = ["nmap", *flags.split(), "-oX", str(out), target]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return self.parse(out.read_text())
