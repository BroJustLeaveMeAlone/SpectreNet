# SpectreNet Phase 4 — Intelligence & Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the AI feedback loop so GoalEngine actually executes recon and reads results. Add a web vulnerability engine (sqlmap/nuclei/nikto), a service→exploit knowledge base, an AI report writer, failure-aware replanning, and an OpenAI-compatible model backend covering Chinese models (DeepSeek, Qwen) and local servers (LM Studio, vLLM).

**Architecture:** `OutputInterpreter` sits between every tool and the AI state dict. `WebVulnEngine` mirrors `ReconEngine` for web tooling. `ExploitMap` is a SQLite knowledge base seeded with known service→exploit mappings. `ReportWriter` synthesizes session logs + findings into a deliverable Markdown report. `GoalEngine` gains `recon_engine` + `output_interpreter` injection so recon steps actually run. `OpenAIBackend` implements `ModelInterface` using the standard `/v1/chat/completions` schema, enabling any OpenAI-spec endpoint without code changes.

**Tech Stack:** Python 3.11+, SQLite, httpx (for OpenAI backend), pytest, pytest-asyncio

---

## File Map

**New files:**
- `spectrenet/ai/output_interpreter.py` — `OutputInterpreter`: structured finding extraction from any tool output
- `spectrenet/ai/report_writer.py` — `ReportWriter`: session log + findings → Markdown report
- `spectrenet/engines/web_vuln.py` — `WebVulnEngine`: orchestrates web vuln wrappers
- `spectrenet/knowledge/__init__.py`
- `spectrenet/knowledge/exploit_map.py` — `ExploitMap`: service+version → exploit candidates (SQLite)
- `spectrenet/knowledge/exploit_map_schema.sql` — table schema reference
- `spectrenet/model/openai_backend.py` — `OpenAIBackend`: any OpenAI-spec endpoint
- `spectrenet/wrappers/builtin/sqlmap.py` — sqlmap wrapper
- `spectrenet/wrappers/builtin/nuclei.py` — nuclei wrapper
- `spectrenet/wrappers/builtin/nikto.py` — nikto wrapper
- `tests/test_output_interpreter.py`
- `tests/test_sqlmap_wrapper.py`
- `tests/test_nuclei_wrapper.py`
- `tests/test_nikto_wrapper.py`
- `tests/test_web_vuln_engine.py`
- `tests/test_exploit_map.py`
- `tests/test_report_writer.py`
- `tests/test_openai_backend.py`

**Modified files:**
- `spectrenet/ai/goal_engine.py` — add `recon_engine`, `output_interpreter` injection; real recon execution; `_replan()`; `web_vuln` step type
- `spectrenet/cli.py` — add `--model openai`, `--openai-base-url`, `--openai-api-key` flags; OpenAIBackend init
- `spectrenet/config.py` — add `openai_base_url`, `openai_api_key` fields
- `spectrenet/tui/app.py` — `_start_goal()` passes recon_engine + output_interpreter; handle `recon_complete` + `replanning` events
- `tests/test_goal_engine.py` — add recon-execution and replan tests
- `README.md` — Phase 4 progress + docs table

---

## Task 1: OutputInterpreter

**Files:**
- Create: `spectrenet/ai/output_interpreter.py`
- Test: `tests/test_output_interpreter.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_output_interpreter.py
import pytest
from spectrenet.ai.output_interpreter import OutputInterpreter


RECON_RESULT = {
    "hosts": [
        {
            "ip": "10.10.10.5",
            "ports": [
                {"port": 445, "service": "microsoft-ds", "version": "Samba 4.6.3"},
                {"port": 22,  "service": "ssh",           "version": "OpenSSH 7.4"},
            ],
        }
    ]
}

WEB_VULN_RESULT = {
    "vulnerabilities": [
        {
            "severity": "HIGH",
            "type":     "sqli",
            "url":      "http://10.10.10.5/login",
            "evidence": "1=1",
        }
    ]
}


def test_from_recon_returns_finding_per_port():
    interp = OutputInterpreter()
    findings = interp.from_recon(RECON_RESULT)
    assert len(findings) == 2


def test_from_recon_finding_schema():
    interp = OutputInterpreter()
    finding = interp.from_recon(RECON_RESULT)[0]
    assert finding["type"] == "open_port"
    assert finding["ip"] == "10.10.10.5"
    assert finding["port"] == 445
    assert finding["service"] == "microsoft-ds"
    assert finding["version"] == "Samba 4.6.3"
    assert finding["severity"] == "INFO"
    assert "detail" in finding


def test_from_recon_empty_hosts_returns_empty_list():
    interp = OutputInterpreter()
    assert interp.from_recon({"hosts": []}) == []


def test_from_web_vuln_returns_finding():
    interp = OutputInterpreter()
    findings = interp.from_web_vuln(WEB_VULN_RESULT)
    assert len(findings) == 1
    assert findings[0]["type"] == "vulnerability"
    assert findings[0]["severity"] == "HIGH"
    assert findings[0]["service"] == "sqli"


def test_from_session_output_fallback_without_model():
    interp = OutputInterpreter()
    findings = interp.from_session_output("getuid", "Server username: NT AUTHORITY\\SYSTEM")
    assert len(findings) == 1
    assert findings[0]["type"] == "post_ex"
    assert "SYSTEM" in findings[0]["detail"]


def test_from_session_output_uses_model_when_available():
    class FakeModel:
        def complete(self, system_prompt, user_prompt):
            return '[{"type":"credential","detail":"SYSTEM shell","severity":"CRITICAL","ip":"","port":null,"service":"","version":"","raw":""}]'

    interp = OutputInterpreter(model=FakeModel())
    findings = interp.from_session_output("getuid", "Server username: NT AUTHORITY\\SYSTEM")
    assert findings[0]["type"] == "credential"
    assert findings[0]["severity"] == "CRITICAL"


def test_from_session_output_falls_back_when_model_returns_invalid_json():
    class BadModel:
        def complete(self, system_prompt, user_prompt):
            return "not json at all"

    interp = OutputInterpreter(model=BadModel())
    findings = interp.from_session_output("sysinfo", "Computer: TARGET-PC")
    assert findings[0]["type"] == "post_ex"
```

- [ ] **Step 2: Implement OutputInterpreter**

