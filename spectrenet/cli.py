import argparse
import sys
from pathlib import Path
import yaml
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
            "  spectrenet                  Launch interactive TUI\n"
            "  spectrenet tools            Check which external tools are installed\n"
            "  spectrenet tools install    Print install commands for missing tools\n"
            "  spectrenet server           Start the team collaboration server\n"
            "  spectrenet model list       List available SpectreBot adapters\n"
            "  spectrenet train export     Export session logs as fine-tuning data\n"
            "  spectrenet train eval       Compare two model backends on pentest prompts\n"
            "  spectrenet config set-key   Save an API key to config.yaml\n"
            "\n"
            "Use --model to skip the startup selector for scripting or quick re-launch."
        ),
    )
    parser.add_argument("--config",   default="config.yaml", metavar="FILE")
    parser.add_argument("--operator", default=None, metavar="NAME",
                        help="Operator name (overrides config operator_name)")
    parser.add_argument(
        "--model",
        choices=["ollama", "openai", "anthropic", "groq", "openrouter", "spectre", "local", "none"],
        default=None,
        metavar="BACKEND",
        help="Skip startup mode selector (ollama|openai|anthropic|groq|openrouter|spectre|local|none)",
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

    tls = sub.add_parser("tools", help="Check tool availability and get install commands")
    tls_sub = tls.add_subparsers(dest="tools_cmd")
    tls_sub.add_parser("status",  help="Show all tools and their availability (default)")
    tls_sub.add_parser("install", help="Print install commands for every missing tool")

    srv = sub.add_parser("server", help="Start the team collaboration server")
    srv.add_argument("--host", default="0.0.0.0")
    srv.add_argument("--port", type=int, default=8888)

    mdl = sub.add_parser("model", help="Manage SpectreBot model adapters")
    mdl_sub = mdl.add_subparsers(dest="model_cmd")
    mdl_sub.add_parser("list",   help="List available SpectreBot variants")
    mdl_sub.add_parser("status", help="Show downloaded models and disk usage")
    dl = mdl_sub.add_parser("download", help="Download a SpectreBot adapter from HuggingFace")
    dl.add_argument("name", help="Model name (e.g. spectrenet-7b)")
    dl.add_argument("--force", action="store_true", help="Re-download even if already present")
    rm = mdl_sub.add_parser("remove", help="Delete a downloaded adapter")
    rm.add_argument("name")

    trn = sub.add_parser("train", help="SpectreBot training utilities")
    trn_sub = trn.add_subparsers(dest="train_cmd")
    exp = trn_sub.add_parser("export", help="Export session logs as fine-tuning data")
    exp.add_argument("--output", default="training_data", metavar="PATH",
                     help="Output file prefix (creates .train.jsonl + .val.jsonl)")
    exp.add_argument("--db", default=None, metavar="PATH",
                     help="Path to spectrenet.db (default: current dir)")
    ev = trn_sub.add_parser("eval", help="Compare two model backends on pentest prompts")
    ev.add_argument("--baseline",  default="ollama:llama3.1:8b", metavar="SPEC",
                    help="Baseline backend spec  (default: ollama:llama3.1:8b)")
    ev.add_argument("--candidate", default=None, metavar="SPEC",
                    help="Candidate backend spec (default: same as baseline for dry-run). "
                         "Format: ollama:<model> | local:<adapter>:<base> | "
                         "groq:<model>:<key> | openrouter:<model>:<key>")
    ev.add_argument("--baseline-label",  default="Baseline",   metavar="LABEL")
    ev.add_argument("--candidate-label", default="SpectreBot", metavar="LABEL")

    cfg_cmd = sub.add_parser("config", help="Configure SpectreNet settings")
    cfg_sub = cfg_cmd.add_subparsers(dest="config_cmd")
    sk = cfg_sub.add_parser("set-key", help="Set an API key in config.yaml")
    sk.add_argument("provider", choices=["openai", "anthropic", "groq", "openrouter", "together"],
                    help="Provider name")
    sk.add_argument("key", help="API key value")
    cfg_sub.add_parser("show-providers", help="Show configured providers and their status")

    return parser


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    # ── snet tools ─────────────────────────────────────────────────────────────
    if args.subcommand == "tools":
        from spectrenet.tools_installer import cmd_tools_status, cmd_tools_install
        if getattr(args, "tools_cmd", None) == "install":
            cmd_tools_install()
        else:
            cmd_tools_status()
        return

    # ── Team server ────────────────────────────────────────────────────────────
    if args.subcommand == "server":
        try:
            from spectrenet.server.app import serve
            print(f"Starting SpectreNet team server on {args.host}:{args.port}")
            serve(host=args.host, port=args.port)
        except ImportError:
            print("fastapi and uvicorn are required: pip install fastapi uvicorn")
            sys.exit(1)
        return

    # ── snet model ─────────────────────────────────────────────────────────────
    if args.subcommand == "model":
        from spectrenet.models.manager import cmd_list, cmd_status, cmd_download, cmd_remove
        cmd = getattr(args, "model_cmd", None) or "list"
        if cmd == "list":
            cmd_list()
        elif cmd == "status":
            cmd_status()
        elif cmd == "download":
            cmd_download(args.name, force=getattr(args, "force", False))
        elif cmd == "remove":
            cmd_remove(args.name)
        else:
            print("Usage: snet model [list|status|download|remove]")
        return

    # ── snet train ─────────────────────────────────────────────────────────────
    if args.subcommand == "train":
        train_cmd = getattr(args, "train_cmd", None)
        if train_cmd == "export":
            from spectrenet.training.dataset_builder import DatasetBuilder
            db_paths = [Path(args.db)] if args.db else []
            builder  = DatasetBuilder()
            output   = Path(args.output)
            n_train, n_val = builder.build(output, db_paths=db_paths)
            print(f"✓ Exported {n_train} training + {n_val} validation examples")
            print(f"  Train: {output.with_suffix('.train.jsonl')}")
            print(f"  Val:   {output.with_suffix('.val.jsonl')}")
            print()
            print("Next steps:")
            print("  1. Upload the .train.jsonl file to Kaggle as a Dataset")
            print("  2. Open notebooks/spectrenet_finetune.ipynb on Kaggle")
            print("  3. Run all cells to fine-tune SpectreBot")
        elif train_cmd == "eval":
            from spectrenet.training.eval import run_eval, _build_backend
            baseline  = _build_backend(args.baseline)
            candidate = _build_backend(args.candidate) if args.candidate else baseline
            run_eval(
                baseline_fn     = lambda s, u: baseline.complete(s, u),
                candidate_fn    = lambda s, u: candidate.complete(s, u),
                baseline_label  = args.baseline_label,
                candidate_label = args.candidate_label,
            )
        else:
            print("Usage: snet train <export|eval> [options]")
            print("  export  Export session logs as fine-tuning data")
            print("  eval    Compare two model backends on pentest prompts")
        return

    # ── snet config ────────────────────────────────────────────────────────────
    if args.subcommand == "config":
        config_cmd = getattr(args, "config_cmd", None)
        if config_cmd == "set-key":
            _set_api_key(Path(args.config), args.provider, args.key)
        elif config_cmd == "show-providers":
            _show_providers(Path(args.config))
        else:
            print("Usage: snet config [set-key|show-providers]")
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
        elif args.model == "anthropic":
            try:
                from spectrenet.model.anthropic_backend import AnthropicBackend
                model = AnthropicBackend.from_config(cfg)
            except Exception as e:
                log.warning("Anthropic init failed: %s", e)
        elif args.model == "groq":
            try:
                from spectrenet.model.groq_backend import GroqBackend
                model = GroqBackend.from_config(cfg)
            except Exception as e:
                log.warning("Groq init failed: %s", e)
        elif args.model == "openrouter":
            try:
                from spectrenet.model.openrouter_backend import OpenRouterBackend
                model = OpenRouterBackend.from_config(cfg)
            except Exception as e:
                log.warning("OpenRouter init failed: %s", e)
        elif args.model == "spectre":
            try:
                from spectrenet.model.spectre_backend import SpectreBackend
                model = SpectreBackend.from_config(cfg)
            except Exception as e:
                log.warning("SpectreBot/Together init failed: %s", e)
        elif args.model == "local":
            try:
                from spectrenet.model.local_backend import LocalSpectreBackend
                model = LocalSpectreBackend.from_config(cfg)
            except Exception as e:
                log.warning("Local SpectreBot init failed: %s", e)

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


_PROVIDER_KEY_MAP = {
    "openai":     "openai_api_key",
    "anthropic":  "anthropic_api_key",
    "groq":       "groq_api_key",
    "openrouter": "openrouter_api_key",
    "together":   "together_api_key",
}


def _set_api_key(config_path: Path, provider: str, key: str) -> None:
    data: dict = {}
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text()) or {}
    field = _PROVIDER_KEY_MAP[provider]
    data[field] = key
    config_path.write_text(yaml.dump(data, default_flow_style=False))
    masked = key[:4] + "…" + key[-4:] if len(key) > 8 else "****"
    print(f"✓ {provider} key saved to {config_path} ({masked})")


def _show_providers(config_path: Path) -> None:
    cfg = load_config(config_path)
    print("\nConfigured Providers")
    print("─" * 52)
    rows = [
        ("Ollama",      "ollama_url",          cfg.ollama_url),
        ("OpenAI",      "openai_api_key",       cfg.openai_api_key),
        ("Anthropic",   "anthropic_api_key",    cfg.anthropic_api_key),
        ("Groq",        "groq_api_key",         cfg.groq_api_key),
        ("OpenRouter",  "openrouter_api_key",   cfg.openrouter_api_key),
        ("Together/SpectreBot", "together_api_key", cfg.together_api_key),
        ("Local SpectreBot", "local_model_name", cfg.local_model_name),
    ]
    for label, field, val in rows:
        if val:
            masked = val[:4] + "…" + val[-4:] if len(val) > 8 else val
            status = f"✓ configured ({masked})"
        else:
            status = "─ not configured"
        print(f"  {label:<24} {status}")
    print()
    print("  Set a key: snet config set-key <provider> <key>")
    print("  Providers: openai  anthropic  groq  openrouter  together")
    print()


if __name__ == "__main__":
    main()
