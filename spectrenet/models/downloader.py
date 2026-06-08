"""
Downloads SpectreBot LoRA adapters from HuggingFace Hub to ~/.spectrenet/models/.

Requires: pip install huggingface_hub
"""
from __future__ import annotations
import logging
import shutil
from pathlib import Path

log = logging.getLogger("spectrenet")

MODELS_DIR = Path.home() / ".spectrenet" / "models"

try:
    from huggingface_hub import snapshot_download as _hf_snapshot
    from huggingface_hub import HfApi as _HfApi
    _hf_available = True
except ImportError:
    _hf_available = False


def adapter_path_for(model_name: str) -> Path:
    """Return the local directory where the adapter should be stored."""
    return MODELS_DIR / model_name


def is_downloaded(model_name: str) -> bool:
    path = adapter_path_for(model_name)
    return path.exists() and any(path.iterdir())


def download(model_name: str, hf_repo: str, force: bool = False) -> Path:
    """
    Download the LoRA adapter from HuggingFace Hub.

    Returns the local adapter path.
    Raises ImportError if huggingface_hub is not installed.
    Raises ValueError for unknown model names.
    """
    if not _hf_available:
        raise ImportError(
            "huggingface_hub is required for model downloads:\n"
            "  pip install huggingface_hub"
        )

    dest = adapter_path_for(model_name)

    if dest.exists() and not force:
        log.info("Adapter %s already downloaded at %s", model_name, dest)
        return dest

    dest.mkdir(parents=True, exist_ok=True)
    log.info("Downloading %s from %s …", model_name, hf_repo)

    _hf_snapshot(
        repo_id=hf_repo,
        local_dir=str(dest),
        local_dir_use_symlinks=False,
    )
    log.info("Download complete: %s", dest)
    return dest


def remove(model_name: str) -> bool:
    """Delete a downloaded adapter. Returns True if something was deleted."""
    path = adapter_path_for(model_name)
    if path.exists():
        shutil.rmtree(path)
        log.info("Removed adapter: %s", path)
        return True
    return False


def disk_usage_mb(model_name: str) -> float:
    """Return disk usage in MB for a downloaded adapter (0 if not downloaded)."""
    path = adapter_path_for(model_name)
    if not path.exists():
        return 0.0
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / (1024 * 1024), 1)
