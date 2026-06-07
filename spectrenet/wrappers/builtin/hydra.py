from spectrenet.wrappers.base import ToolWrapper


class HydraWrapper(ToolWrapper):
    tool_name = "hydra"
    binary = "hydra"

    @property
    def schema(self) -> dict:
        return {"credentials": [{"login": str, "password": str}]}

    def run(self, target: str, service: str = "ssh", userlist: str = "", passlist: str = "", **kwargs) -> dict:
        import subprocess
        cmd = ["hydra"]
        if userlist:
            cmd += ["-L", userlist]
        if passlist:
            cmd += ["-P", passlist]
        cmd += [f"{service}://{target}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        creds = []
        for line in result.stdout.splitlines():
            if "] login:" in line:
                parts = line.split("login:")
                if len(parts) > 1:
                    login_pass = parts[1].split("password:")
                    creds.append({
                        "login": login_pass[0].strip(),
                        "password": login_pass[1].strip() if len(login_pass) > 1 else "",
                    })
        return {"credentials": creds}
