# spectrenet/logging_setup.py
import logging
from pathlib import Path
from rich.logging import RichHandler

def setup_logging(level: str = "INFO", log_file: str = "spectrenet.log") -> logging.Logger:
    logger = logging.getLogger("spectrenet")
    logger.setLevel(level)
    logger.handlers.clear()

    console = RichHandler(rich_tracebacks=True, show_path=False)
    console.setLevel(level)
    logger.addHandler(console)

    fh = logging.FileHandler(Path(log_file), encoding="utf-8")
    fh.setLevel("DEBUG")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    ))
    logger.addHandler(fh)
    logger.propagate = False
    return logger
