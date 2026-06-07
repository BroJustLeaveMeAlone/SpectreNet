import argparse
from pathlib import Path
from spectrenet.config import load_config
from spectrenet.logging_setup import setup_logging
from spectrenet.wrappers.registry import WrapperRegistry
from spectrenet.engines.recon import ReconEngine
from spectrenet.tui.app import SpectreNetApp


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="spectrenet",
        description="SpectreNet — Always one step ahead",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Without flags, SpectreNet shows the interactive mode selector on startup.\n"
            "Use --model to skip the selector for scripting or quick re-launch."
        ),
    )
    parser.add_argument("--config", default="config.yaml", metavar="FILE")
    parser.add_argument(
        "--model", choices=["ollama", "openai", "none"], default=None,
        metavar="BACKEND",
        help="Skip startup mode selector and launch with this AI backend (optional)",
    )
    parser.add_argument("--openai-base-url", default=None, metavar="URL",
                        help="OpenAI-compatible API base URL")
    parser.add_argument("--openai-api-key",  default=None, metavar="KEY",
                        help="API key for OpenAI-compatible backend")
    parser.add_argument("--msf-host",     default="127.0.0.1")
    parser.add_argument("--msf-port",     type=int, default=55553)
    parser.add_argument("--msf-password", default="msf")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    log = setup_logging(cfg.log_level)
    log.info("Starting SpectreNet (operator=%s)", cfg.operator_name)

    registry = WrapperRegistry()
    registry.discover()
    recon = ReconEngine(registry)

    msf_bridge = None
    try:
        from spectrenet.msf.bridge import MsfBridge
        msf_bridge = MsfBridge(
            host=args.msf_host,
            port=args.msf_port,
            password=args.msf_password,
        )
        msf_bridge.connect()
    except ModuleNotFoundError:
        log.debug("pymetasploit3 not installed — MSF bridge disabled (install with: pip install pymetasploit3)")
    except Exception as e:
        log.debug("MSF bridge unavailable: %s", e)

    app = SpectreNetApp(registry=registry, recon=recon, config=cfg, msf_bridge=msf_bridge)

    # --model skips the interactive mode selector
    if args.model and args.model != "none":
        model = None
        if args.model == "ollama":
            try:
                from spectrenet.model.ollama_backend import OllamaBackend
                model = OllamaBackend(model=cfg.model_name, url=cfg.ollama_url)
            except Exception as e:
                log.warning("Ollama init failed: %s — falling back to mode selector", e)
        elif args.model == "openai":
            try:
                from spectrenet.model.openai_backend import OpenAIBackend
                model = OpenAIBackend(
                    model=cfg.model_name,
                    base_url=args.openai_base_url or cfg.openai_base_url,
                    api_key=args.openai_api_key  or cfg.openai_api_key,
                )
            except Exception as e:
                log.warning("OpenAI init failed: %s — falling back to mode selector", e)

        if model is not None:
            # Monkey-patch on_mount to skip mode selector and go straight to AI mode
            _orig_mount = app.on_mount

            def _ai_mount():
                from spectrenet.tui.ai_screen import AIScreen
                app.push_screen(AIScreen(
                    model=model, registry=registry, recon=recon, msf_bridge=msf_bridge
                ))
            app.on_mount = _ai_mount
        else:
            # --model none OR failed init → Classic mode directly
            _orig_mount = app.on_mount

            def _classic_mount():
                from spectrenet.tui.classic_screen import ClassicScreen
                app.push_screen(ClassicScreen(
                    registry=registry, recon=recon, msf_bridge=msf_bridge
                ))
            if args.model == "none":
                app.on_mount = _classic_mount

    app.run()


if __name__ == "__main__":
    main()
