# spectrenet/cli.py
import argparse
from pathlib import Path
from spectrenet.config import load_config
from spectrenet.logging_setup import setup_logging
from spectrenet.wrappers.registry import WrapperRegistry
from spectrenet.engines.recon import ReconEngine
from spectrenet.tui.app import SpectreNetApp

def main() -> None:
    parser = argparse.ArgumentParser(prog="spectrenet", description="SpectreNet — Always one step ahead")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    log = setup_logging(cfg.log_level)
    log.info("Starting SpectreNet (operator=%s)", cfg.operator_name)

    registry = WrapperRegistry()
    registry.discover()
    recon = ReconEngine(registry)

    SpectreNetApp(registry=registry, recon=recon).run()

if __name__ == "__main__":
    main()
