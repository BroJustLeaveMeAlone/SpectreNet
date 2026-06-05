# SpectreNet Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the SpectreNet foundation — a themed Terminal UI that loads config, autodiscovers tool wrappers, runs nmap/masscan recon with normalized output, persists sessions to SQLite, queries a basic CVE knowledge base, and talks to an Ollama model backend through a swappable interface.

**Architecture:** Python 3.11+ monorepo. A small core (config, logging, theme) underpins five subsystems: a convention-based wrapper registry, a recon engine, a swappable model interface, SQLite session storage, and a SQLite CVE knowledge base. A Textual/Rich TUI ties them together. Every subsystem is independently testable; the TUI is the only integration surface.

**Tech Stack:** Python 3.11+, Textual + Rich (TUI), PyYAML (config), pytest (tests), SQLite (stdlib `sqlite3`), httpx (Ollama HTTP), nmap/masscan (external binaries, mocked in tests).

---

## File Structure

```
spectrenet/
  pyproject.toml                      # package metadata, deps, pytest config
  README.md
  spectrenet/
    __init__.py                       # version
    config.py                         # YAML config load + defaults dataclass
    logging_setup.py                  # structured logging to file + console
    theme.py                          # SpectreNet colors (dark navy + cyan)
    cli.py                            # entry point: spectrenet / snet
    wrappers/
      __init__.py
      base.py                         # ToolWrapper abstract interface
      registry.py                     # convention-based autodiscovery
      builtin/
        __init__.py
        nmap.py                       # nmap wrapper -> normalized hosts schema
        masscan.py                    # masscan wrapper -> normalized hosts schema
      custom/
        __init__.py                   # empty; third-party wrappers dropped here
    engines/
      __init__.py
      recon.py                        # ReconEngine: orchestrates recon wrappers
    model/
      __init__.py
      interface.py                    # ModelInterface ABC: complete()
      ollama_backend.py               # OllamaBackend implementation
    storage/
      __init__.py
      schema.sql                      # session/action DDL
      session.py                      # SessionStore: SQLite persistence
    knowledge/
      __init__.py
      schema.sql                      # cve + service_exploit_map DDL
      cve_db.py                       # CVEKnowledgeBase: query CVEs by service
    tui/
      __init__.py
      app.py                          # SpectreNetApp (Textual)
      command_parser.py               # parse "verb arg --flag" into Command
  tests/
    conftest.py
    test_config.py
    test_wrapper_registry.py
    test_nmap_wrapper.py
    test_masscan_wrapper.py
    test_recon_engine.py
    test_model_interface.py
    test_ollama_backend.py
    test_session_store.py
    test_cve_db.py
    test_command_parser.py
    fixtures/
      nmap_sample.xml
      masscan_sample.json
```

**Responsibility boundaries:**
- `core` (config/logging/theme) knows nothing about subsystems.
- `wrappers` depend only on `base.py`; the registry never imports a specific wrapper.
- `engines/recon.py` depends on the registry, not on individual wrappers.
- `model`, `storage`, `knowledge` are independent silos.
- `tui` is the only place that wires everything together.

---

## Task 1: Project skeleton + git init

**Files:**
- Create: `pyproject.toml`
- Create: `spectrenet/__init__.py`
- Create: `README.md`
- Create: `.gitignore`

- [ ] **Step 1: Initialize git and create package metadata**

Run:
```bash
git init
```

Create `pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "spectrenet"
version = "0.1.0"
description = "SpectreNet — AI-assisted offensive security framework. Always one step ahead."
requires-python = ">=3.11"
dependencies = [
    "textual>=0.50",
    "rich>=13.7",
    "pyyaml>=6.0",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=4.1"]

[project.scripts]
spectrenet = "spectrenet.cli:main"
snet = "spectrenet.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v"

[tool.setuptools.packages.find]
include = ["spectrenet*"]
```

Create `spectrenet/__init__.py`:
```python
__version__ = "0.1.0"
APP_NAME = "SpectreNet"
TAGLINE = "Always one step ahead"
```

Create `.gitignore`:
```
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
.venv/
*.db
*.sqlite
.coverage
```

Create `README.md`:
```markdown
# SpectreNet

> Always one step ahead

AI-assisted offensive security framework. For authorized penetration testing and red team operations only.

See `docs/superpowers/specs/` for architecture and `docs/superpowers/plans/` for implementation plans.
```

- [ ] **Step 2: Create empty package directories**