```python
# spectrenet/ai/output_interpreter.py
from __future__ import annotations
import json
from typing import Any


_SEVERITY_MAP = {"CRITICAL": "CRITICAL", "HIGH": "HIGH", "MED": "MED",
                 "MEDIUM": "MED", "LOW": "LOW", "INFO": "INFO"}

_SESSION_SYSTEM = (
    "You are a penetration testing assistant. "
    "Given post-exploitation command output, extract a JSON array of findings. "
    "Each finding must match this schema exactly: "
    '{"type": str, "ip": str, "port": int|null, "service": str, '
    '"version": str, "severity": str, "detail": str, "raw": str}. '
    "Use severity CRITICAL for SYSTEM/root shells or clear credentials, "
    "HIGH for domain user credentials, MED for local users, INFO otherwise. "
    "Return ONLY the JSON array, no markdown fences."
)


class OutputInterpreter:
    def __init__(self, model: Any | None = None) -> None:
        self._model = model

    def from_recon(self, recon_result: dict) -> list[dict]:
        findings: list[dict] = []
        for host in recon_result.get("hosts", []):
            ip = host.get("ip", "")
            for port_info in host.get("ports", []):
                port = port_info.get("port")
                service = port_info.get("service", "")
                version = port_info.get("version", "")
                findings.append({
                    "type":     "open_port",
                    "ip":       ip,
                    "port":     port,
                    "service":  service,
                    "version":  version,
                    "severity": "INFO",
                    "detail":   f"{service} {version} on port {port}".strip(),
                    "raw":      str(port_info),
                })
        return findings

    def from_web_vuln(self, vuln_result: dict) -> list[dict]:
        findings: list[dict] = []
        for vuln in vuln_result.get("vulnerabilities", []):
            severity = _SEVERITY_MAP.get(vuln.get("severity", "INFO").upper(), "INFO")
            findings.append({
                "type":     "vulnerability",
                "ip":       vuln.get("ip", ""),
                "port":     vuln.get("port"),
                "service":  vuln.get("type", ""),
                "version":  "",
                "severity": severity,
                "detail":   f"{vuln.get('type', '')} at {vuln.get('url', '')}",
                "raw":      str(vuln),
            })
        return findings

    def from_session_output(self, command: str, output: str) -> list[dict]:
        if self._model is not None:
            try:
                user_prompt = f"Command: {command}\nOutput:\n{output}"
                raw = self._model.complete(_SESSION_SYSTEM, user_prompt)
                parsed = json.loads(raw)
                if isinstance(parsed, list) and parsed:
                    return parsed
            except Exception:
                pass
        return [{
            "type":     "post_ex",
            "ip":       "",
            "port":     None,
            "service":  "",
            "version":  "",
            "severity": "INFO",
            "detail":   output,
            "raw":      output,
        }]
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_output_interpreter.py -v
```

All 7 tests should pass.

- [ ] **Step 4: Commit**

```
git add spectrenet/ai/output_interpreter.py tests/test_output_interpreter.py
git commit -m "feat(phase4): add OutputInterpreter for structured finding extraction"
```

---

## Task 2: Web Vulnerability Wrappers (sqlmap, nuclei, nikto)

**Files:**
- Create: `spectrenet/wrappers/builtin/sqlmap.py`
- Create: `spectrenet/wrappers/builtin/nuclei.py`
- Create: `spectrenet/wrappers/builtin/nikto.py`
- Test: `tests/test_sqlmap_wrapper.py`, `tests/test_nuclei_wrapper.py`, `tests/test_nikto_wrapper.py`

- [ ] **Step 1: Write failing tests — sqlmap**

```python
# tests/test_sqlmap_wrapper.py
import pytest
from spectrenet.wrappers.builtin.sqlmap import SqlmapWrapper

INJECTABLE_OUTPUT = """\
[INFO] GET parameter 'id' is vulnerable. Do you want to keep testing the others (if any)? [y/N] N
[INFO] sqlmap identified the following injection point(s) with a total of 42 HTTP(s) requests:
Parameter: id (GET)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE or HAVING clause
available databases [2]:
[*] information_schema
[*] webapp
"""

NOT_INJECTABLE = "[INFO] all tested parameters do not appear to be injectable"


def test_parse_injectable_true():
    w = SqlmapWrapper()
    result = w.parse(INJECTABLE_OUTPUT)
    assert result["injectable"] is True


def test_parse_detects_payload_type():
    w = SqlmapWrapper()
    result = w.parse(INJECTABLE_OUTPUT)
    assert "boolean-based blind" in result["payloads"]


def test_parse_extracts_databases():
    w = SqlmapWrapper()
    result = w.parse(INJECTABLE_OUTPUT)
    assert "webapp" in result["databases"]
    assert "information_schema" in result["databases"]


def test_parse_not_injectable():
    w = SqlmapWrapper()
    result = w.parse(NOT_INJECTABLE)
    assert result["injectable"] is False
    assert result["databases"] == []


def test_schema_present():
    w = SqlmapWrapper()
    schema = w.schema
    assert "injectable" in schema
    assert "databases" in schema
```

- [ ] **Step 2: Implement SqlmapWrapper**

```python
# spectrenet/wrappers/builtin/sqlmap.py
from __future__ import annotations
import re
import subprocess
from spectrenet.wrappers.base import ToolWrapper


class SqlmapWrapper(ToolWrapper):
    tool_name = "sqlmap"

    @property
    def schema(self) -> dict:
        return {
            "injectable": bool,
            "payloads":   list,
            "databases":  list,
            "tables":     dict,
            "dump":       dict,
        }

    def parse(self, text: str) -> dict:
        injectable = "is vulnerable" in text or "injection point" in text
        payloads: list[str] = []
        for line in text.splitlines():
            m = re.match(r"\s+Type:\s+(.+)", line)
            if m:
                payloads.append(m.group(1).strip())
        databases: list[str] = []
        in_db_section = False
        for line in text.splitlines():
            if "available databases" in line:
                in_db_section = True
                continue
            if in_db_section:
                m = re.match(r"\[\*\]\s+(\S+)", line)
                if m:
                    databases.append(m.group(1))
                elif line.strip() and not line.startswith("["):
                    in_db_section = False
        return {"injectable": injectable, "payloads": payloads,
                "databases": databases, "tables": {}, "dump": {}}

    def run(self, target: str, **kwargs) -> dict:
        extra = kwargs.get("extra_args", [])
        result = subprocess.run(
            ["sqlmap", "-u", target, "--batch", "--output-dir=/tmp/sqlmap_out"] + extra,
            capture_output=True, text=True, timeout=300,
        )
        return self.parse(result.stdout + result.stderr)
```

- [ ] **Step 3: Write failing tests — nuclei**

```python
# tests/test_nuclei_wrapper.py
import pytest
from spectrenet.wrappers.builtin.nuclei import NucleiWrapper

NUCLEI_OUTPUT = """\
[2024-01-01 12:00:00] [cve-2021-44228] [http] [critical] http://10.10.10.5/api/log?input= ["log4shell"]
[2024-01-01 12:00:01] [xss-generic] [http] [medium] http://10.10.10.5/search?q= ["XSS"]
"""

EMPTY_OUTPUT = ""


def test_parse_detects_two_vulns():
    w = NucleiWrapper()
    result = w.parse(NUCLEI_OUTPUT)
    assert len(result["vulnerabilities"]) == 2


def test_parse_critical_severity():
    w = NucleiWrapper()
    vulns = w.parse(NUCLEI_OUTPUT)["vulnerabilities"]
    crit = [v for v in vulns if v["severity"].upper() == "CRITICAL"]
    assert crit


def test_parse_template_id():
    w = NucleiWrapper()
    vulns = w.parse(NUCLEI_OUTPUT)["vulnerabilities"]
    assert any(v["template_id"] == "cve-2021-44228" for v in vulns)


def test_parse_empty_returns_no_vulns():
    w = NucleiWrapper()
    assert w.parse(EMPTY_OUTPUT)["vulnerabilities"] == []


def test_schema_present():
    w = NucleiWrapper()
    assert "vulnerabilities" in w.schema
```

