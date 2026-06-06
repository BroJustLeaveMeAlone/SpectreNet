# spectrenet/wrappers/builtin/masscan.py
import json
import subprocess
import tempfile
from pathlib import Path
from spectrenet.wrappers.base import ToolWrapper

class MasscanWrapper(ToolWrapper):
    tool_name = "masscan"
    binary = "masscan"

    @property
    def schema(self) -> dict:
        return {"hosts": [{"ip": str, "ports": [{"port": int, "service": str, "version": str}]}]}

    def parse(self, json_text: str) -> dict:
        raw = json.loads(json_text)
        hosts = []
        for entry in raw:
            ports = [
                {"port": int(p["port"]), "service": "", "version": ""}
                for p in entry.get("ports", [])
                if p.get("status", "open") == "open"
            ]
            hosts.append({"ip": entry["ip"], "ports": ports})
        return {"hosts": hosts}

    def run(self, target: str, ports: str = "1-1000", rate: int = 1000, **kwargs) -> dict:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "scan.json"
            cmd = ["masscan", target, "-p", ports, "--rate", str(rate), "-oJ", str(out)]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return self.parse(out.read_text())
