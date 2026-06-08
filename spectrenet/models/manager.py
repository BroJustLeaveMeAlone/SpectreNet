"""
snet model — command-line model manager.

Commands:
  snet model list                  Show all available SpectreBot variants
  snet model download <name>       Download adapter from HuggingFace Hub
  snet model status                Show downloaded models + disk usage
  snet model remove <name>         Delete a downloaded adapter
"""
from __future__ import annotations

from spectrenet.models.registry import SPECTRENET_MODELS, list_models
from spectrenet.models.downloader import (
    is_downloaded, download, remove, disk_usage_mb, MODELS_DIR
)

_COL = 22  # column width for model name


def cmd_list() -> None:
    print(f"\n{'SpectreBot Models':}")
    print("─" * 72)
    print(f"  {'Name':<{_COL}} {'Params':<8} {'Min VRAM':<10} {'Adapter':<10} Description")
    print("─" * 72)
    for m in list_models():
        params = m["base_model"].split("/")[-1][:12]
        downloaded = "✓ local" if is_downloaded(m["name"]) else "─ cloud"
        print(
            f"  {m['name']:<{_COL}} "
            f"{params:<8} "
            f"{m['min_vram_gb']} GB{'':<6} "
            f"{downloaded:<10} "
            f"{m['description'][:48]}"
        )
    print()
    print(f"  Adapters stored in: {MODELS_DIR}")
    print()
    print("  snet model download <name>   Download an adapter")
    print("  snet model status            Show disk usage")
    print()


def cmd_status() -> None:
    print(f"\n{'SpectreBot — Local Model Status':}")
    print("─" * 52)
    any_downloaded = False
    for m in list_models():
        name = m["name"]
        if is_downloaded(name):
            mb = disk_usage_mb(name)
            print(f"  ✓  {name:<{_COL}}  {mb:>6.0f} MB  {MODELS_DIR / name}")
            any_downloaded = True
    if not any_downloaded:
        print("  No models downloaded yet.")
        print(f"  Run: snet model download spectrenet-7b")
    print()


def cmd_download(name: str, force: bool = False) -> None:
    meta = SPECTRENET_MODELS.get(name)
    if meta is None:
        available = ", ".join(SPECTRENET_MODELS)
        print(f"Unknown model '{name}'. Available: {available}")
        return

    if is_downloaded(name) and not force:
        print(f"'{name}' is already downloaded at {MODELS_DIR / name}")
        print("Use --force to re-download.")
        return

    print(f"Downloading {name} from {meta['hf_repo']} …")
    print(f"  Adapter size: ~{meta['adapter_size_mb']} MB")
    print(f"  Base model will be downloaded automatically on first use (~{meta['base_size_gb']} GB)")
    print()
    try:
        path = download(name, meta["hf_repo"], force=force)
        print(f"✓ Downloaded to {path}")
    except ImportError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Download failed: {e}")
        print("The model may not be published yet — check https://huggingface.co/SpectreNet")


def cmd_remove(name: str) -> None:
    if name not in SPECTRENET_MODELS:
        print(f"Unknown model '{name}'.")
        return
    if remove(name):
        print(f"✓ Removed {name}")
    else:
        print(f"'{name}' is not downloaded.")