Run:
```bash
mkdir -p spectrenet/wrappers/builtin spectrenet/wrappers/custom spectrenet/engines spectrenet/model spectrenet/storage spectrenet/knowledge spectrenet/tui tests/fixtures
```

Create empty `__init__.py` in each: `spectrenet/wrappers/__init__.py`, `spectrenet/wrappers/builtin/__init__.py`, `spectrenet/wrappers/custom/__init__.py`, `spectrenet/engines/__init__.py`, `spectrenet/model/__init__.py`, `spectrenet/storage/__init__.py`, `spectrenet/knowledge/__init__.py`, `spectrenet/tui/__init__.py`.

- [ ] **Step 3: Install in editable mode and verify**

Run:
```bash
pip install -e ".[dev]"
python -c "import spectrenet; print(spectrenet.APP_NAME, spectrenet.__version__)"
```
Expected: `SpectreNet 0.1.0`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: scaffold SpectreNet Phase 1 project skeleton"
```

---

## Task 2: Config system

**Files:**
- Create: `spectrenet/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectrenet.config'`

- [ ] **Step 3: Write minimal implementation**

```python
# spectrenet/config.py
from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass
class Config:
    model_backend: str = "ollama"
    model_name: str = "llama3.1:70b"
    ollama_url: str = "http://localhost:11434"
    storage_backend: str = "sqlite"
    db_path: str = "spectrenet.db"
    server_port: int = 7777
    operator_name: str = "operator"
    log_level: str = "INFO"

def load_config(path: Path) -> Config:
    path = Path(path)
    if not path.exists():
        return Config()
    data = yaml.safe_load(path.read_text()) or {}
    known = {f for f in Config.__dataclass_fields__}
    filtered = {k: v for k, v in data.items() if k in known}
    return Config(**filtered)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add spectrenet/config.py tests/test_config.py
git commit -m "feat: add YAML config system with defaults"
```

---

## Task 3: Logging + theme

**Files:**
- Create: `spectrenet/logging_setup.py`
- Create: `spectrenet/theme.py`

- [ ] **Step 1: Write the theme module (no test — constants only)**

```python
# spectrenet/theme.py
"""SpectreNet visual identity: dark navy base, cyan accent. Modern, not retro."""

# Core palette
NAVY_DEEP = "#050d1a"     # primary background
NAVY = "#0a1628"          # panel background
NAVY_LIGHT = "#16263f"    # borders / dividers
CYAN = "#00c8ff"          # primary accent
CYAN_DIM = "#0891b2"      # secondary accent
WHITE = "#e8f1f8"         # primary text
GREY = "#7a8ba0"          # muted text

# Semantic
RISK_HIGH = "#ff4d6d"
RISK_MED = "#ffb84d"
RISK_LOW = "#4dffa3"
SUCCESS = "#4dffa3"
WARNING = "#ffb84d"
ERROR = "#ff4d6d"

# Rich style strings
STYLE_HEADER = f"bold {CYAN} on {NAVY_DEEP}"
STYLE_PROMPT = f"bold {CYAN}"
STYLE_MUTED = GREY
STYLE_WARNING = f"bold {WARNING}"

BANNER = r"""
   ____                 _           _   _      _
  / ___| _ __  ___  ___| |_ _ __ __| \ | | ___| |_
  \___ \| '_ \/ _ \/ __| __| '__/ _ \ \| |/ _ \ __|
   ___) | |_) |  __/ (__| |_| | |  __/ |\  |  __/ |_
  |____/| .__/ \___|\___|\__|_|  \___|_| \_|\___|\__|
        |_|        Always one step ahead
"""
```

- [ ] **Step 2: Write the logging module (no unit test — side-effect module, verified via smoke run)**

```python
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
```

- [ ] **Step 3: Smoke-verify both modules import and run**

Run:
```bash
python -c "from spectrenet.theme import BANNER, CYAN; from spectrenet.logging_setup import setup_logging; lg=setup_logging('DEBUG'); lg.info('boot ok'); print('theme cyan', CYAN)"
```
Expected: a rich-formatted `boot ok` log line and `theme cyan #00c8ff`. A `spectrenet.log` file is created.

- [ ] **Step 4: Commit**

```bash
git add spectrenet/theme.py spectrenet/logging_setup.py
git commit -m "feat: add SpectreNet theme palette and structured logging"
```

---

## Task 4: ToolWrapper base interface

