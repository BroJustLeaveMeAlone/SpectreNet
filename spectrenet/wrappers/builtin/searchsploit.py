import json
import re
import shutil
from spectrenet.wrappers.base import ToolWrapper

_ROW_RE = re.compile(r"^(.+?)\s{2,}(\|\s*EDB-ID:\s*(\d+)|EDB-ID:\s*(\d+)|\S+/\S+)", re.MULTILINE)


class SearchsploitWrapper(ToolWrapper):
    tool_name = "searchsploit"

    def is_available(self) -> bool:
        return shutil.which("searchsploit") is not None

    def run(self, query: str, flags: str = "--json") -> dict:
        import subprocess
        if "--json" in flags:
            args = ["searchsploit", "--json"] + query.split()
        else:
            args = ["searchsploit"] + flags.split() + query.split()
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        return {"raw": result.stdout, "exploits": self._parse(result.stdout, "--json" in flags)}

    def _parse(self, output: str, is_json: bool) -> list[dict]:
        if is_json:
            try:
                data   = json.loads(output)
                result = []
                for item in data.get("RESULTS_EXPLOIT", []) + data.get("RESULTS_SHELLCODE", []):
                    result.append({
                        "title":    item.get("Title", ""),
                        "edb_id":   str(item.get("EDB-ID", "")),
                        "path":     item.get("Path", ""),
                        "type":     item.get("Type", ""),
                        "platform": item.get("Platform", ""),
                        "date":     item.get("Date", ""),
                    })
                return result
            except Exception:
                pass
        # Fallback: plain text parsing
        exploits = []
        for m in _ROW_RE.finditer(output):
            title  = m.group(1).strip()
            edb_id = m.group(3) or m.group(4) or ""
            if title and not title.startswith("-"):
                exploits.append({"title": title, "edb_id": edb_id, "path": "", "type": "", "platform": "", "date": ""})
        return exploits

    @property
    def schema(self) -> dict:
        return {
            "exploits": "list[{title, edb_id, path, type, platform, date}]"
        }
