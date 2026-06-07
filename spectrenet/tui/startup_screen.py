from __future__ import annotations
import logging
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Input, RadioSet, RadioButton, Label
from textual.containers import Container, Horizontal, Vertical
from spectrenet.theme import CYAN, CYAN_DIM, NAVY, NAVY_DEEP, NAVY_LIGHT, GREY, WHITE, ERROR

log = logging.getLogger("spectrenet")

_LOGO = """\
   ____                 _           _   _      _
  / ___| _ __  ___  ___| |_ _ __ __| \\ | | ___| |_
  \\___ \\| '_ \\/ _ \\/ __| __| '__/ _ \\ \\| |/ _ \\ __|
   ___) | |_) |  __/ (__| |_| | |  __/ |\\  |  __/ |_
  |____/| .__/ \\___|\\___|\\__|_|  \\___|_| \\_|\\___|\\__|
        |_|\
"""


class ModeSelectScreen(Screen):
    """Initial mode selection — shown every time SpectreNet starts."""

    DEFAULT_CSS = f"""
    ModeSelectScreen {{
        background: {NAVY_DEEP};
        align: center middle;
    }}
    #card {{
        width: 64;
        height: auto;
        background: {NAVY};
        border: round {CYAN};
        padding: 2 3;
    }}
    #logo {{
        color: {CYAN};
        text-style: bold;
        margin-bottom: 1;
    }}
    #tagline {{
        color: {GREY};
        margin-bottom: 2;
        text-align: center;
    }}
    #divider {{
        height: 1;
        border-top: solid {NAVY_LIGHT};
        margin-bottom: 1;
    }}
    .mode-btn {{
        width: 100%;
        height: 3;
        margin-bottom: 1;
        border: solid {NAVY_LIGHT};
    }}
    #classic-btn {{
        background: {NAVY};
        color: {WHITE};
    }}
    #classic-btn:hover {{
        background: {NAVY_LIGHT};
        border: solid {CYAN};
    }}
    #ai-btn {{
        background: {CYAN};
        color: {NAVY_DEEP};
        text-style: bold;
    }}
    #ai-btn:hover {{
        background: {CYAN_DIM};
    }}
    #hint {{
        color: {GREY};
        text-align: center;
        margin-top: 1;
    }}
    """

    def compose(self) -> ComposeResult:
        with Container(id="card"):
            yield Static(_LOGO, id="logo")
            yield Static("Always one step ahead", id="tagline")
            yield Static("", id="divider")
            yield Button("[1]  Classic Mode     Direct tool control", id="classic-btn", classes="mode-btn")
            yield Button("[2]  AI Mode          Autonomous or approval-gated", id="ai-btn", classes="mode-btn")
            yield Static("[dim]Press 1 / 2  or  click to select[/]", id="hint")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "classic-btn":
            self.app.enter_classic_mode()
        elif event.button.id == "ai-btn":
            self.app.push_screen(AIConfigScreen())

    def on_key(self, event) -> None:
        if event.key == "1":
            self.app.enter_classic_mode()
        elif event.key == "2":
            self.app.push_screen(AIConfigScreen())


class AIConfigScreen(Screen):
    """Configure AI backend before entering AI mode."""

    DEFAULT_CSS = f"""
    AIConfigScreen {{
        background: {NAVY_DEEP};
        align: center middle;
    }}
    #card {{
        width: 64;
        height: auto;
        background: {NAVY};
        border: round {CYAN};
        padding: 2 3;
    }}
    #title {{
        color: {CYAN};
        text-style: bold;
        margin-bottom: 1;
        border-bottom: solid {NAVY_LIGHT};
        padding-bottom: 1;
    }}
    RadioSet {{
        background: {NAVY};
        border: none;
        margin-bottom: 1;
    }}
    Label {{
        color: {GREY};
        margin-top: 1;
    }}
    Input {{
        border: solid {NAVY_LIGHT};
        background: {NAVY_DEEP};
        color: {WHITE};
        margin-bottom: 0;
    }}
    Input:focus {{
        border: solid {CYAN};
    }}
    #error-msg {{
        color: {ERROR};
        height: 1;
        margin-top: 1;
    }}
    #btn-row {{
        margin-top: 2;
        height: 3;
    }}
    #connect-btn {{
        background: {CYAN};
        color: {NAVY_DEEP};
        text-style: bold;
        width: 1fr;
    }}
    #back-btn {{
        background: {NAVY};
        color: {GREY};
        border: solid {NAVY_LIGHT};
        width: 1fr;
        margin-left: 1;
    }}
    """

    _OLLAMA_URL = "http://localhost:11434"
    _OLLAMA_MODEL = "llama3.1:70b"

    def compose(self) -> ComposeResult:
        with Container(id="card"):
            yield Static("Configure AI Backend", id="title")
            yield RadioSet(
                RadioButton("Ollama  (local)", id="rb-ollama", value=True),
                RadioButton("OpenAI-compatible  (DeepSeek, Qwen, LM Studio, vLLM...)", id="rb-openai"),
                id="backend-radio",
            )
            yield Label("Model name")
            yield Input(placeholder=self._OLLAMA_MODEL, id="model-input")
            yield Label("API endpoint")
            yield Input(placeholder=self._OLLAMA_URL, id="url-input")
            yield Label("API key  (leave blank for Ollama)")
            yield Input(placeholder="sk-...", id="key-input", password=True)
            yield Static("", id="error-msg")
            with Horizontal(id="btn-row"):
                yield Button("Connect & Start", id="connect-btn")
                yield Button("Back", id="back-btn")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        url_input = self.query_one("#url-input", Input)
        model_input = self.query_one("#model-input", Input)
        if str(event.pressed.id) == "rb-ollama":
            url_input.placeholder = self._OLLAMA_URL
            model_input.placeholder = self._OLLAMA_MODEL
        else:
            url_input.placeholder = "https://api.deepseek.com"
            model_input.placeholder = "deepseek-chat"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect-btn":
            self._try_connect()
        elif event.button.id == "back-btn":
            self.app.pop_screen()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()

    def _try_connect(self) -> None:
        error = self.query_one("#error-msg", Static)
        error.update("")

        radio = self.query_one("#backend-radio", RadioSet)
        is_ollama = radio.pressed_index == 0

        model_val = self.query_one("#model-input", Input).value.strip()
        url_val   = self.query_one("#url-input",   Input).value.strip()
        key_val   = self.query_one("#key-input",   Input).value.strip()

        try:
            if is_ollama:
                from spectrenet.model.ollama_backend import OllamaBackend
                model = OllamaBackend(
                    model=model_val or self._OLLAMA_MODEL,
                    url=url_val or self._OLLAMA_URL,
                )
            else:
                from spectrenet.model.openai_backend import OpenAIBackend
                if not url_val:
                    error.update("API endpoint is required for OpenAI-compatible backends.")
                    return
                model = OpenAIBackend(
                    model=model_val or "deepseek-chat",
                    base_url=url_val,
                    api_key=key_val,
                )
            # Pop config screen (and mode select if present) then launch AI mode
            self.app.pop_screen()
            self.app.enter_ai_mode(model)
        except Exception as exc:
            log.warning("AI backend init failed: %s", exc)
            error.update(f"Failed: {exc}")