**Files:**
- Create: `spectrenet/wrappers/base.py`

- [ ] **Step 1: Write the base interface (contract verified by wrapper tests in Tasks 6-7)**

```python
# spectrenet/wrappers/base.py
from abc import ABC, abstractmethod

class ToolWrapper(ABC):
    """Base contract every tool wrapper must implement.

    Subclasses are autodiscovered from wrappers/builtin and wrappers/custom.
    """

    #: Unique tool identifier, e.g. "nmap". Must be set by subclass.
    tool_name: str = ""

    #: Name of the external binary required on PATH. Defaults to tool_name.
    binary: str = ""

    @property
    @abstractmethod
    def schema(self) -> dict:
        """Return a dict describing the normalized output structure."""

    @abstractmethod
    def run(self, **kwargs) -> dict:
        """Execute the tool and return output normalized to `schema`."""

    def is_available(self) -> bool:
        """True if the tool's binary is present on PATH."""
        import shutil
        return shutil.which(self.binary or self.tool_name) is not None
```

- [ ] **Step 2: Verify it imports and is abstract**

Run:
```bash
python -c "from spectrenet.wrappers.base import ToolWrapper; 
try:
    ToolWrapper()
    print('ERROR: should be abstract')
except TypeError:
    print('abstract ok')"
```
Expected: `abstract ok`

- [ ] **Step 3: Commit**

```bash
git add spectrenet/wrappers/base.py
git commit -m "feat: add ToolWrapper abstract base interface"
```

---

## Task 5: Wrapper registry (convention-based autodiscovery)

**Files:**
- Create: `spectrenet/wrappers/registry.py`
- Test: `tests/test_wrapper_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wrapper_registry.py
from spectrenet.wrappers.registry import WrapperRegistry
from spectrenet.wrappers.base import ToolWrapper

def test_registry_discovers_a_custom_wrapper(tmp_path):
    # Drop a fake wrapper file into a temp custom dir
    custom = tmp_path / "custom"
    custom.mkdir()
    (custom / "__init__.py").write_text("")
    (custom / "fake.py").write_text(
        "from spectrenet.wrappers.base import ToolWrapper\n"
        "class FakeWrapper(ToolWrapper):\n"
        "    tool_name = 'fake'\n"
        "    @property\n"
        "    def schema(self): return {'ok': bool}\n"
        "    def run(self, **kw): return {'ok': True}\n"
    )
    reg = WrapperRegistry(extra_dirs=[custom])
    reg.discover()
    assert "fake" in reg.names()
    w = reg.get("fake")
    assert w.run() == {"ok": True}

def test_registry_skips_non_wrapper_classes(tmp_path):
    custom = tmp_path / "custom"
    custom.mkdir()
    (custom / "__init__.py").write_text("")
    (custom / "junk.py").write_text("class NotAWrapper:\n    pass\n")
    reg = WrapperRegistry(extra_dirs=[custom])
    reg.discover()
    assert reg.names() == [] or "junk" not in reg.names()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wrapper_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectrenet.wrappers.registry'`

- [ ] **Step 3: Write minimal implementation**

```python
# spectrenet/wrappers/registry.py
import importlib.util
import inspect
import logging
from pathlib import Path
from spectrenet.wrappers.base import ToolWrapper

log = logging.getLogger("spectrenet")

class WrapperRegistry:
    """Discovers ToolWrapper subclasses from builtin + custom directories."""

    def __init__(self, extra_dirs=None):
        here = Path(__file__).parent
        self._dirs = [here / "builtin", here / "custom"]
        if extra_dirs:
            self._dirs.extend(Path(d) for d in extra_dirs)
        self._wrappers: dict[str, ToolWrapper] = {}

    def discover(self) -> None:
        for d in self._dirs:
            if not d.exists():
                continue
            for py in sorted(d.glob("*.py")):
                if py.name == "__init__.py":
                    continue
                self._load_file(py)

    def _load_file(self, py: Path) -> None:
        spec = importlib.util.spec_from_file_location(f"_snwrap_{py.stem}", py)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:  # a broken wrapper must not crash startup
            log.warning("Failed to load wrapper %s: %s", py.name, e)
            return
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, ToolWrapper) and obj is not ToolWrapper:
                if not getattr(obj, "tool_name", ""):
                    continue
                instance = obj()
                self._wrappers[instance.tool_name] = instance
                status = "available" if instance.is_available() else "unavailable"
                log.info("Registered wrapper '%s' (%s)", instance.tool_name, status)

    def names(self) -> list[str]:
        return sorted(self._wrappers)

    def get(self, name: str) -> ToolWrapper:
        return self._wrappers[name]

    def available(self) -> list[str]:
        return sorted(n for n, w in self._wrappers.items() if w.is_available())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_wrapper_registry.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add spectrenet/wrappers/registry.py tests/test_wrapper_registry.py
git commit -m "feat: add convention-based wrapper autodiscovery registry"
```

