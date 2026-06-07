# SpectreNet Phase 4 — Intelligence & Reporting Design Spec

**Version:** 1.0  
**Date:** 2026-06-07  
**Status:** Approved for implementation

---

## 1. Goal

Phase 4 makes SpectreNet genuinely intelligent. The AI loop currently plans and dispatches steps but cannot read results — recon is queued, not executed; findings never enter state; the model reasons in the dark. Phase 4 closes that loop and completes the engagement lifecycle with a deliverable report.

**Six capabilities added in this phase:**

1. **OutputInterpreter** — structured parsing of tool output into findings that feed back into AI state
2. **Web Vulnerability Engine** — sqlmap, nuclei, nikto wrappers + `WebVulnEngine` orchestrator
3. **ExploitMap** — SQLite knowledge base: service + version → exploit candidates with MSF module paths
4. **ReportWriter** — AI-generated pentest report (Markdown) from session logs at mission end
5. **GoalEngine enhancements** — actual recon execution, OutputInterpreter integration, failure-aware replanning
6. **OpenAI-compatible backend** — second ModelInterface implementation covering any OpenAI-spec endpoint (DeepSeek, Qwen, LM Studio, vLLM, cloud)

---

## 2. Architecture Changes

### 2.1 Data Flow Before Phase 4

```
GoalEngine → StepReasoner → PlanStep
  recon step  → state["recon"].append({"tool": ..., "target": ...})  ← QUEUED ONLY
  exploit step → ExploitEngine.run_msf() → session?
```

The AI never sees actual findings. `StepReasoner` reasons on a state dict that says
`"recon queued"` — not hosts, ports, services, or vulnerabilities.

### 2.2 Data Flow After Phase 4

```
GoalEngine → StepReasoner → PlanStep
  recon step    → ReconEngine.scan()   → OutputInterpreter.from_recon()   → state["findings"]
  web_vuln step → WebVulnEngine.scan() → OutputInterpreter.from_web_vuln() → state["findings"]
  exploit step  → ExploitMap.find_exploits(service, version)               → options
               → ExploitEngine.run_msf(best_option, options)
               → session → SessionInteractor post-ex
               → OutputInterpreter.from_session_output()                   → state["findings"]
  failure       → GoalEngine._replan(failure_context) → StepReasoner.next_step(enriched_state)
  mission end   → ReportWriter.generate(session_store, session_id)         → report.md
```

### 2.3 GoalEngine Dependency Injection

`GoalEngine.__init__` gains two optional injections:

```python
GoalEngine(
    model,
    exploit_engine,
    msf_bridge,
    recon_engine=None,           # NEW — runs actual recon steps
    output_interpreter=None,     # NEW — parses all tool output into findings
    on_event=...,
    session_poll_timeout=60,
    auto_approve=False,
)
```

Both are optional — Classic mode and existing tests remain unaffected.

### 2.4 New Components

```
spectrenet/
  ai/
    output_interpreter.py     NEW — OutputInterpreter: structured finding extraction
    report_writer.py          NEW — ReportWriter: session log → Markdown report
  engines/
    web_vuln.py               NEW — WebVulnEngine: orchestrates web vuln wrappers
  knowledge/
    exploit_map.py            NEW — ExploitMap: service+version → exploit candidates
    exploit_map_schema.sql    NEW — schema for exploit_map table
  model/
    openai_backend.py         NEW — OpenAIBackend: any OpenAI-spec endpoint
  wrappers/builtin/
    sqlmap.py                 NEW — sqlmap wrapper
    nuclei.py                 NEW — nuclei wrapper
    nikto.py                  NEW — nikto wrapper
  config.py                   MODIFY — add openai_base_url, openai_api_key fields

tests/
  test_output_interpreter.py  NEW
  test_sqlmap_wrapper.py      NEW
  test_nuclei_wrapper.py      NEW
  test_nikto_wrapper.py       NEW
  test_web_vuln_engine.py     NEW
  test_exploit_map.py         NEW
  test_report_writer.py       NEW
  test_goal_engine.py         MODIFY — add recon + replan tests
  test_openai_backend.py      NEW
```

---

## 3. Component Specifications

### 3.1 OutputInterpreter

**Location:** `spectrenet/ai/output_interpreter.py`

**Purpose:** Single parsing entry point for all tool output. Rule-based for structured JSON
(nmap, nuclei, sqlmap). AI-assisted for unstructured text (nikto, session commands) when
a model is available; falls back to raw text capture when not.

**Interface:**

```python
class OutputInterpreter:
    def __init__(self, model: ModelInterface | None = None): ...

    def from_recon(self, recon_result: dict) -> list[dict]:
        """Convert ReconEngine normalized output to finding dicts."""

    def from_web_vuln(self, vuln_result: dict) -> list[dict]:
        """Convert WebVulnEngine output to finding dicts."""

    def from_session_output(self, command: str, output: str) -> list[dict]:
        """Parse post-ex session output. AI-assisted when model available."""
```

