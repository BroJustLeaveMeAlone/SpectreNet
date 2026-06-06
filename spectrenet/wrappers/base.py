# spectrenet/wrappers/base.py
from abc import ABC, abstractmethod

class ToolWrapper(ABC):
    """Base contract every tool wrapper must implement.

    Subclasses are autodiscovered from wrappers/builtin and wrappers/custom.
    """

    #: Unique tool identifier, e.g. "nmap". Must be set by subclass.
    tool_name: str = ""

    #: Name of the external binary required on PATH. Defaults to tool_name.
    binary: str = ""

    @property
    @abstractmethod
    def schema(self) -> dict:
        """Return a dict describing the normalized output structure."""

    @abstractmethod
    def run(self, **kwargs) -> dict:
        """Execute the tool and return output normalized to `schema`."""

    def is_available(self) -> bool:
        """True if the tool's binary is present on PATH."""
        import shutil
        return shutil.which(self.binary or self.tool_name) is not None