- [ ] **Step 4: Implement NucleiWrapper**

```python
# spectrenet/wrappers/builtin/nuclei.py
from __future__ import annotations
import re
import subprocess
from spectrenet.wrappers.base import ToolWrapper

_LINE_RE = re.compile(
    r"\[[\d\-: ]+\]\s+\[([^\]]+)\]\s+\[([^\]]+)\]\s+\[([^\]]+)\]\s+(\S+)"
)


class NucleiWrapper(ToolWrapper):
    tool_name = "nuclei"

    @property
    def schema(self) -> dict:
        return {"vulnerabilities": list}

    def parse(self, text: str) -> dict:
        vulns: list[dict] = []
        for line in text.splitlines():
            m = _LINE_RE.search(line)
            if m:
                template_id, proto, severity, url = m.groups()
                vulns.append({
                    "template_id": template_id,
                    "severity":    severity,
                    "type":        proto,
                    "url":         url,
                    "matched_at":  url,
                    "evidence":    line.strip(),
                })
        return {"vulnerabilities": vulns}

    def run(self, target: str, **kwargs) -> dict:
        templates = kwargs.get("templates", "cves,vulnerabilities")
        result = subprocess.run(
            ["nuclei", "-u", target, "-t", templates, "-silent"],
            capture_output=True, text=True, timeout=300,
        )
        return self.parse(result.stdout + result.stderr)
```

- [ ] **Step 5: Write failing tests — nikto**

```python
# tests/test_nikto_wrapper.py
import pytest
from spectrenet.wrappers.builtin.nikto import NiktoWrapper

NIKTO_OUTPUT = """\
- Nikto v2.1.6
---------------------------------------------------------------------------
+ Target IP:          10.10.10.5
+ Target Port:        80
---------------------------------------------------------------------------
+ Server: Apache/2.2.14 (Ubuntu)
+ OSVDB-3268: /icons/: Directory indexing found.
+ OSVDB-3233: /icons/README: Apache default file found.
+ 8345 requests: 0 error(s) and 2 item(s) reported on remote host
"""

EMPTY_OUTPUT = "- Nikto v2.1.6\n0 items reported"


def test_parse_returns_two_findings():
    w = NiktoWrapper()
    result = w.parse(NIKTO_OUTPUT)
    assert len(result["findings"]) == 2


def test_parse_finding_has_id_and_msg():
    w = NiktoWrapper()
    findings = w.parse(NIKTO_OUTPUT)["findings"]
    assert findings[0]["id"] == "OSVDB-3268"
    assert "Directory indexing" in findings[0]["msg"]


def test_parse_target_captured():
    w = NiktoWrapper()
    result = w.parse(NIKTO_OUTPUT)
    assert result["target"] == "10.10.10.5"


def test_parse_empty_returns_no_findings():
    w = NiktoWrapper()
    assert w.parse(EMPTY_OUTPUT)["findings"] == []


def test_schema_present():
    w = NiktoWrapper()
    assert "findings" in w.schema
```

- [ ] **Step 6: Implement NiktoWrapper**

```python
# spectrenet/wrappers/builtin/nikto.py
from __future__ import annotations
import re
import subprocess
from spectrenet.wrappers.base import ToolWrapper

_FINDING_RE = re.compile(r"\+\s+(OSVDB-\d+|CVE-[\d-]+):\s+(.+)")
_TARGET_RE   = re.compile(r"\+ Target IP:\s+(\S+)")


class NiktoWrapper(ToolWrapper):
    tool_name = "nikto"

    @property
    def schema(self) -> dict:
        return {"target": str, "findings": list}

    def parse(self, text: str) -> dict:
        target = ""
        m = _TARGET_RE.search(text)
        if m:
            target = m.group(1)
        findings: list[dict] = []
        for line in text.splitlines():
            fm = _FINDING_RE.search(line)
            if fm:
                findings.append({
                    "id":       fm.group(1),
                    "method":   "GET",
                    "url":      "",
                    "msg":      fm.group(2).strip(),
                    "severity": "LOW",
                })
        return {"target": target, "findings": findings}

    def run(self, target: str, **kwargs) -> dict:
        port = kwargs.get("port", 80)
        result = subprocess.run(
            ["nikto", "-h", target, "-p", str(port), "-nointeractive"],
            capture_output=True, text=True, timeout=300,
        )
        return self.parse(result.stdout + result.stderr)
```

- [ ] **Step 7: Run all wrapper tests**

```bash
python -m pytest tests/test_sqlmap_wrapper.py tests/test_nuclei_wrapper.py tests/test_nikto_wrapper.py -v
```

All 14 tests should pass.

- [ ] **Step 8: Commit**

```
git add spectrenet/wrappers/builtin/sqlmap.py spectrenet/wrappers/builtin/nuclei.py \
        spectrenet/wrappers/builtin/nikto.py \
        tests/test_sqlmap_wrapper.py tests/test_nuclei_wrapper.py tests/test_nikto_wrapper.py
git commit -m "feat(phase4): add sqlmap, nuclei, nikto wrappers"
```

---

## Task 3: WebVulnEngine

**Files:**
- Create: `spectrenet/engines/web_vuln.py`
- Test: `tests/test_web_vuln_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_web_vuln_engine.py
import pytest
from spectrenet.engines.web_vuln import WebVulnEngine
from spectrenet.wrappers.registry import WrapperRegistry


class FakeWebWrapper:
    tool_name = "fakeweb"
    schema = {"vulnerabilities": list}

    def run(self, target: str, **kwargs) -> dict:
        return {"vulnerabilities": [{"severity": "HIGH", "type": "xss",
                                     "url": f"http://{target}/", "evidence": "test"}]}


def _engine_with_fake():
    reg = WrapperRegistry()
    reg.register(FakeWebWrapper())
    return WebVulnEngine(reg)


def test_scan_returns_vulnerabilities():
    engine = _engine_with_fake()
    result = engine.scan(tool="fakeweb", target="10.10.10.5")
    assert "vulnerabilities" in result
    assert len(result["vulnerabilities"]) == 1


def test_scan_raises_for_unknown_tool():
    engine = _engine_with_fake()
    with pytest.raises(ValueError, match="not available"):
        engine.scan(tool="nothere", target="10.10.10.5")


def test_scan_passes_kwargs_to_wrapper():
    calls = {}

    class RecordingWrapper:
        tool_name = "recorder"
        schema = {}

        def run(self, target: str, **kwargs) -> dict:
            calls["kwargs"] = kwargs
            return {"vulnerabilities": []}

    reg = WrapperRegistry()
    reg.register(RecordingWrapper())
    engine = WebVulnEngine(reg)
    engine.scan(tool="recorder", target="10.10.10.5", extra_args=["--level=3"])
    assert calls["kwargs"].get("extra_args") == ["--level=3"]


def test_scan_logs_finding_count(caplog):
    import logging
    engine = _engine_with_fake()
    with caplog.at_level(logging.INFO):
        engine.scan(tool="fakeweb", target="10.10.10.5")
    assert any("fakeweb" in r.message for r in caplog.records)
```

