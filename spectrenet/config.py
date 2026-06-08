from dataclasses import dataclass, field
from pathlib import Path
import yaml

@dataclass
class Config:
    # AI backend selector: ollama | openai | anthropic | groq | openrouter | spectre | local | none
    model_backend: str = "ollama"
    model_name: str = "llama3.1:70b"

    # Ollama
    ollama_url: str = "http://localhost:11434"

    # OpenAI-compatible (OpenAI, LM Studio, vLLM, custom)
    openai_base_url: str = "https://api.openai.com"
    openai_api_key: str = ""

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # Groq (free tier available — fast inference)
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-70b-versatile"

    # OpenRouter (routes to many providers)
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.1-70b-instruct"

    # Together.ai (SpectreBot hosted fine-tune)
    together_api_key: str = ""
    together_model: str = "spectrenet/spectre-70b"

    # Local SpectreBot adapter (downloaded via snet model download)
    local_model_name: str = "spectrenet-7b"
    local_model_path: str = ""   # auto-resolved from ~/.spectrenet/models if empty

    # Storage
    storage_backend: str = "sqlite"
    db_path: str = "spectrenet.db"

    # Team server
    server_port: int = 7777

    # Operator
    operator_name: str = "operator"
    log_level: str = "INFO"

    # Scope
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
