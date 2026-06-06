# spectrenet/engines/recon.py
import logging

log = logging.getLogger("spectrenet")

class ReconEngine:
    """Orchestrates recon tool wrappers via the registry."""

    def __init__(self, registry):
        self.registry = registry

    def scan(self, tool: str, target: str, **kwargs) -> dict:
        if tool not in self.registry.available():
            raise ValueError(f"Recon tool '{tool}' is not available")
        log.info("Recon scan: tool=%s target=%s", tool, target)
        wrapper = self.registry.get(tool)
        return wrapper.run(target=target, **kwargs)