**Finding schema:**

```python
{
    "type": str,         # open_port | vulnerability | credential | file | process | ...
    "ip": str,           # target IP
    "port": int | None,
    "service": str,
    "version": str,
    "severity": str,     # CRITICAL | HIGH | MED | LOW | INFO
    "detail": str,       # human-readable description
    "raw": str,          # original tool output snippet
}
```

**Rule-based paths (no model required):**
- `from_recon`: maps `{hosts:[{ip, ports:[{port, service, version}]}]}` → `open_port` findings
- `from_web_vuln`: maps `{vulnerabilities:[{severity, type, url, evidence}]}` → `vulnerability` findings

**AI-assisted path:**
- `from_session_output`: calls `model.complete()` with a structured extraction prompt
  to identify credentials, privilege levels, interesting files, and processes from raw output.
  Falls back to `{"type":"post_ex","detail":output,"severity":"INFO"}` when model is None.

---

### 3.2 Web Vulnerability Wrappers

All three follow the nmap/masscan pattern: `parse(text)` for unit tests, `run(**kwargs)` for live execution.

**sqlmap** (`spectrenet/wrappers/builtin/sqlmap.py`):
```python
schema = {
    "injectable": bool,
    "payloads": list,        # list of working payload types
    "databases": list,       # discovered database names
    "tables": dict,          # db_name → [table_names]
    "dump": dict,            # table → rows (when --dump used)
}
```

**nuclei** (`spectrenet/wrappers/builtin/nuclei.py`):
```python
schema = {
    "vulnerabilities": [
        {"template_id": str, "severity": str, "type": str,
         "url": str, "matched_at": str, "evidence": str}
    ]
}
```

**nikto** (`spectrenet/wrappers/builtin/nikto.py`):
```python
schema = {
    "target": str,
    "findings": [
        {"id": str, "method": str, "url": str, "msg": str, "severity": str}
    ]
}
```

**WebVulnEngine** (`spectrenet/engines/web_vuln.py`):
- Same interface as `ReconEngine`: `scan(tool, target, **kwargs) -> dict`
- Raises `ValueError` if tool unavailable in registry
- Logs scan start/end with tool, target, finding count

---

### 3.3 ExploitMap

**Location:** `spectrenet/knowledge/exploit_map.py`

**Schema:**

```sql
CREATE TABLE exploit_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    version_pattern TEXT NOT NULL,   -- regex, e.g. "^Samba 4\.[0-6]"
    exploit_name TEXT NOT NULL,      -- human label, e.g. "EternalBlue"
    msf_module TEXT NOT NULL,        -- e.g. "exploit/windows/smb/ms17_010_eternalblue"
    platform TEXT NOT NULL,          -- windows | linux | multi
    reliability TEXT NOT NULL,       -- excellent | great | good | normal | low
    cve_id TEXT                      -- optional reference
);
```

**Interface:**

```python
class ExploitMap:
    def add_entry(service, version_pattern, exploit_name, msf_module,
                  platform, reliability, cve_id=""): ...
    def find_exploits(service: str, version: str) -> list[dict]: ...
    def seed_defaults(): ...   # pre-loads ~10 well-known mappings
```

**Default seed entries:**

| Service | Version Pattern | Exploit | MSF Module |
|---|---|---|---|
| microsoft-ds | `.*` | EternalBlue | `exploit/windows/smb/ms17_010_eternalblue` |
| microsoft-ds | `.*` | EternalRomance | `exploit/windows/smb/ms17_010_psexec` |
| ssh | `OpenSSH [1-6]\..*` | SSH Bruteforce | `auxiliary/scanner/ssh/ssh_login` |
| http | `Apache 2\.[0-3]\..*` | Shellshock | `exploit/multi/http/apache_mod_cgi_bash_env_exec` |
| ftp | `vsftpd 2\.3\.4` | Backdoor | `exploit/unix/ftp/vsftpd_234_backdoor` |
| http | `.*` | Tomcat Manager Upload | `exploit/multi/http/tomcat_mgr_upload` |
| mysql | `.*` | MySQL UDF | `exploit/linux/mysql/mysql_udf_payload` |
| postgres | `.*` | PostgreSQL COPY | `exploit/linux/postgres/postgres_copy_from_program_cmd_exec` |

---

### 3.4 ReportWriter

**Location:** `spectrenet/ai/report_writer.py`

**Purpose:** At mission end, synthesize the full session (actions, findings, sessions opened,
approvals, timeline) into a structured Markdown pentest report.

