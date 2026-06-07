from textual.app import App
from spectrenet import APP_NAME, TAGLINE
from spectrenet.theme import NAVY_DEEP


class SpectreNetApp(App):
    """SpectreNet — Always one step ahead.

    Thin shell: holds shared resources and routes between screens.
    All UI logic lives in the individual Screen subclasses.
    """

    CSS = f"Screen {{ background: {NAVY_DEEP}; }}"
    TITLE = APP_NAME
    SUB_TITLE = TAGLINE

    def __init__(self, registry, recon, config=None, msf_bridge=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.registry = registry
        self.recon = recon
        self.config = config
        self.msf_bridge = msf_bridge

    def on_mount(self) -> None:
        from spectrenet.tui.startup_screen import ModeSelectScreen
        self.push_screen(ModeSelectScreen())

    def enter_classic_mode(self) -> None:
        from spectrenet.tui.classic_screen import ClassicScreen
        self.push_screen(ClassicScreen(
            registry=self.registry,
            recon=self.recon,
            msf_bridge=self.msf_bridge,
        ))

    def enter_ai_mode(self, model) -> None:
        from spectrenet.tui.ai_screen import AIScreen
        self.push_screen(AIScreen(
            model=model,
            registry=self.registry,
            recon=self.recon,
            msf_bridge=self.msf_bridge,
        ))
