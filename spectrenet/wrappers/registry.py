# spectrenet/wrappers/registry.py
import importlib.util
import inspect
import logging
from pathlib import Path
from spectrenet.wrappers.base import ToolWrapper

log = logging.getLogger("spectrenet")


class WrapperRegistry:
    """Discovers ToolWrapper subclasses from builtin + custom directories."""

    def __init__(self, extra_dirs=None):
        here = Path(__file__).parent
        self._dirs = [here / "builtin", here / "custom"]
        if extra_dirs:
            self._dirs.extend(Path(d) for d in extra_dirs)
        self._wrappers: dict[str, ToolWrapper] = {}

    def discover(self) -> None:
        for d in self._dirs:
            if not d.exists():
                continue
            for py in sorted(d.glob("*.py")):
                if py.name == "__init__.py":
                    continue
                self._load_file(py)

    def _load_file(self, py: Path) -> None:
        spec = importlib.util.spec_from_file_location(f"_snwrap_{py.stem}", py)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:  # a broken wrapper must not crash startup
            log.warning("Failed to load wrapper %s: %s", py.name, e)
            return
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, ToolWrapper) and obj is not ToolWrapper:
                if not getattr(obj, "tool_name", ""):
                    continue
                instance = obj()
                self._wrappers[instance.tool_name] = instance
                status = "available" if instance.is_available() else "unavailable"
                log.info("Registered wrapper '%s' (%s)", instance.tool_name, status)

    def names(self) -> list[str]:
        return sorted(self._wrappers)

    def get(self, name: str) -> ToolWrapper:
        return self._wrappers[name]

    def available(self) -> list[str]:
        return sorted(n for n, w in self._wrappers.items() if w.is_available())