**Interface:**

```python
class ReportWriter:
    def __init__(self, model: ModelInterface): ...
    def generate(self, session_store: SessionStore, session_id: int,
                 findings: list[dict] | None = None) -> str: ...
```

**Report structure (Markdown output):**

```markdown
# SpectreNet Engagement Report
## Executive Summary
## Scope & Methodology
## Findings
### Critical / High / Medium / Low
## Exploitation Timeline
## Session Evidence
## Recommendations
## Appendix — Full Action Log
```

**Implementation approach:**
- Pulls actions + approvals from `SessionStore` for the session
- Merges with `findings` list (from GoalEngine state)
- Groups findings by severity
- Calls `model.complete()` three times:
  1. Executive summary + methodology (from scope + finding counts)
  2. Recommendations (from finding types + exploitation outcome)
  3. Formats timeline from raw action log data (deterministic, no model needed)
- Falls back gracefully if model returns malformed output

---

### 3.5 GoalEngine Enhancements

Two changes to `spectrenet/ai/goal_engine.py`:

**A — Actual recon execution:**

```python
# Before (Phase 3):
if step.action_type == "recon":
    self._state.setdefault("recon", []).append({"tool": ..., "target": ...})
    self._emit("step_complete", ...)

# After (Phase 4):
if step.action_type == "recon" and self._recon_engine:
    result = self._recon_engine.scan(tool=step.tool, target=step.target, **step.params)
    findings = self._interpreter.from_recon(result) if self._interpreter else []
    self._state.setdefault("findings", []).extend(findings)
    self._emit("recon_complete", findings=findings, count=len(findings))
```

**B — Failure-aware replanning:**

```python
async def _replan(self, failed_step, error: str) -> None:
    """Ask StepReasoner to replan with failure context injected into state."""
    self._state.setdefault("failed_steps_detail", []).append({
        "step_id": failed_step.step_id,
        "tool": failed_step.tool,
        "target": failed_step.target,
        "error": error,
    })
    self._emit("replanning", reason=error)
```

The replanning is implicit: `StepReasoner.next_step(state)` now receives a state dict that
includes `failed_steps_detail`. The next call to the reasoner will naturally avoid the same
approach. No extra model call needed.

---

### 3.6 OpenAI-Compatible Backend

**Location:** `spectrenet/model/openai_backend.py`

**Covers:** OpenAI, DeepSeek, Qwen, Mistral API, LM Studio, vLLM, any server implementing
`POST /v1/chat/completions` with the standard request/response schema.

**Config fields added:**

```yaml
# config.yaml additions
openai_base_url: https://api.deepseek.com    # or http://localhost:1234 for LM Studio
openai_api_key: sk-...
```

**Interface:**

```python
class OpenAIBackend(ModelInterface):
    def __init__(self, model: str, base_url: str, api_key: str,
                 client=None, timeout: float = 120.0): ...
    def complete(self, system_prompt: str, user_prompt: str) -> str: ...
```

**CLI flag:** `--model openai` added alongside existing `--model ollama`.

---

## 4. Definition of Done

- [ ] `python -m pytest tests/ -v` — all tests pass (~112 total)
- [ ] `OutputInterpreter.from_recon()` converts nmap output to finding list without model
- [ ] `OutputInterpreter.from_session_output()` returns raw fallback when model=None
- [ ] `WebVulnEngine.scan()` raises `ValueError` for unavailable tool
- [ ] `ExploitMap.find_exploits("microsoft-ds", "Samba 4.6")` returns EternalBlue entry after seed
- [ ] `ReportWriter.generate()` returns Markdown string containing "Executive Summary"
- [ ] `GoalEngine` with `recon_engine` injected actually calls `ReconEngine.scan()` on recon steps
- [ ] `GoalEngine` injects `failed_steps_detail` into state on exploit failure
- [ ] `OpenAIBackend.complete()` passes correct `base_url`, messages structure; tested with injected client
- [ ] `spectrenet --model openai` launches without error (bridge unavailable is a warning, not crash)

---

## 5. Post-Phase-4 State

After Phase 4, one full engagement loop works end-to-end:

```
goal <objective>
  → StepReasoner plans recon
  → ReconEngine scans → OutputInterpreter → findings in state
  → StepReasoner plans exploit based on real findings
  → ExploitMap suggests MSF module for discovered service
  → ExploitEngine dispatches → approval gate → session
  → SessionInteractor post-ex → OutputInterpreter parses output
  → mission complete → ReportWriter generates report.md
```

What remains for Phase 5: PostgreSQL team backend, FastAPI server, web dashboard,
live network map, desktop GUI, and custom fine-tuned model.

---

*SpectreNet Phase 4 — Intelligence & Reporting. Always one step ahead.*