---

## Task 6: nmap wrapper

**Files:**
- Create: `spectrenet/wrappers/builtin/nmap.py`
- Create: `tests/fixtures/nmap_sample.xml`
- Test: `tests/test_nmap_wrapper.py`

- [ ] **Step 1: Create the fixture**

```xml
<!-- tests/fixtures/nmap_sample.xml -->
<?xml version="1.0"?>
<nmaprun>
  <host>
    <address addr="192.168.1.45" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="445">
        <state state="open"/>
        <service name="microsoft-ds" version="Samba 4.6"/>
      </port>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" version="OpenSSH 7.4"/>
      </port>
    </ports>
  </host>
</nmaprun>
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_nmap_wrapper.py
from pathlib import Path
from spectrenet.wrappers.builtin.nmap import NmapWrapper

FIX = Path(__file__).parent / "fixtures" / "nmap_sample.xml"

def test_nmap_parses_xml_into_normalized_schema():
    w = NmapWrapper()
    result = w.parse(FIX.read_text())
    assert result == {
        "hosts": [
            {
                "ip": "192.168.1.45",
                "ports": [
                    {"port": 445, "service": "microsoft-ds", "version": "Samba 4.6"},
                    {"port": 22, "service": "ssh", "version": "OpenSSH 7.4"},
                ],
            }
        ]
    }

def test_nmap_tool_name_and_schema():
    w = NmapWrapper()
    assert w.tool_name == "nmap"
    assert "hosts" in w.schema
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_nmap_wrapper.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# spectrenet/wrappers/builtin/nmap.py
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from spectrenet.wrappers.base import ToolWrapper

class NmapWrapper(ToolWrapper):
    tool_name = "nmap"
    binary = "nmap"

    @property
    def schema(self) -> dict:
        return {"hosts": [{"ip": str, "ports": [{"port": int, "service": str, "version": str}]}]}

    def parse(self, xml_text: str) -> dict:
        root = ET.fromstring(xml_text)
        hosts = []
        for host in root.findall("host"):
            addr_el = host.find("address")
            ip = addr_el.get("addr") if addr_el is not None else ""
            ports = []
            for port in host.findall("./ports/port"):
                state = port.find("state")
                if state is None or state.get("state") != "open":
                    continue
                svc = port.find("service")
                ports.append({
                    "port": int(port.get("portid")),
                    "service": svc.get("name") if svc is not None else "",
                    "version": svc.get("version", "") if svc is not None else "",
                })
            hosts.append({"ip": ip, "ports": ports})
        return {"hosts": hosts}

    def run(self, target: str, flags: str = "-sV", **kwargs) -> dict:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "scan.xml"
            cmd = ["nmap", *flags.split(), "-oX", str(out), target]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return self.parse(out.read_text())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_nmap_wrapper.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add spectrenet/wrappers/builtin/nmap.py tests/fixtures/nmap_sample.xml tests/test_nmap_wrapper.py
git commit -m "feat: add nmap wrapper with XML->JSON normalization"
```

---

## Task 7: masscan wrapper

**Files:**
- Create: `spectrenet/wrappers/builtin/masscan.py`
- Create: `tests/fixtures/masscan_sample.json`
- Test: `tests/test_masscan_wrapper.py`

- [ ] **Step 1: Create the fixture**

