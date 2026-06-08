from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, RichLog
from textual.containers import Vertical
from spectrenet.theme import CYAN, CYAN_DIM, GREY, WHITE, SUCCESS, WARNING, NAVY, NAVY_LIGHT, NAVY_DEEP

_PROVIDERS = [
    ("ollama",      "Ollama",       "Local models via Ollama (llama3.1, mistral, …)",    "ollama_url",          ""),
    ("openai",      "OpenAI",       "GPT-4o, GPT-4-turbo — openai.com",                  "openai_api_key",      "openai_base_url"),
    ("anthropic",   "Anthropic",    "Claude 3.5 Sonnet/Haiku — console.anthropic.com",   "anthropic_api_key",   ""),
    ("groq",        "Groq",         "Free fast inference (Llama, Mixtral) — console.groq.com", "groq_api_key",  ""),
    ("openrouter",  "OpenRouter",   "100+ models via one key — openrouter.ai",            "openrouter_api_key",  ""),
    ("spectre",     "SpectreBot/Together", "Hosted SpectreBot on Together.ai — together.ai", "together_api_key", ""),
    ("local",       "SpectreBot/Local",   "Downloaded SpectreBot adapter (snet model download)", "local_model_path", "local_model_name"),
]


def _key_status(cfg, key_field: str) -> str:
    val = getattr(cfg, key_field, "")
    if not key_field:
        return f"[{SUCCESS}]always available[/]"
    if val:
        masked = val[:4] + "…" + val[-4:] if len(val) > 8 else "****"
        return f"[{SUCCESS}]configured[/] [{GREY}]({masked})[/]"
    return f"[{GREY}]not configured[/]"


class ProvidersScreen(Screen):
    """AI providers and SpectreBot model management screen."""

    BINDINGS = [("escape", "app.pop_screen", "Close")]

    DEFAULT_CSS = f"""
    ProvidersScreen {{
        background: {NAVY_DEEP};
        align: center middle;
    }}
    #panel {{
        width: 82;
        height: auto;
        max-height: 44;
        background: {NAVY};
        border: round {CYAN_DIM};
        padding: 1 2;
    }}
    #log {{
        height: 1fr;
        min-height: 28;
        background: {NAVY_DEEP};
        border: none;
        padding: 0;
    }}
    #close-btn {{
        width: 10;
        height: 1;
        background: {NAVY};
        color: {GREY};
        border: none;
        margin-top: 1;
    }}
    #close-btn:hover {{
        background: {NAVY_LIGHT};
        color: {CYAN};
    }}
    """

    def __init__(self, config=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._cfg = config

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static(
                f"[bold {CYAN}]◈ AI Providers & SpectreBot Models[/]  "
                f"[{GREY}]ESC to close[/]"
            )
            yield Static("")
            log = RichLog(highlight=True, markup=True, id="log")
            yield log
            yield Button("Close", id="close-btn")

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        cfg = self._cfg
        self._render(log, cfg)

    def _render(self, log: RichLog, cfg) -> None:
        log.write(f"[bold {CYAN}]── API Providers ──────────────────────────────────[/]")
        log.write(
            f"[{GREY}]Configure keys in config.yaml or set them via "
            f"[bold {CYAN}]snet config set-key <provider> <key>[/]\n[/]"
        )

        for backend_id, label, desc, key_field, extra_field in _PROVIDERS:
            status = _key_status(cfg, key_field) if cfg else f"[{GREY}]no config[/]"
            log.write(f"  [bold {WHITE}]{label:<22}[/]  {status}")
            log.write(f"  [{GREY}]  {desc}[/]")
            if extra_field and cfg:
                extra_val = getattr(cfg, extra_field, "")
                if extra_val:
                    log.write(f"  [{GREY}]  {extra_field}: {extra_val}[/]")
            log.write("")

        log.write(f"[bold {CYAN}]── SpectreBot Models ──────────────────────────────[/]")
        log.write(
            f"[{GREY}]Download with: [bold {CYAN}]snet model download <name>[/]   "
            f"or from the TUI: [bold {CYAN}]model download <name>[/]\n[/]"
        )

        try:
            from spectrenet.models.registry import list_models
            from spectrenet.models.downloader import is_downloaded, disk_usage_mb
            for m in list_models():
                dl = is_downloaded(m["name"])
                if dl:
                    mb   = disk_usage_mb(m["name"])
                    flag = f"[{SUCCESS}]✓ downloaded[/] [{GREY}]({mb:.0f} MB)[/]"
                else:
                    flag = f"[{GREY}]not downloaded[/]"
                log.write(
                    f"  [bold {WHITE}]{m['name']:<22}[/]  {flag}"
                )
                log.write(
                    f"  [{GREY}]  {m['description'][:60]}[/]"
                )
                log.write(
                    f"  [{GREY}]  Base: {m['base_model']}  "
                    f"Min VRAM: {m['min_vram_gb']} GB[/]"
                )
                log.write("")
        except Exception as e:
            log.write(f"[{WARNING}]Could not load model registry: {e}[/]")

        log.write(f"[bold {CYAN}]── Quick Setup Guide ──────────────────────────────[/]")
        log.write(f"[{GREY}]Free options (no credit card required):[/]")
        log.write(f"  [bold {WHITE}]Ollama[/]  [{GREY}]ollama.com → pull llama3.1:8b → snet --model ollama[/]")
        log.write(f"  [bold {WHITE}]Groq  [/]  [{GREY}]console.groq.com → free API key → groq_api_key in config[/]")
        log.write(f"  [bold {WHITE}]SpectreBot/Local[/]  [{GREY}]snet model download spectrenet-7b → model_backend: local[/]")
        log.write("")
        log.write(f"[{GREY}]  See [bold {CYAN}]help models[/] for full documentation.[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.app.pop_screen()
