import re
import shutil
from spectrenet.wrappers.base import ToolWrapper

# WhatWeb log format: URL [status] Tech[version], Tech[version], ...
_ENTRY_RE = re.compile(
    r"^(https?://\S+)\s+\[(\d{3})\]\s+(.+)$", re.MULTILINE
)
_TECH_RE = re.compile(r"([A-Za-z0-9_\-\.]+)(?:\[([^\]]*)\])?")


class WhatWebWrapper(ToolWrapper):
    tool_name = "whatweb"

    def is_available(self) -> bool:
        return shutil.which("whatweb") is not None

    def run(self, target: str, flags: str = "--color=never") -> dict:
        import subprocess
        args = ["whatweb", "--color=never"] + flags.split() + [target]
        result = subprocess.run(args, capture_output=True, text=True, timeout=60)
        output = result.stdout + result.stderr
        return {"raw": output, "fingerprints": self._parse(output)}

    def _parse(self, output: str) -> list[dict]:
        results = []
        for m in _ENTRY_RE.finditer(output):
            url, status, tech_str = m.group(1), m.group(2), m.group(3)
            techs = []
            for tm in _TECH_RE.finditer(tech_str):
                name    = tm.group(1).strip()
                version = tm.group(2) or ""
                if name and name not in (",", ""):
                    techs.append({"name": name, "version": version})
            results.append({"url": url, "status": status, "technologies": techs})
        return results

    @property
    def schema(self) -> dict:
        return {
            "fingerprints": "list[{url, status, technologies: list[{name, version}]}]"
        }