```json
[
  {"ip": "192.168.1.45", "ports": [{"port": 445, "proto": "tcp", "status": "open"}]},
  {"ip": "192.168.1.50", "ports": [{"port": 80, "proto": "tcp", "status": "open"}]}
]
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_masscan_wrapper.py
from pathlib import Path
from spectrenet.wrappers.builtin.masscan import MasscanWrapper

FIX = Path(__file__).parent / "fixtures" / "masscan_sample.json"

def test_masscan_parses_json_into_normalized_schema():
    w = MasscanWrapper()
    result = w.parse(FIX.read_text())
    assert result == {
        "hosts": [
            {"ip": "192.168.1.45", "ports": [{"port": 445, "service": "", "version": ""}]},
            {"ip": "192.168.1.50", "ports": [{"port": 80, "service": "", "version": ""}]},
        ]
    }

def test_masscan_tool_name():
    assert MasscanWrapper().tool_name == "masscan"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_masscan_wrapper.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# spectrenet/wrappers/builtin/masscan.py
import json
import subprocess
import tempfile
from pathlib import Path
from spectrenet.wrappers.base import ToolWrapper

class MasscanWrapper(ToolWrapper):
    tool_name = "masscan"
    binary = "masscan"

    @property
    def schema(self) -> dict:
        return {"hosts": [{"ip": str, "ports": [{"port": int, "service": str, "version": str}]}]}

    def parse(self, json_text: str) -> dict:
        raw = json.loads(json_text)
        hosts = []
        for entry in raw:
            ports = [
                {"port": int(p["port"]), "service": "", "version": ""}
                for p in entry.get("ports", [])
                if p.get("status", "open") == "open"
            ]
            hosts.append({"ip": entry["ip"], "ports": ports})
        return {"hosts": hosts}

    def run(self, target: str, ports: str = "1-1000", rate: int = 1000, **kwargs) -> dict:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "scan.json"
            cmd = ["masscan", target, "-p", ports, "--rate", str(rate), "-oJ", str(out)]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return self.parse(out.read_text())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_masscan_wrapper.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add spectrenet/wrappers/builtin/masscan.py tests/fixtures/masscan_sample.json tests/test_masscan_wrapper.py
git commit -m "feat: add masscan wrapper with JSON->normalized schema"
```

---

## Task 8: Recon engine

**Files:**
- Create: `spectrenet/engines/recon.py`
- Test: `tests/test_recon_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recon_engine.py
from spectrenet.engines.recon import ReconEngine
from spectrenet.wrappers.base import ToolWrapper

class StubNmap(ToolWrapper):
    tool_name = "nmap"
    @property
    def schema(self): return {"hosts": []}
    def run(self, **kw):
        return {"hosts": [{"ip": "10.0.0.1", "ports": [{"port": 22, "service": "ssh", "version": "8.0"}]}]}
    def is_available(self): return True

class FakeRegistry:
    def __init__(self): self._w = {"nmap": StubNmap()}
    def get(self, n): return self._w[n]
    def available(self): return ["nmap"]

def test_recon_engine_runs_named_tool_and_returns_hosts():
    eng = ReconEngine(FakeRegistry())
    result = eng.scan(tool="nmap", target="10.0.0.1")
    assert result["hosts"][0]["ip"] == "10.0.0.1"

def test_recon_engine_rejects_unavailable_tool():
    eng = ReconEngine(FakeRegistry())
    try:
        eng.scan(tool="zmap", target="10.0.0.1")
        assert False, "should have raised"
    except ValueError as e:
        assert "zmap" in str(e)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_recon_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# spectrenet/engines/recon.py
import logging

log = logging.getLogger("spectrenet")

class ReconEngine:
    """Orchestrates recon tool wrappers via the registry."""

    def __init__(self, registry):
        self.registry = registry

    def scan(self, tool: str, target: str, **kwargs) -> dict:
        if tool not in self.registry.available():
            raise ValueError(f"Recon tool '{tool}' is not available")
        log.info("Recon scan: tool=%s target=%s", tool, target)
        wrapper = self.registry.get(tool)
        return wrapper.run(target=target, **kwargs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_recon_engine.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add spectrenet/engines/recon.py tests/test_recon_engine.py
git commit -m "feat: add recon engine orchestrating wrappers via registry"
```

---

## Task 9: Model interface (abstraction)

**Files:**
- Create: `spectrenet/model/interface.py`
- Test: `tests/test_model_interface.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_interface.py
from spectrenet.model.interface import ModelInterface

class EchoModel(ModelInterface):
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return f"[{system_prompt}] {user_prompt}"

def test_model_interface_single_method_contract():
    m = EchoModel()
    assert m.complete("sys", "hello") == "[sys] hello"

def test_model_interface_is_abstract():
    try:
        ModelInterface()
        assert False, "should be abstract"
    except TypeError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_model_interface.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# spectrenet/model/interface.py
from abc import ABC, abstractmethod

class ModelInterface(ABC):
    """Swappable model backend. All AI core components call complete()."""

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return the model's completion for the given prompts."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_model_interface.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add spectrenet/model/interface.py tests/test_model_interface.py
git commit -m "feat: add swappable ModelInterface abstraction"
```

