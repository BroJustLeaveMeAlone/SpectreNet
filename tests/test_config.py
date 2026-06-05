import textwrap
from spectrenet.config import load_config, Config

def test_load_config_uses_defaults_when_file_missing(tmp_path):
    cfg = load_config(tmp_path / "nope.yaml")
    assert isinstance(cfg, Config)
    assert cfg.model_backend == "ollama"
    assert cfg.storage_backend == "sqlite"
    assert cfg.server_port == 7777

def test_load_config_overrides_from_yaml(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent("""
        model_backend: openai
        storage_backend: postgres
        server_port: 8888
        operator_name: alice
    """))
    cfg = load_config(p)
    assert cfg.model_backend == "openai"
    assert cfg.storage_backend == "postgres"
    assert cfg.server_port == 8888
    assert cfg.operator_name == "alice"
