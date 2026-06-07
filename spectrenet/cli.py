import argparse
from pathlib import Path
from spectrenet.config import load_config
from spectrenet.logging_setup import setup_logging
from spectrenet.wrappers.registry import WrapperRegistry
from spectrenet.engines.recon import ReconEngine
from spectrenet.tui.app import SpectreNetApp


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="spectrenet", description="SpectreNet — Always one step ahead"
    )
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--model", choices=["ollama", "openai", "none"], default=None,
                        help="AI model backend (overrides config)")
    parser.add_argument("--openai-base-url", default=None,
                        help="OpenAI-compatible API base URL (e.g. https://api.deepseek.com)")
    parser.add_argument("--openai-api-key", default=None,
                        help="API key for OpenAI-compatible backend")
    parser.add_argument("--msf-host", default="127.0.0.1", help="msfrpcd host")
    parser.add_argument("--msf-port", type=int, default=55553, help="msfrpcd port")
    parser.add_argument("--msf-password", default="msf", help="msfrpcd password")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    log = setup_logging(cfg.log_level)
    log.info("Starting SpectreNet (operator=%s)", cfg.operator_name)

    registry = WrapperRegistry()
    registry.discover()
    recon = ReconEngine(registry)

    model = None
    backend = args.model or cfg.model_backend
    if backend == "ollama":
        try:
            from spectrenet.model.ollama_backend import OllamaBackend
            model = OllamaBackend(model=cfg.model_name, url=cfg.ollama_url)
            log.info("AI mode: Ollama (%s)", cfg.model_name)
        except Exception as e:
            log.warning("Failed to initialise Ollama backend: %s — running in Classic mode", e)
    elif backend == "openai":
        try:
            from spectrenet.model.openai_backend import OpenAIBackend
            base_url = args.openai_base_url or cfg.openai_base_url
            api_key  = args.openai_api_key  or cfg.openai_api_key
            model = OpenAIBackend(model=cfg.model_name, base_url=base_url, api_key=api_key)
            log.info("AI mode: OpenAI-compatible (%s @ %s)", cfg.model_name, base_url)
        except Exception as e:
            log.warning("Failed to initialise OpenAI backend: %s — running in Classic mode", e)

    msf_bridge = None
    try:
        from spectrenet.msf.bridge import MsfBridge
        msf_bridge = MsfBridge(
            host=args.msf_host,
            port=args.msf_port,
            password=args.msf_password,
        )
        msf_bridge.connect()
    except Exception as e:
        log.warning("MSF bridge unavailable: %s", e)

    SpectreNetApp(registry=registry, recon=recon, model=model, msf_bridge=msf_bridge).run()


if __name__ == "__main__":
    main()