---

## Task 10: Ollama backend

**Files:**
- Create: `spectrenet/model/ollama_backend.py`
- Test: `tests/test_ollama_backend.py`

- [ ] **Step 1: Write the failing test (HTTP mocked, no real Ollama needed)**

```python
# tests/test_ollama_backend.py
from spectrenet.model.ollama_backend import OllamaBackend

class FakeResponse:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p

class FakeClient:
    def __init__(self, payload): self._p = payload; self.last = None
    def post(self, url, json, timeout):
        self.last = {"url": url, "json": json}
        return FakeResponse(self._p)

def test_ollama_complete_returns_message_content():
    fake = FakeClient({"message": {"content": "pong"}})
    be = OllamaBackend(model="llama3.1:70b", url="http://x:11434", client=fake)
    out = be.complete("you are a scanner", "ping")
    assert out == "pong"
    # verify it sent both prompts as chat messages
    msgs = fake.last["json"]["messages"]
    assert msgs[0]["role"] == "system" and msgs[0]["content"] == "you are a scanner"
    assert msgs[1]["role"] == "user" and msgs[1]["content"] == "ping"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ollama_backend.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# spectrenet/model/ollama_backend.py
import httpx
from spectrenet.model.interface import ModelInterface

class OllamaBackend(ModelInterface):
    def __init__(self, model: str, url: str = "http://localhost:11434", client=None, timeout: float = 120.0):
        self.model = model
        self.url = url.rstrip("/")
        self.timeout = timeout
        self._client = client or httpx.Client()

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        resp = self._client.post(
            f"{self.url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ollama_backend.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add spectrenet/model/ollama_backend.py tests/test_ollama_backend.py
git commit -m "feat: add Ollama model backend (dependency-injected HTTP client)"
```

---

## Task 11: SQLite session storage

**Files:**
- Create: `spectrenet/storage/schema.sql`
- Create: `spectrenet/storage/session.py`
- Test: `tests/test_session_store.py`

- [ ] **Step 1: Create the schema**

```sql
-- spectrenet/storage/schema.sql
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    operator TEXT NOT NULL,
    started_at TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'classic'
);

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    ts TEXT NOT NULL,
    operator TEXT NOT NULL,
    tool TEXT NOT NULL,
    params TEXT,
    output_hash TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_session_store.py
from spectrenet.storage.session import SessionStore

def test_create_session_and_log_action(tmp_path):
    store = SessionStore(tmp_path / "s.db")
    sid = store.create_session(name="engagement-1", operator="alice", mode="classic")
    assert sid == 1
    store.log_action(sid, operator="alice", tool="nmap",
                     params={"target": "10.0.0.1"}, output_hash="abc123")
    actions = store.actions_for(sid)
    assert len(actions) == 1
    assert actions[0]["tool"] == "nmap"
    assert actions[0]["operator"] == "alice"

def test_actions_isolated_per_session(tmp_path):
    store = SessionStore(tmp_path / "s.db")
    s1 = store.create_session("a", "alice")
    s2 = store.create_session("b", "bob")
    store.log_action(s1, "alice", "nmap", {}, "h1")
    assert store.actions_for(s2) == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_session_store.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# spectrenet/storage/session.py
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = Path(__file__).parent / "schema.sql"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class SessionStore:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA.read_text())
        self.conn.commit()

    def create_session(self, name: str, operator: str, mode: str = "classic") -> int:
        cur = self.conn.execute(
            "INSERT INTO sessions (name, operator, started_at, mode) VALUES (?,?,?,?)",
            (name, operator, _now(), mode),
        )
        self.conn.commit()
        return cur.lastrowid

    def log_action(self, session_id: int, operator: str, tool: str,
                   params: dict, output_hash: str) -> None:
        self.conn.execute(
            "INSERT INTO actions (session_id, ts, operator, tool, params, output_hash) "
            "VALUES (?,?,?,?,?,?)",
            (session_id, _now(), operator, tool, json.dumps(params), output_hash),
        )
        self.conn.commit()

    def actions_for(self, session_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM actions WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_session_store.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add spectrenet/storage/schema.sql spectrenet/storage/session.py tests/test_session_store.py
git commit -m "feat: add SQLite session storage with audit action log"
```

---

## Task 12: CVE knowledge base