- [ ] **Step 2: Implement WebVulnEngine**

```python
# spectrenet/engines/web_vuln.py
from __future__ import annotations
import logging
from spectrenet.wrappers.registry import WrapperRegistry

_log = logging.getLogger(__name__)


class WebVulnEngine:
    def __init__(self, registry: WrapperRegistry) -> None:
        self.registry = registry

    def scan(self, tool: str, target: str, **kwargs) -> dict:
        if tool not in self.registry.available():
            raise ValueError(f"Web vuln tool '{tool}' is not available in registry")
        wrapper = self.registry.get(tool)
        _log.info("WebVulnEngine: starting %s → %s", tool, target)
        result = wrapper.run(target=target, **kwargs)
        vuln_count = len(result.get("vulnerabilities", result.get("findings", [])))
        _log.info("WebVulnEngine: %s complete — %d findings", tool, vuln_count)
        return result
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_web_vuln_engine.py -v
```

All 4 tests pass.

- [ ] **Step 4: Commit**

```
git add spectrenet/engines/web_vuln.py tests/test_web_vuln_engine.py
git commit -m "feat(phase4): add WebVulnEngine orchestrating web vuln wrappers"
```

---

## Task 4: ExploitMap

**Files:**
- Create: `spectrenet/knowledge/__init__.py`
- Create: `spectrenet/knowledge/exploit_map.py`
- Create: `spectrenet/knowledge/exploit_map_schema.sql`
- Test: `tests/test_exploit_map.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_exploit_map.py
import pytest
from spectrenet.knowledge.exploit_map import ExploitMap


@pytest.fixture
def fresh_map(tmp_path):
    return ExploitMap(db_path=str(tmp_path / "exploit_map.db"))


def test_add_and_find_exact_match(fresh_map):
    fresh_map.add_entry(
        service="ftp", version_pattern="vsftpd 2\\.3\\.4",
        exploit_name="vsftpd Backdoor", msf_module="exploit/unix/ftp/vsftpd_234_backdoor",
        platform="linux", reliability="excellent",
    )
    results = fresh_map.find_exploits("ftp", "vsftpd 2.3.4")
    assert len(results) == 1
    assert results[0]["msf_module"] == "exploit/unix/ftp/vsftpd_234_backdoor"


def test_find_with_wildcard_pattern(fresh_map):
    fresh_map.add_entry(
        service="microsoft-ds", version_pattern=".*",
        exploit_name="EternalBlue", msf_module="exploit/windows/smb/ms17_010_eternalblue",
        platform="windows", reliability="excellent",
    )
    results = fresh_map.find_exploits("microsoft-ds", "Windows 7 SP1")
    assert any(r["exploit_name"] == "EternalBlue" for r in results)


def test_no_match_returns_empty(fresh_map):
    assert fresh_map.find_exploits("telnet", "unknown 1.0") == []


def test_seed_defaults_loads_entries(fresh_map):
    fresh_map.seed_defaults()
    results = fresh_map.find_exploits("microsoft-ds", "anything")
    assert len(results) >= 2


def test_seed_defaults_ftp_backdoor(fresh_map):
    fresh_map.seed_defaults()
    results = fresh_map.find_exploits("ftp", "vsftpd 2.3.4")
    assert any(r["msf_module"] == "exploit/unix/ftp/vsftpd_234_backdoor" for r in results)


def test_result_schema(fresh_map):
    fresh_map.seed_defaults()
    results = fresh_map.find_exploits("microsoft-ds", "x")
    r = results[0]
    for key in ("service", "exploit_name", "msf_module", "platform", "reliability"):
        assert key in r
```

- [ ] **Step 2: Implement ExploitMap**

```python
# spectrenet/knowledge/__init__.py
```

```python
# spectrenet/knowledge/exploit_map.py
from __future__ import annotations
import re
import sqlite3
from pathlib import Path

_DEFAULT_DB = "spectrenet_exploit_map.db"

_SEED_DATA = [
    ("microsoft-ds", r".*", "EternalBlue", "exploit/windows/smb/ms17_010_eternalblue", "windows", "excellent", "CVE-2017-0144"),
    ("microsoft-ds", r".*", "EternalRomance", "exploit/windows/smb/ms17_010_psexec", "windows", "great", "CVE-2017-0144"),
    ("ssh", r"OpenSSH [1-6]\\..*", "SSH Bruteforce", "auxiliary/scanner/ssh/ssh_login", "multi", "normal", ""),
    ("http", r"Apache 2\\.[0-3]\\..*", "Shellshock", "exploit/multi/http/apache_mod_cgi_bash_env_exec", "multi", "excellent", "CVE-2014-6271"),
    ("ftp", r"vsftpd 2\\.3\\.4", "vsftpd Backdoor", "exploit/unix/ftp/vsftpd_234_backdoor", "linux", "excellent", "CVE-2011-2523"),
    ("http", r".*Apache Tomcat.*", "Tomcat Manager Upload", "exploit/multi/http/tomcat_mgr_upload", "multi", "excellent", ""),
    ("mysql", r".*", "MySQL UDF", "exploit/linux/mysql/mysql_udf_payload", "linux", "great", ""),
    ("postgresql", r".*", "PostgreSQL COPY", "exploit/linux/postgres/postgres_copy_from_program_cmd_exec", "linux", "excellent", "CVE-2019-9193"),
    ("http", r".*", "Apache Struts RCE", "exploit/multi/http/struts2_content_type_ognl", "multi", "excellent", "CVE-2017-5638"),
    ("rdp", r".*", "BlueKeep", "exploit/windows/rdp/cve_2019_0708_bluekeep_rce", "windows", "great", "CVE-2019-0708"),
]


class ExploitMap:
    def __init__(self, db_path: str = _DEFAULT_DB) -> None:
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS exploit_map (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    service          TEXT NOT NULL,
                    version_pattern  TEXT NOT NULL,
                    exploit_name     TEXT NOT NULL,
                    msf_module       TEXT NOT NULL,
                    platform         TEXT NOT NULL,
                    reliability      TEXT NOT NULL,
                    cve_id           TEXT DEFAULT ''
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def add_entry(self, service: str, version_pattern: str, exploit_name: str,
                  msf_module: str, platform: str, reliability: str,
                  cve_id: str = "") -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO exploit_map "
                "(service, version_pattern, exploit_name, msf_module, platform, reliability, cve_id) "
                "VALUES (?,?,?,?,?,?,?)",
                (service, version_pattern, exploit_name, msf_module, platform, reliability, cve_id),
            )

    def find_exploits(self, service: str, version: str) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT service, version_pattern, exploit_name, msf_module, platform, reliability, cve_id "
                "FROM exploit_map WHERE service = ?",
                (service,),
            ).fetchall()
        results = []
        for row in rows:
            svc, pattern, name, module, platform, reliability, cve_id = row
            try:
                if re.search(pattern, version, re.IGNORECASE):
                    results.append({
                        "service":      svc,
                        "version_pattern": pattern,
                        "exploit_name": name,
                        "msf_module":   module,
                        "platform":     platform,
                        "reliability":  reliability,
                        "cve_id":       cve_id,
                    })
            except re.error:
                pass
        return results

    def seed_defaults(self) -> None:
        with self._connect() as con:
            existing = con.execute("SELECT COUNT(*) FROM exploit_map").fetchone()[0]
        if existing == 0:
            for row in _SEED_DATA:
                self.add_entry(*row)
```

