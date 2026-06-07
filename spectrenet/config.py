from dataclasses import dataclass, field
from pathlib import Path
import yaml

@dataclass
class Config:
    model_backend: str = "ollama"
    model_name: str = "llama3.1:70b"
    ollama_url: str = "http://localhost:11434"
    openai_base_url: str = "https://api.openai.com"
    openai_api_key: str = ""
    together_api_key: str = ""
    together_model: str = "spectrenet/spectre-70b"
    storage_backend: str = "sqlite"
    db_path: str = "spectrenet.db"
    server_port: int = 7777
    operator_name: str = "operator"
    log_level: str = "INFO"
    scope: list = field(default_factory=list)
    scope_strict: bool = False

def load_config(path: Path) -> Config:
    path = Path(path)
    if not path.exists():
        return Config()
    data = yaml.safe_load(path.read_text()) or {}
    known = {f for f in Config.__dataclass_fields__}
    filtered = {k: v for k, v in data.items() if k in known}
    return Config(**filtered)