**Files:**
- Create: `spectrenet/knowledge/schema.sql`
- Create: `spectrenet/knowledge/cve_db.py`
- Test: `tests/test_cve_db.py`

- [ ] **Step 1: Create the schema**

```sql
-- spectrenet/knowledge/schema.sql
CREATE TABLE IF NOT EXISTS cves (
    cve_id TEXT PRIMARY KEY,
    cvss REAL,
    service TEXT,
    version_match TEXT,
    description TEXT
);

CREATE INDEX IF NOT EXISTS idx_cves_service ON cves(service);
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_cve_db.py
from spectrenet.knowledge.cve_db import CVEKnowledgeBase

def test_seed_and_query_by_service(tmp_path):
    kb = CVEKnowledgeBase(tmp_path / "cve.db")
    kb.add_cve("CVE-2017-0144", 9.3, "microsoft-ds", "Samba 4.6", "EternalBlue SMB RCE")
    kb.add_cve("CVE-2014-6271", 10.0, "bash", "<4.3", "Shellshock")
    hits = kb.find_by_service("microsoft-ds")
    assert len(hits) == 1
    assert hits[0]["cve_id"] == "CVE-2017-0144"
    assert hits[0]["cvss"] == 9.3

def test_query_unknown_service_returns_empty(tmp_path):
    kb = CVEKnowledgeBase(tmp_path / "cve.db")
    assert kb.find_by_service("nothing") == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_cve_db.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# spectrenet/knowledge/cve_db.py
import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).parent / "schema.sql"

class CVEKnowledgeBase:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA.read_text())
        self.conn.commit()

    def add_cve(self, cve_id: str, cvss: float, service: str,
                version_match: str, description: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO cves VALUES (?,?,?,?,?)",
            (cve_id, cvss, service, version_match, description),
        )
        self.conn.commit()

    def find_by_service(self, service: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM cves WHERE service=? ORDER BY cvss DESC", (service,)
        ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_cve_db.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add spectrenet/knowledge/schema.sql spectrenet/knowledge/cve_db.py tests/test_cve_db.py
git commit -m "feat: add SQLite CVE knowledge base with service lookup"
```

---

## Task 13: Command parser

**Files:**
- Create: `spectrenet/tui/command_parser.py`
- Test: `tests/test_command_parser.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_command_parser.py
from spectrenet.tui.command_parser import parse_command, Command

def test_parse_simple_verb_and_arg():
    cmd = parse_command("scan 192.168.1.0/24")
    assert cmd == Command(verb="scan", args=["192.168.1.0/24"], flags={})

def test_parse_flags():
    cmd = parse_command("scan 10.0.0.1 --tool nmap --ports 1-1000")
    assert cmd.verb == "scan"
    assert cmd.args == ["10.0.0.1"]
    assert cmd.flags == {"tool": "nmap", "ports": "1-1000"}

def test_parse_empty_returns_none():
    assert parse_command("   ") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_command_parser.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# spectrenet/tui/command_parser.py
from dataclasses import dataclass, field

@dataclass
class Command:
    verb: str
    args: list[str] = field(default_factory=list)
    flags: dict[str, str] = field(default_factory=dict)

def parse_command(line: str):
    tokens = line.split()
    if not tokens:
        return None
    verb = tokens[0]
    args: list[str] = []
    flags: dict[str, str] = {}
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--"):
            key = tok[2:]
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                flags[key] = tokens[i + 1]
                i += 2
            else:
                flags[key] = "true"
                i += 1
        else:
            args.append(tok)
            i += 1
    return Command(verb=verb, args=args, flags=flags)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_command_parser.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add spectrenet/tui/command_parser.py tests/test_command_parser.py
git commit -m "feat: add TUI command parser (verb/args/flags)"
```

---

## Task 14: TUI shell + CLI entry point

**Files:**
- Create: `spectrenet/tui/app.py`
- Create: `spectrenet/cli.py`

- [ ] **Step 1: Write the Textual app**