- [ ] **Step 3: Write the schema SQL reference**

```sql
-- spectrenet/knowledge/exploit_map_schema.sql
-- Reference only — ExploitMap creates this table programmatically.
CREATE TABLE IF NOT EXISTS exploit_map (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    service          TEXT NOT NULL,
    version_pattern  TEXT NOT NULL,   -- Python regex matched against detected version string
    exploit_name     TEXT NOT NULL,
    msf_module       TEXT NOT NULL,   -- full MSF module path
    platform         TEXT NOT NULL,   -- windows | linux | multi
    reliability      TEXT NOT NULL,   -- excellent | great | good | normal | low
    cve_id           TEXT DEFAULT ''
);
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_exploit_map.py -v
```

All 6 tests pass.

- [ ] **Step 5: Commit**

```
git add spectrenet/knowledge/ tests/test_exploit_map.py
git commit -m "feat(phase4): add ExploitMap — service+version to MSF module knowledge base"
```

---

## Task 5: ReportWriter

**Files:**
- Create: `spectrenet/ai/report_writer.py`
- Test: `tests/test_report_writer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_report_writer.py
import pytest
from unittest.mock import MagicMock
from spectrenet.ai.report_writer import ReportWriter


class ScriptedModel:
    def __init__(self, responses: list[str]):
        self._it = iter(responses)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        try:
            return next(self._it)
        except StopIteration:
            return ""


class FakeSessionStore:
    def get_actions(self, session_id: int):
        return [
            {"id": 1, "action_type": "recon", "tool": "nmap",
             "target": "10.10.10.5", "result": "open_port 445", "timestamp": "2026-06-07T10:00:00"},
            {"id": 2, "action_type": "exploit", "tool": "ms17_010_eternalblue",
             "target": "10.10.10.5", "result": "session_opened", "timestamp": "2026-06-07T10:01:00"},
        ]

    def get_approvals(self, session_id: int):
        return [
            {"action_id": 2, "decision": "Y", "timestamp": "2026-06-07T10:00:55"},
        ]


FINDINGS = [
    {"type": "open_port",    "ip": "10.10.10.5", "port": 445, "service": "microsoft-ds",
     "version": "Samba 4.6", "severity": "INFO",     "detail": "SMB open"},
    {"type": "vulnerability","ip": "10.10.10.5", "port": 445, "service": "smb",
     "version": "",           "severity": "CRITICAL",  "detail": "EternalBlue"},
]


def test_report_contains_executive_summary():
    model = ScriptedModel([
        "## Executive Summary\nThis engagement identified one critical vulnerability.",
        "## Recommendations\nPatch immediately.",
    ])
    writer = ReportWriter(model)
    report = writer.generate(FakeSessionStore(), session_id=1, findings=FINDINGS)
    assert "Executive Summary" in report


def test_report_contains_findings_section():
    model = ScriptedModel([
        "Summary here",
        "Recommendations here",
    ])
    writer = ReportWriter(model)
    report = writer.generate(FakeSessionStore(), session_id=1, findings=FINDINGS)
    assert "Findings" in report


def test_report_contains_exploitation_timeline():
    model = ScriptedModel(["Summary", "Recs"])
    writer = ReportWriter(model)
    report = writer.generate(FakeSessionStore(), session_id=1, findings=FINDINGS)
    assert "Timeline" in report or "nmap" in report


def test_report_groups_findings_by_severity():
    model = ScriptedModel(["Summary", "Recs"])
    writer = ReportWriter(model)
    report = writer.generate(FakeSessionStore(), session_id=1, findings=FINDINGS)
    assert "CRITICAL" in report


def test_report_with_empty_findings_still_returns_markdown():
    model = ScriptedModel(["Summary", "Recs"])
    writer = ReportWriter(model)
    report = writer.generate(FakeSessionStore(), session_id=1, findings=[])
    assert isinstance(report, str)
    assert len(report) > 0
```

- [ ] **Step 2: Implement ReportWriter**

```python
# spectrenet/ai/report_writer.py
from __future__ import annotations
from datetime import datetime
from typing import Any

_SUMMARY_SYSTEM = (
    "You are a professional penetration tester writing an engagement report. "
    "Given a list of findings and an action summary, write the Executive Summary "
    "and Scope & Methodology sections in clear, professional Markdown. "
    "Be concise. Use ## headings. Do not use code blocks."
)

_RECS_SYSTEM = (
    "You are a professional penetration tester. Given a list of findings by severity, "
    "write a Recommendations section in Markdown. Each recommendation should map to a "
    "specific finding type. Use ## Recommendations as the heading."
)


class ReportWriter:
    def __init__(self, model: Any) -> None:
        self._model = model

    def generate(self, session_store: Any, session_id: int,
                 findings: list[dict] | None = None) -> str:
        findings = findings or []
        actions = session_store.get_actions(session_id)
        approvals = session_store.get_approvals(session_id)

        by_severity: dict[str, list[dict]] = {}
        for f in findings:
            sev = f.get("severity", "INFO")
            by_severity.setdefault(sev, []).append(f)

        finding_summary = (
            f"{len(findings)} total findings: "
            + ", ".join(f"{len(v)} {k}" for k, v in sorted(by_severity.items()))
        ) if findings else "No findings recorded."

        summary_prompt = (
            f"Engagement scope: session {session_id}\n"
            f"Actions performed: {len(actions)}\n"
            f"Approvals granted: {len([a for a in approvals if a.get('decision') == 'Y'])}\n"
            f"Findings: {finding_summary}\n"
        )
        summary_section = self._safe_complete(_SUMMARY_SYSTEM, summary_prompt)

        recs_prompt = "\n".join(
            f"- [{f['severity']}] {f['detail']}" for f in findings
        ) or "No findings."
        recs_section = self._safe_complete(_RECS_SYSTEM, recs_prompt)

        timeline = self._build_timeline(actions, approvals)
        findings_section = self._build_findings_section(by_severity)
        action_log = self._build_action_log(actions)

        return "\n\n".join([
            "# SpectreNet Engagement Report",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            summary_section,
            findings_section,
            "## Exploitation Timeline",
            timeline,
            recs_section,
            "## Appendix — Full Action Log",
            action_log,
        ])

    def _safe_complete(self, system: str, user: str) -> str:
        try:
            return self._model.complete(system, user) or ""
        except Exception:
            return ""

    def _build_findings_section(self, by_severity: dict[str, list[dict]]) -> str:
        lines = ["## Findings"]
        order = ["CRITICAL", "HIGH", "MED", "LOW", "INFO"]
        for sev in order:
            items = by_severity.get(sev, [])
            if not items:
                continue
            lines.append(f"\n### {sev}")
            for f in items:
                lines.append(f"- **{f.get('service', '')}** on {f.get('ip', '')}"
                              f":{f.get('port', '')} — {f.get('detail', '')}")
        if not any(by_severity.get(s) for s in order):
            lines.append("No findings recorded.")
        return "\n".join(lines)

    def _build_timeline(self, actions: list[dict], approvals: list[dict]) -> str:
        approval_map = {a["action_id"]: a["decision"] for a in approvals}
        lines = []
        for a in actions:
            ts = a.get("timestamp", "")
            decision = approval_map.get(a.get("id"))
            dec_str = f" [{decision}]" if decision else ""
            lines.append(
                f"- `{ts}` **{a.get('action_type', '')}** "
                f"{a.get('tool', '')} → {a.get('target', '')}{dec_str}"
            )
        return "\n".join(lines) if lines else "*No actions recorded.*"

    def _build_action_log(self, actions: list[dict]) -> str:
        lines = ["| # | Type | Tool | Target | Result |",
                 "|---|---|---|---|---|"]
        for a in actions:
            lines.append(
                f"| {a.get('id','')} | {a.get('action_type','')} "
                f"| {a.get('tool','')} | {a.get('target','')} "
                f"| {a.get('result','')} |"
            )
        return "\n".join(lines)
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_report_writer.py -v
```

