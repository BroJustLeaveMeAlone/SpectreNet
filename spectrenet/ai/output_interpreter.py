from __future__ import annotations
import json
from typing import Any

_SEVERITY_MAP = {
    "CRITICAL": "CRITICAL", "HIGH": "HIGH",
    "MED": "MED", "MEDIUM": "MED", "LOW": "LOW", "INFO": "INFO",
}

_SESSION_SYSTEM = (
    "You are a penetration testing assistant. "
    "Given post-exploitation command output, extract a JSON array of findings. "
    'Each finding must match: {"type":str,"ip":str,"port":int|null,"service":str,'
    '"version":str,"severity":str,"detail":str,"raw":str}. '
    "severity: CRITICAL=SYSTEM/root shell or clear creds, HIGH=domain creds, "
    "MED=local creds, INFO otherwise. Return ONLY the JSON array, no markdown."
)


class OutputInterpreter:
    def __init__(self, model: Any | None = None) -> None:
        self._model = model

    def from_recon(self, recon_result: dict) -> list[dict]:
        findings: list[dict] = []
        for host in recon_result.get("hosts", []):
            ip = host.get("ip", "")
            for port_info in host.get("ports", []):
                port = port_info.get("port")
                service = port_info.get("service", "")
                version = port_info.get("version", "")
                findings.append({
                    "type":     "open_port",
                    "ip":       ip,
                    "port":     port,
                    "service":  service,
                    "version":  version,
                    "severity": "INFO",
                    "detail":   f"{service} {version} on port {port}".strip(),
                    "raw":      str(port_info),
                })
        return findings

    def from_web_vuln(self, vuln_result: dict) -> list[dict]:
        findings: list[dict] = []
        for vuln in vuln_result.get("vulnerabilities", []):
            severity = _SEVERITY_MAP.get(vuln.get("severity", "INFO").upper(), "INFO")
            findings.append({
                "type":     "vulnerability",
                "ip":       vuln.get("ip", ""),
                "port":     vuln.get("port"),
                "service":  vuln.get("type", ""),
                "version":  "",
                "severity": severity,
                "detail":   f"{vuln.get('type', '')} at {vuln.get('url', '')}",
                "raw":      str(vuln),
            })
        return findings

    def from_session_output(self, command: str, output: str) -> list[dict]:
        if self._model is not None:
            try:
                user_prompt = f"Command: {command}\nOutput:\n{output}"
                raw = self._model.complete(_SESSION_SYSTEM, user_prompt)
                parsed = json.loads(raw)
                if isinstance(parsed, list) and parsed:
                    return parsed
            except Exception:
                pass
        return [{
            "type":     "post_ex",
            "ip":       "",
            "port":     None,
            "service":  "",
            "version":  "",
            "severity": "INFO",
            "detail":   output,
            "raw":      output,
        }]
