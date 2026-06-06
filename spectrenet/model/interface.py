# spectrenet/model/interface.py
from abc import ABC, abstractmethod

class ModelInterface(ABC):
    """Swappable model backend. All AI core components call complete()."""

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return the model's completion for the given prompts."""
