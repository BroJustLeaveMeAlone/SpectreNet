from spectrenet.wrappers.base import ToolWrapper


class GobusterWrapper(ToolWrapper):
    tool_name = "gobuster"
    binary = "gobuster"

    @property
    def schema(self) -> dict:
        return {"findings": [{"path": str, "status": int}]}

    def run(self, target: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt", **kwargs) -> dict:
        import subprocess
        cmd = ["gobuster", "dir", "-u", target, "-w", wordlist]
        result = subprocess.run(cmd, capture_output=True, text=True)
        findings = []
        for line in result.stdout.splitlines():
            if "(Status:" in line:
                parts = line.split()
                try:
                    status = int(line.split("Status:")[1].split(")")[0].strip())
                except (ValueError, IndexError):
                    status = 0
                if parts:
                    findings.append({"path": parts[0], "status": status})
        return {"findings": findings}
