import argparse
import sys
from pathlib import Path
from spectrenet.config import load_config
from spectrenet.logging_setup import setup_logging
from spectrenet.wrappers.registry import WrapperRegistry
from spectrenet.engines.recon import ReconEngine
from spectrenet.tui.app import SpectreNetApp


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spectrenet",
        description="SpectreNet — Always one step ahead",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Subcommands:\n"
            "  spectrenet            Launch interactive TUI\n"
            "  spectrenet server     Start the team collaboration server\n"
            "\n"
            "Use --model to skip the startup selector for scripting or quick re-launch."
        ),
    )
    parser.add_argument("--config",   default="config.yaml", metavar="FILE")
    parser.add_argument("--operator", default=None, metavar="NAME",
                        help="Operator name (overrides config operator_name)")
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
    parser.add_argument("--db",           default=None, metavar="URL",
                        help="PostgreSQL DSN (postgresql://user:pass@host/db) — overrides SQLite")

    sub = parser.add_subparsers(dest="subcommand")
    srv = sub.add_parser("server", help="Start the team collaboration server")
    srv.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    srv.add_argument("--port", type=int, default=8888, help="Bind port (default: 8888)")
    return parser


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    # ── Team server subcommand ─────────────────────────────────────────────────
    if args.subcommand == "server":
        try:
            from spectrenet.server.app import serve
            print(f"Starting SpectreNet team server on {args.host}:{args.port}")
            serve(host=args.host, port=args.port)
        except ImportError:
            print("fastapi and uvicorn are required: pip install fastapi uvicorn")
            sys.exit(1)
        return

    cfg = load_config(Path(args.config))
    if args.operator:
        cfg.operator_name = args.operator
    if args.db:
        cfg.storage_backend = "postgresql"
        cfg.db_path = args.db
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