All 5 tests pass.

- [ ] **Step 4: Commit**

```
git add spectrenet/ai/report_writer.py tests/test_report_writer.py
git commit -m "feat(phase4): add ReportWriter — AI-generated Markdown pentest report"
```

---

## Task 6: GoalEngine Enhancements

**Files:**
- Modify: `spectrenet/ai/goal_engine.py`
- Modify: `spectrenet/tui/app.py`
- Modify: `tests/test_goal_engine.py`

- [ ] **Step 1: Add new tests to test_goal_engine.py**

Append these to the existing test file:

```python
# Append to tests/test_goal_engine.py


class FakeReconEngine:
    def __init__(self, result: dict):
        self._result = result
        self.calls: list[dict] = []

    def scan(self, tool: str, target: str, **kwargs) -> dict:
        self.calls.append({"tool": tool, "target": target})
        return self._result


@pytest.mark.asyncio
async def test_goal_engine_executes_recon_when_engine_injected():
    """GoalEngine actually calls ReconEngine when recon_engine is provided."""
    recon_result = {
        "hosts": [{"ip": "10.10.10.5", "ports": [
            {"port": 445, "service": "microsoft-ds", "version": "4.6"}
        ]}]
    }
    fake_recon = FakeReconEngine(recon_result)

    class ReconThenDoneModel:
        _calls = 0

        def complete(self, system_prompt, user_prompt):
            self._calls += 1
            if self._calls == 1:
                return json.dumps({
                    "step_id": "r1", "action_type": "recon",
                    "tool": "nmap", "target": "10.10.10.5",
                    "params": {}, "risk": "LOW", "reason": "discover hosts"
                })
            return json.dumps({"done": True})

    events: list[dict] = []
    engine = GoalEngine(
        model=ReconThenDoneModel(),
        exploit_engine=FakeExploitEngine(session_id=None),
        msf_bridge=FakeMsfBridge(sessions={}),
        recon_engine=fake_recon,
        on_event=events.append,
        session_poll_timeout=0,
        auto_approve=True,
    )
    engine.set_goal("find hosts on 10.10.10.5")
    await engine.start()

    assert len(fake_recon.calls) == 1
    recon_events = [e for e in events if e["type"] == "recon_complete"]
    assert recon_events


@pytest.mark.asyncio
async def test_goal_engine_injects_failed_steps_detail_on_exploit_failure():
    """On exploit failure, GoalEngine adds failed_steps_detail to state."""
    class ExploitThenDoneModel:
        _calls = 0

        def complete(self, system_prompt, user_prompt):
            self._calls += 1
            if self._calls == 1:
                return json.dumps({
                    "step_id": "e1", "action_type": "exploit",
                    "tool": "ms17_010_eternalblue", "target": "10.10.10.5",
                    "params": {}, "risk": "HIGH", "reason": "SMB exploit"
                })
            return json.dumps({"done": True})

    class FailingExploitEngine:
        def run(self, module, target, port=None, options=None):
            from spectrenet.engines.exploit import ExploitResult
            return ExploitResult(success=False, error="module failed", session_id=None)

    events: list[dict] = []
    engine = GoalEngine(
        model=ExploitThenDoneModel(),
        exploit_engine=FailingExploitEngine(),
        msf_bridge=FakeMsfBridge(sessions={}),
        on_event=events.append,
        session_poll_timeout=0,
        auto_approve=True,
    )
    engine.set_goal("exploit smb")
    await engine.start()

    assert "failed_steps_detail" in engine._state
    assert len(engine._state["failed_steps_detail"]) >= 1


@pytest.mark.asyncio
async def test_goal_engine_emits_recon_complete_with_findings():
    """GoalEngine emits recon_complete event with findings list."""
    recon_result = {
        "hosts": [{"ip": "192.168.1.1", "ports": [
            {"port": 80, "service": "http", "version": "Apache 2.4"}
        ]}]
    }
    fake_recon = FakeReconEngine(recon_result)

    class ReconModel:
        _calls = 0

        def complete(self, system_prompt, user_prompt):
            self._calls += 1
            if self._calls == 1:
                return json.dumps({
                    "step_id": "r1", "action_type": "recon",
                    "tool": "nmap", "target": "192.168.1.1",
                    "params": {}, "risk": "LOW", "reason": "scan"
                })
            return json.dumps({"done": True})

    events: list[dict] = []
    engine = GoalEngine(
        model=ReconModel(),
        exploit_engine=FakeExploitEngine(session_id=None),
        msf_bridge=FakeMsfBridge(sessions={}),
        recon_engine=fake_recon,
        on_event=events.append,
        session_poll_timeout=0,
        auto_approve=True,
    )
    engine.set_goal("recon")
    await engine.start()

    rc = [e for e in events if e["type"] == "recon_complete"]
    assert rc
    assert rc[0]["count"] == 1
```

- [ ] **Step 2: Modify GoalEngine**

In `spectrenet/ai/goal_engine.py`, update `__init__` and the recon step handling:

