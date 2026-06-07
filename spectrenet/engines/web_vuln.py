from __future__ import annotations
import logging

_log = logging.getLogger(__name__)


class WebVulnEngine:
    """Orchestrates web vulnerability wrappers via the wrapper registry."""

    def __init__(self, registry) -> None:
        self.registry = registry

    def scan(self, tool: str, target: str, **kwargs) -> dict:
        if tool not in self.registry.available():
            raise ValueError(f"Web vuln tool '{tool}' is not available in registry")
        wrapper = self.registry.get(tool)
        _log.info("WebVulnEngine: starting %s → %s", tool, target)
        result = wrapper.run(target=target, **kwargs)
        vuln_count = len(result.get("vulnerabilities", result.get("findings", [])))
        _log.info("WebVulnEngine: %s complete — %d findings", tool, vuln_count)
        return result