```python
# spectrenet/tui/app.py
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
from textual.containers import Vertical
from spectrenet import APP_NAME, TAGLINE, __version__
from spectrenet.theme import BANNER, CYAN, NAVY_DEEP
from spectrenet.tui.command_parser import parse_command

class SpectreNetApp(App):
    CSS = f"""
    Screen {{ background: {NAVY_DEEP}; }}
    RichLog {{ border: round {CYAN}; height: 1fr; }}
    Input {{ border: round {CYAN}; }}
    """
    TITLE = APP_NAME
    SUB_TITLE = TAGLINE

    def __init__(self, registry, recon, **kwargs):
        super().__init__(**kwargs)
        self.registry = registry
        self.recon = recon

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            self.log_view = RichLog(highlight=True, markup=True)
            yield self.log_view
            yield Input(placeholder="snet> type a command (scan, wrappers, help, quit)")
        yield Footer()

    def on_mount(self) -> None:
        self.log_view.write(f"[bold {CYAN}]{BANNER}[/]")
        self.log_view.write(f"[{CYAN}]{APP_NAME} v{__version__}[/] — {TAGLINE}")
        self.log_view.write(f"Wrappers available: {', '.join(self.registry.available()) or 'none'}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = parse_command(event.value)
        event.input.value = ""
        if cmd is None:
            return
        if cmd.verb in ("quit", "exit"):
            self.exit()
        elif cmd.verb == "help":
            self.log_view.write("Commands: scan <target> --tool <name>, wrappers, help, quit")
        elif cmd.verb == "wrappers":
            self.log_view.write("Registered: " + ", ".join(self.registry.names()))
        elif cmd.verb == "scan":
            self._do_scan(cmd)
        else:
            self.log_view.write(f"[red]Unknown command:[/] {cmd.verb}")

    def _do_scan(self, cmd) -> None:
        if not cmd.args:
            self.log_view.write("[red]scan requires a target[/]")
            return
        tool = cmd.flags.get("tool", "nmap")
        target = cmd.args[0]
        try:
            result = self.recon.scan(tool=tool, target=target)
            for host in result["hosts"]:
                ports = ", ".join(str(p["port"]) for p in host["ports"])
                self.log_view.write(f"[{CYAN}]{host['ip']}[/]  ports: {ports}")
        except Exception as e:
            self.log_view.write(f"[red]scan failed:[/] {e}")
```

- [ ] **Step 2: Write the CLI entry point**

```python
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
```

- [ ] **Step 3: Smoke-verify the app constructs without launching the UI**

Run:
```bash
python -c "from spectrenet.wrappers.registry import WrapperRegistry; from spectrenet.engines.recon import ReconEngine; from spectrenet.tui.app import SpectreNetApp; r=WrapperRegistry(); r.discover(); app=SpectreNetApp(registry=r, recon=ReconEngine(r)); print('app constructed; wrappers:', r.names())"
```
Expected: `app constructed; wrappers: ['masscan', 'nmap']`

- [ ] **Step 4: Commit**

```bash
git add spectrenet/tui/app.py spectrenet/cli.py
git commit -m "feat: add Textual TUI shell and CLI entry point"
```

---

## Task 15: Full test suite + integration smoke

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Add a shared conftest (silences logging noise in tests)**

```python
# tests/conftest.py
import logging
import pytest

@pytest.fixture(autouse=True)
def quiet_logging():
    logging.getLogger("spectrenet").handlers.clear()
    logging.getLogger("spectrenet").addHandler(logging.NullHandler())
    yield
```

- [ ] **Step 2: Run the entire suite**

Run: `pytest -v`
Expected: all tests pass (config, registry, nmap, masscan, recon, model interface, ollama, session store, cve db, command parser). ~18 passed.

- [ ] **Step 3: Run a coverage check**

Run: `pytest --cov=spectrenet --cov-report=term-missing`
Expected: core modules (config, registry, wrappers, recon, model, storage, knowledge, command_parser) show high coverage. The TUI app and cli entry are integration-only and may show lower coverage — acceptable for Phase 1.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add shared conftest and verify full Phase 1 suite"
```

---

## Definition of Done (Phase 1)

- [ ] `pip install -e ".[dev]"` succeeds; `spectrenet` and `snet` commands exist
- [ ] `pytest -v` is green
- [ ] Launching `spectrenet` shows the themed banner, lists discovered wrappers, accepts `scan`/`wrappers`/`help`/`quit`
- [ ] Dropping a new wrapper file into `spectrenet/wrappers/custom/` makes it appear in `wrappers` with no code changes
- [ ] A session can be created and actions logged to SQLite
- [ ] The CVE knowledge base answers service lookups
- [ ] The Ollama backend is reachable through `ModelInterface.complete()` (verified by unit test; live Ollama optional)

---

*SpectreNet Phase 1 — Foundation. Always one step ahead.*