```python
# In __init__, add two parameters after msf_bridge:
#   recon_engine=None, output_interpreter=None

def __init__(
    self,
    model,
    exploit_engine,
    msf_bridge,
    recon_engine=None,           # NEW
    output_interpreter=None,     # NEW
    on_event=None,
    session_poll_timeout=60,
    auto_approve=False,
):
    ...
    self._recon_engine = recon_engine
    self._interpreter = output_interpreter
```

Replace the recon step handling block inside `start()` (wherever it currently does `state["recon"].append(...)`):

```python
if step.action_type == "recon":
    if self._recon_engine is not None:
        try:
            result = self._recon_engine.scan(
                tool=step.tool, target=step.target, **(step.params or {})
            )
            findings: list[dict] = []
            if self._interpreter is not None:
                findings = self._interpreter.from_recon(result)
            else:
                for host in result.get("hosts", []):
                    for p in host.get("ports", []):
                        findings.append({"type": "open_port", "ip": host.get("ip", ""),
                                         "port": p.get("port"), "service": p.get("service", ""),
                                         "version": p.get("version", ""), "severity": "INFO",
                                         "detail": f"port {p.get('port')}", "raw": str(p)})
            self._state.setdefault("findings", []).extend(findings)
            self._emit("recon_complete", findings=findings, count=len(findings))
            self._no_progress_count = 0
        except Exception as exc:
            self._state.setdefault("failed_steps_detail", []).append({
                "step_id": step.step_id, "tool": step.tool,
                "target": step.target, "error": str(exc),
            })
            self._emit("step_failed", step_id=step.step_id, error=str(exc))
            self._no_progress_count += 1
    else:
        self._state.setdefault("recon", []).append(
            {"tool": step.tool, "target": step.target}
        )
        self._emit("step_complete", step_id=step.step_id, output="recon queued (no engine)")
```

Also add `failed_steps_detail` injection on exploit failure — inside the `elif step.action_type == "exploit":` block, where `result.success is False`:

```python
if not result.success:
    self._state.setdefault("failed_steps_detail", []).append({
        "step_id": step.step_id, "tool": step.tool,
        "target": step.target, "error": result.error or "exploit failed",
    })
    self._emit("step_failed", ...)
```

- [ ] **Step 3: Update TUI app.py**

In `_start_goal()`, pass `recon_engine` and `output_interpreter` to `GoalEngine`:

```python
def _start_goal(self, objective: str) -> None:
    ...
    from spectrenet.ai.output_interpreter import OutputInterpreter
    output_interpreter = OutputInterpreter(model=self.model)

    self._goal_engine = GoalEngine(
        model=self.model,
        exploit_engine=exploit_engine,
        msf_bridge=self.msf_bridge,
        recon_engine=self.recon,           # NEW
        output_interpreter=output_interpreter,  # NEW
        on_event=self._on_goal_event,
    )
```

Add `recon_complete` and `replanning` event handlers in `_on_goal_event()`:

```python
elif etype == "recon_complete":
    count = event.get("count", 0)
    findings = event.get("findings", [])
    self.feed.write(f"    [{CYAN}]◈ RECON COMPLETE[/] — {count} findings")
    for f in findings[:5]:
        svc = f.get("service", "")
        ver = f.get("version", "")
        port = f.get("port", "")
        ip = f.get("ip", "")
        self.feed.write(f"      [dim]├─ {ip}:{port}  {svc} {ver}[/]")
    if count > 5:
        self.feed.write(f"      [dim]└─ ... and {count - 5} more[/]")

elif etype == "replanning":
    reason = event.get("reason", "")
    self.feed.write(f"  [yellow]◈ REPLANNING[/] — {reason}")
```

- [ ] **Step 4: Run updated goal engine tests**

```bash
python -m pytest tests/test_goal_engine.py -v
```

All tests (original 9 + 3 new = 12) pass.

- [ ] **Step 5: Commit**

```
git add spectrenet/ai/goal_engine.py spectrenet/tui/app.py tests/test_goal_engine.py
git commit -m "feat(phase4): GoalEngine executes recon, injects failure context, emits recon_complete"
```

---

## Task 7: OpenAI-Compatible Backend

**Files:**
- Create: `spectrenet/model/openai_backend.py`
- Modify: `spectrenet/config.py`
- Modify: `spectrenet/cli.py`
- Test: `tests/test_openai_backend.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_openai_backend.py
import pytest
from spectrenet.model.openai_backend import OpenAIBackend


class FakeHTTPResponse:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {
            "choices": [{"message": {"content": self._content}}]
        }


class FakeHTTPClient:
    def __init__(self, response_text: str):
        self._response_text = response_text
        self.last_request: dict = {}

    def post(self, url: str, json: dict, headers: dict, timeout: float):
        self.last_request = {"url": url, "json": json, "headers": headers}
        return FakeHTTPResponse(self._response_text)


def test_complete_returns_model_text():
    client = FakeHTTPClient("hello from model")
    backend = OpenAIBackend(
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        api_key="sk-test",
        client=client,
    )
    result = backend.complete("system prompt", "user prompt")
    assert result == "hello from model"


def test_complete_posts_to_correct_endpoint():
    client = FakeHTTPClient("ok")
    backend = OpenAIBackend(
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        api_key="sk-test",
        client=client,
    )
    backend.complete("sys", "usr")
    assert client.last_request["url"].endswith("/v1/chat/completions")


def test_complete_sends_system_and_user_messages():
    client = FakeHTTPClient("ok")
    backend = OpenAIBackend(
        model="gpt-4o",
        base_url="https://api.openai.com",
        api_key="sk-abc",
        client=client,
    )
    backend.complete("be helpful", "what is 2+2?")
    messages = client.last_request["json"]["messages"]
    roles = [m["role"] for m in messages]
    assert "system" in roles
    assert "user" in roles


def test_complete_sends_api_key_as_bearer():
    client = FakeHTTPClient("ok")
    backend = OpenAIBackend(
        model="qwen-turbo",
        base_url="https://dashscope.aliyuncs.com/compatible-mode",
        api_key="qwen-key",
        client=client,
    )
    backend.complete("sys", "usr")
    auth = client.last_request["headers"].get("Authorization", "")
    assert auth == "Bearer qwen-key"


def test_implements_model_interface():
    from spectrenet.model.base import ModelInterface
    client = FakeHTTPClient("ok")
    backend = OpenAIBackend("model", "http://localhost", "key", client=client)
    assert isinstance(backend, ModelInterface)
```

- [ ] **Step 2: Implement OpenAIBackend**

```python
# spectrenet/model/openai_backend.py
from __future__ import annotations
import json
from typing import Any
from spectrenet.model.base import ModelInterface

try:
    import httpx as _httpx
    _DEFAULT_CLIENT = _httpx
except ImportError:
    _httpx = None
    _DEFAULT_CLIENT = None


class OpenAIBackend(ModelInterface):
    def __init__(self, model: str, base_url: str, api_key: str,
                 client: Any = None, timeout: float = 120.0) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = client
        self._timeout = timeout

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self._base_url}/v1/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type":  "application/json",
        }
        client = self._client
        if client is None:
            if _httpx is None:
                raise ImportError("httpx is required for OpenAIBackend: pip install httpx")
            client = _httpx
        response = client.post(url, json=payload, headers=headers, timeout=self._timeout)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
```

