<div align="center">

# 👻 SPECTRENET

**Always one step ahead.**

AI-assisted offensive security framework for authorized penetration testing.

---

![Python](https://img.shields.io/badge/Python-3.11%2B-00c8ff?style=flat-square&logo=python&logoColor=white&labelColor=050d1a)
![Phase](https://img.shields.io/badge/Phase-1%20Foundation-00c8ff?style=flat-square&labelColor=050d1a)
![License](https://img.shields.io/badge/License-MIT-00c8ff?style=flat-square&labelColor=050d1a)
![Status](https://img.shields.io/badge/Status-In%20Development-ffb84d?style=flat-square&labelColor=050d1a)

</div>

---

## Overview

SpectreNet is a next-generation offensive security framework that extends the classic pentest workflow with an optional AI layer. It runs on a pentest machine, supports teams of 1–5 operators sharing sessions, and can operate fully offline.

Two modes. One engine.

| Mode | AI Active | How it works |
|---|---|---|
| **Classic** | No | Modernized msfconsole-style interface. You drive every step. |
| **AI — Autonomous** | Yes | AI plans and executes the full attack chain. |
| **AI — Approval-Gated** | Yes | AI plans; you approve every intrusive action before execution. |

The AI is a force-multiplier — not a hard dependency. Every engine, wrapper, and knowledge base is fully accessible without it.

---

## Architecture

SpectreNet is organized into six vertical layers:

```
┌─────────────────────────────────────────────────────┐
│                  Interface Layer                     │
│   TUI (Textual/Rich)  │  GUI (Tauri)  │  Web Dash   │
├─────────────────────────────────────────────────────┤
│                  Mode Selector                       │
│          Classic  │  AI Autonomous  │  AI Gated      │
├─────────────────────────────────────────────────────┤
│              AI Core  (optional)                     │
│  Mission Planner │ Step Reasoner │ Report Writer     │
├─────────────────────────────────────────────────────┤
│                  Engine Layer                        │
│   Recon  │  Web Vulns  │  Exploit  │  Post-Ex        │
├─────────────────────────────────────────────────────┤
│              Tool Wrapper Layer                      │
│  nmap │ sqlmap │ nuclei │ msfvenom │ Burp │ custom…  │
├─────────────────────────────────────────────────────┤
│           Knowledge Base  +  Storage                 │
│    CVE DB  │  Exploit Map  │  Session History        │
└─────────────────────────────────────────────────────┘
```

Every tool wrapper normalizes output to a common JSON schema. Drop a file into `wrappers/custom/` — it's autodiscovered on startup with no config changes required.

---

## Tech Stack

| Component | Technology |
|---|---|
| Core language | Python 3.11+ |
| Terminal UI | Textual + Rich |
| Desktop GUI | Tauri (Phase 3) |
| Web dashboard | FastAPI — embedded, LAN-accessible (Phase 3) |
| AI orchestration | Custom Python — direct prompt control |
| Model backend | Ollama (local, default) — swappable to any OpenAI-compatible API |
| MSF bridge | pymetasploit3 + msfrpc |
| Recon tools | nmap, masscan, shodan-cli |
| Web vulns | sqlmap, nuclei, nikto |
| Network map | NetworkX |
| Vector search | ChromaDB (embedded, zero-setup) |
| Storage | SQLite (solo) / PostgreSQL (team) |
| Packaging | PyInstaller / pipx |

---

## Build Roadmap

```
Phase 1 — Foundation          ██████░░░░  IN PROGRESS
Phase 2 — Core Attack Loop    ░░░░░░░░░░  Planned
Phase 3 — Full Intelligence   ░░░░░░░░░░  Planned
Phase 4 — Custom Model        ░░░░░░░░░░  Planned
```

### Phase 1 — Foundation *(current)*
- [x] Project skeleton, config system, logging
- [x] SpectreNet theme (dark navy + cyan)
- [ ] Convention-based wrapper autodiscovery
- [ ] nmap + masscan wrappers with normalized JSON output
- [ ] Recon engine
- [ ] Swappable model interface + Ollama backend
- [ ] SQLite session storage + audit log
- [ ] CVE knowledge base
- [ ] TUI shell (Textual) + CLI entry point (`spectrenet` / `snet`)

### Phase 2 — Core Attack Loop
- Metasploit RPC bridge (pymetasploit3)
- Native Python exploit module system
- msfvenom payload generation wrapper
- AI mission planner + step reasoner
- Approval-gated execution pipeline (blocking Y/N/S prompt)

### Phase 3 — Full Intelligence
- Web vulnerability engine (sqlmap, nuclei, nikto, Burp Suite)
- Custom fuzzer + web crawler
- Live network map (terminal + GUI rendering)
- Post-exploitation engine (sessions, pivot, loot)
- AI report writer
- Tauri desktop GUI
- PostgreSQL + FastAPI team server + web dashboard

### Phase 4 — Custom Model
- Fine-tune on session logs from Phases 1–3
- Security-domain LoRA on Llama 3.1 or equivalent
- Register custom backend via model interface
- Benchmark against Ollama baseline

---

## Installation

> **Requires Python 3.11+.** `nmap` and `masscan` must be installed separately.

```bash
# Clone
git clone https://github.com/BroJustLeaveMeAlone/SpectreNet.git
cd SpectreNet

# Install (editable, with dev tools)
pip install -e ".[dev]"

# Launch
spectrenet
# or
snet
```

### Optional: Ollama (for AI mode)

```bash
# Install Ollama — https://ollama.com
ollama pull llama3.1:70b
```

SpectreNet defaults to Ollama as its AI backend. To use a different backend, set `model_backend` in `config.yaml`.

---

## Configuration

On first run, SpectreNet uses built-in defaults. To customize, create `config.yaml` in the working directory:

```yaml
operator_name: alice           # shown in the audit log
model_backend: ollama          # ollama | openai | anthropic
model_name: llama3.1:70b
ollama_url: http://localhost:11434
storage_backend: sqlite        # sqlite | postgres
db_path: spectrenet.db
server_port: 7777              # team web dashboard port
log_level: INFO
```

---

## Adding Custom Tool Wrappers

Drop a Python file into `spectrenet/wrappers/custom/` that subclasses `ToolWrapper`:

```python
from spectrenet.wrappers.base import ToolWrapper

class ZmapWrapper(ToolWrapper):
    tool_name = "zmap"

    @property
    def schema(self):
        return {
            "hosts": [{"ip": str, "ports": [{"port": int, "service": str, "version": str}]}]
        }

    def run(self, target: str, **kwargs) -> dict:
        # invoke zmap, normalize output, return dict matching schema
        ...
```

SpectreNet autodiscovers it on the next startup. No config edits needed. If the binary isn't present on PATH, the wrapper registers as `unavailable` — shown as a warning at startup, not a crash.

---

## Approval-Gated AI Mode

When the AI plans an intrusive action, execution pauses and the operator is prompted:

```
┌─ APPROVAL REQUIRED ──────────────────────────────────┐
│  Action   : exploit/multi/handler                    │
│  Target   : 192.168.1.45:445                         │
│  Module   : ms17_010_eternalblue                     │
│  Risk     : HIGH                                     │
│  Reason   : SMB service detected, patch level < 2017 │
│                                                      │
│  [Y] Approve    [N] Deny    [S] Skip mission step    │
└──────────────────────────────────────────────────────┘
```

- **Y** — action executes, AI continues the mission plan
- **N** — action denied, AI replans from current state
- **S** — mission step skipped, AI advances to the next

Recon and passive enumeration never require approval. Classic mode has no gate — you drive every step manually.

---

## Team Usage

*(Phase 3 — PostgreSQL + FastAPI server required)*

```bash
# Lead operator — starts the embedded server on port 7777
spectrenet --mode team --session engagement-2025

# Teammates connect via their own local TUI
spectrenet --host 192.168.1.10 --session engagement-2025 --operator bob
```

Each operator is identified by their local `operator_name`. All actions are stamped with operator identity in the shared audit trail. If two operators work the same target simultaneously, a warning is shown — no hard lock, full audit.

---

## Docs

| Document | Path |
|---|---|
| Architecture spec | [`docs/superpowers/specs/2026-06-06-spectrenet-architecture-design.md`](docs/superpowers/specs/2026-06-06-spectrenet-architecture-design.md) |
| Phase 1 implementation plan | [`docs/superpowers/plans/2026-06-06-spectrenet-phase1-foundation.md`](docs/superpowers/plans/2026-06-06-spectrenet-phase1-foundation.md) |

---

## Legal

SpectreNet is designed for **authorized penetration testing, red team operations, and security research** within controlled environments.

**You are responsible for ensuring you have explicit written authorization before targeting any system.**

Using this tool against systems without authorization is illegal in most jurisdictions and is not supported by this project. The authors accept no liability for unauthorized or unlawful use.

---

<div align="center">

**SpectreNet** — Always one step ahead.

*Built for operators.*

</div>
