import re
import shutil
from spectrenet.wrappers.base import ToolWrapper

_USER_RE   = re.compile(r"user:\[(\S+)\]")
_GROUP_RE  = re.compile(r"group:\[([^\]]+)\]")
_SHARE_RE  = re.compile(r"Mapping:\s+(\S+)")
_OS_RE     = re.compile(r"OS=\[([^\]]+)\]")


class Enum4linuxWrapper(ToolWrapper):
    tool_name = "enum4linux"

    def is_available(self) -> bool:
        return shutil.which("enum4linux") is not None

    def run(self, target: str, flags: str = "-a") -> dict:
        import subprocess
        args = ["enum4linux"] + flags.split() + [target]
        result = subprocess.run(args, capture_output=True, text=True, timeout=120)
        output = result.stdout + result.stderr
        return {
            "raw":    output,
            "users":  list(dict.fromkeys(_USER_RE.findall(output))),
            "groups": list(dict.fromkeys(_GROUP_RE.findall(output))),
            "shares": list(dict.fromkeys(_SHARE_RE.findall(output))),
            "os":     _OS_RE.search(output).group(1) if _OS_RE.search(output) else "",
        }

    @property
    def schema(self) -> dict:
        return {
            "users":  "list[str]",
            "groups": "list[str]",
            "shares": "list[str]",
            "os":     "str",
        }