- [ ] **Step 3: Update Config**

In `spectrenet/config.py`, add two new optional fields:

```python
# Add to the Config dataclass or Pydantic model:
openai_base_url: str = "https://api.openai.com"
openai_api_key:  str = ""
```

- [ ] **Step 4: Update CLI**

In `spectrenet/cli.py`, add the `openai` choice and flags:

```python
# Update choices:
parser.add_argument("--model", choices=["ollama", "openai", "none"], default=None, ...)

# Add new flags:
parser.add_argument("--openai-base-url", default=None, help="OpenAI-compatible API base URL")
parser.add_argument("--openai-api-key",  default=None, help="API key for OpenAI-compatible backend")

# In the backend init block:
elif backend == "openai":
    try:
        from spectrenet.model.openai_backend import OpenAIBackend
        base_url = args.openai_base_url or cfg.openai_base_url
        api_key  = args.openai_api_key  or cfg.openai_api_key
        model = OpenAIBackend(model=cfg.model_name, base_url=base_url, api_key=api_key)
        log.info("AI mode: OpenAI-compatible (%s @ %s)", cfg.model_name, base_url)
    except Exception as e:
        log.warning("Failed to initialise OpenAI backend: %s — running in Classic mode", e)
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_openai_backend.py -v
```

All 5 tests pass.

- [ ] **Step 6: Commit**

```
git add spectrenet/model/openai_backend.py spectrenet/config.py spectrenet/cli.py \
        tests/test_openai_backend.py
git commit -m "feat(phase4): add OpenAIBackend — any OpenAI-compatible endpoint (DeepSeek, Qwen, LM Studio)"
```

---

## Task 8: Phase 4 Suite — Full Run, README, Push

- [ ] **Step 1: Add httpx as an optional dependency**

In `pyproject.toml`, add to optional or main dependencies:

```toml
[project.optional-dependencies]
openai = ["httpx>=0.27"]
```

Or to the main `dependencies` list if always required:

```toml
"httpx>=0.27",
```

- [ ] **Step 2: Run the full test suite**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tee /tmp/phase4_tests.txt
tail -5 /tmp/phase4_tests.txt
```

Expected: all tests pass (~112 total). Fix any failures before continuing.

- [ ] **Step 3: Update README.md**

Update the Phase badge and test badge:

```markdown
![Phase](https://img.shields.io/badge/Phase-4%20Complete-00c8ff?...)
![Tests](https://img.shields.io/badge/Tests-112%20passed-4dffa3?...)
```

Update the roadmap progress bar and Phase 4 checklist:

```markdown
Phase 4 — Intelligence & Reporting  ██████████  COMPLETE  ✓
Phase 5 — Full Platform             ░░░░░░░░░░  Planned

### Phase 4 — Intelligence & Reporting ✓
- [x] OutputInterpreter — structured finding extraction from all tool output
- [x] sqlmap, nuclei, nikto wrappers + WebVulnEngine
- [x] ExploitMap — SQLite service+version → MSF module knowledge base
- [x] ReportWriter — AI-generated Markdown pentest report at mission end
- [x] GoalEngine recon execution — AI loop actually runs tools and reads results
- [x] GoalEngine failure-aware replanning — failed steps injected into AI state
- [x] OpenAI-compatible backend — DeepSeek, Qwen, LM Studio, vLLM, OpenAI

### Phase 5 — Full Platform
- Web dashboard (FastAPI + React)
- Live network map (terminal rendering)
- PostgreSQL team backend
- Tauri desktop GUI
- Fine-tuned security-domain model (LoRA on Llama 3.1)
```

Update the docs table in README.md:

```markdown
| Phase 4 design spec | `docs/superpowers/specs/2026-06-07-spectrenet-phase4-design.md` |
| Phase 4 implementation plan | `docs/superpowers/plans/2026-06-07-spectrenet-phase4-intelligence-reporting.md` |
```

- [ ] **Step 4: Commit and push**

```bash
git add -p    # stage all Phase 4 files
git commit -m "feat: Phase 4 complete — Intelligence & Reporting

- OutputInterpreter: structured findings from recon, web vuln, session output
- sqlmap, nuclei, nikto wrappers + WebVulnEngine
- ExploitMap: SQLite service+version -> MSF module knowledge base (10 seeds)
- ReportWriter: AI-generated Markdown pentest report
- GoalEngine: actual recon execution + OutputInterpreter integration
- GoalEngine: failed_steps_detail replanning context
- OpenAIBackend: any OpenAI-spec endpoint (DeepSeek, Qwen, LM Studio, vLLM)
- CLI: --model openai, --openai-base-url, --openai-api-key flags
- ~112 tests passing"

git push origin phase1-foundation
git push origin phase1-foundation:main
```

---

## Definition of Done

- [ ] `python -m pytest tests/ -v` — all ~112 tests pass, zero failures
- [ ] `OutputInterpreter.from_recon()` converts nmap dict to per-port findings without model
- [ ] `OutputInterpreter.from_session_output()` returns raw fallback when model=None
- [ ] `OutputInterpreter.from_session_output()` uses model when available and falls back on bad JSON
- [ ] `SqlmapWrapper.parse()` extracts injectable=True, payload type, databases from text
- [ ] `NucleiWrapper.parse()` extracts template_id and severity from output lines
- [ ] `NiktoWrapper.parse()` extracts OSVDB findings from nikto text output
- [ ] `WebVulnEngine.scan()` raises ValueError for unavailable tool
- [ ] `ExploitMap.find_exploits("microsoft-ds", "anything")` returns EternalBlue after seed
- [ ] `ExploitMap.find_exploits("ftp", "vsftpd 2.3.4")` returns vsftpd backdoor entry
- [ ] `ReportWriter.generate()` returns string containing "Executive Summary"
- [ ] `ReportWriter.generate()` returns string containing "CRITICAL" when critical finding present
- [ ] `GoalEngine` with `recon_engine` injected calls `ReconEngine.scan()` on recon steps
- [ ] `GoalEngine` emits `recon_complete` event with `count` field
- [ ] `GoalEngine` sets `state["failed_steps_detail"]` on exploit failure
- [ ] `OpenAIBackend.complete()` posts to `{base_url}/v1/chat/completions`
- [ ] `OpenAIBackend.complete()` sends `Authorization: Bearer <key>` header
- [ ] `OpenAIBackend` is an instance of `ModelInterface`
- [ ] `spectrenet --model openai --openai-base-url http://localhost:1234 --openai-api-key x` launches without crash
- [ ] README Phase badge = "4 Complete", tests badge ≈ 112 passed
- [ ] Both `phase1-foundation` and `main` branches pushed with Phase 4 commits

---

*SpectreNet Phase 4 — Intelligence & Reporting. Always one step ahead.*
