<div align="center">

```
                          ░░░░░░░░░░░░░
                        ░░             ░░
             ┌──○──┐  ░░   ◈       ◈   ░░  ┌──○──┐
    ─────────┤     ├─░░                 ░░─┤     ├─────────
             └──○──┘  ░░       ∧       ░░  └──○──┘
                        ░░   ╰───╯   ░░
                          ░░░░░░░░░░░░░
                          ░   ░   ░   ░
                        ░░ ░░░ ░░░ ░░░ ░░
             ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐
    ─────────┘  └──┘  └──┘  └──┘  └──┘  └──┘  └─────────
```

```
  ██████╗ ██████╗ ███████╗ ██████╗████████╗██████╗ ███████╗
 ██╔════╝ ██╔══██╗██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔════╝
 ╚██████╗ ██████╔╝█████╗  ██║        ██║   ██████╔╝█████╗  
  ╚════██╗██╔═══╝ ██╔══╝  ██║        ██║   ██╔══██╗██╔══╝  
  ██████╔╝██║     ███████╗╚██████╗   ██║   ██║  ██║███████╗
  ╚═════╝ ╚═╝     ╚══════╝ ╚═════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝
  ███╗   ██╗███████╗████████╗
  ████╗  ██║██╔════╝╚══██╔══╝
  ██╔██╗ ██║█████╗     ██║   
  ██║╚██╗██║██╔══╝     ██║   
  ██║ ╚████║███████╗   ██║   
  ╚═╝  ╚═══╝╚══════╝   ╚═╝   
```

**Always one step ahead.**

---

![Python](https://img.shields.io/badge/Python-3.11%2B-00c8ff?style=flat-square&logo=python&logoColor=white&labelColor=050d1a)
![Phase](https://img.shields.io/badge/Phase-4%20Complete-00c8ff?style=flat-square&labelColor=050d1a)
![Tests](https://img.shields.io/badge/Tests-123%20passed-4dffa3?style=flat-square&labelColor=050d1a)
![License](https://img.shields.io/badge/License-MIT-00c8ff?style=flat-square&labelColor=050d1a)
![Status](https://img.shields.io/badge/Status-In%20Development-ffb84d?style=flat-square&labelColor=050d1a)

</div>

---

## Overview

SpectreNet is a next-generation offensive security framework that extends the classic pentest workflow with an optional AI layer. It runs on a pentest machine, supports teams of 1–5 operators sharing sessions, and operates fully offline.

Two modes. One engine.

| Mode | AI Active | How it works |
|---|---|---|
| **Classic** | No | Modernized msfconsole-style interface. You drive every step. |
| **AI — Autonomous** | Yes | AI plans and executes the full attack chain. |
| **AI — Approval-Gated** | Yes | AI plans; you approve every intrusive action before execution. |

The AI is a force-multiplier — not a hard dependency. Every engine, wrapper, and knowledge base is fully accessible without it.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Interface Layer                         │
│      TUI (Textual/Rich)  │  GUI (Tauri)  │  Web Dashboard   │
├─────────────────────────────────────────────────────────────┤
│                      Mode Selector                           │
│           Classic  │  AI Autonomous  │  AI Approval-Gated   │
├─────────────────────────────────────────────────────────────┤
│                   AI Core  (optional)                        │
│     Mission Planner  │  Step Reasoner  │  Goal Engine        │
├─────────────────────────────────────────────────────────────┤
│                      Engine Layer                            │
│      Recon  │  Web Vulns  │  Exploit  │  Post-Exploitation   │
├─────────────────────────────────────────────────────────────┤
│                   Tool Wrapper Layer                         │
│    nmap │ masscan │ sqlmap │ nuclei │ msfvenom │ custom...   │
├─────────────────────────────────────────────────────────────┤
│                Knowledge Base  +  Storage                    │
│         CVE DB  │  Exploit Map  │  Session History           │
└─────────────────────────────────────────────────────────────┘
```

Every tool wrapper normalizes output to a common JSON schema. Drop a file into `wrappers/custom/` — it's autodiscovered on startup with no config changes required.

---

## Tech Stack

| Component | Technology |
|---|---|
| Core language | Python 3.11+ |
| Terminal UI | Textual + Rich |
| Desktop GUI | Tauri (Phase 4) |
| Web dashboard | FastAPI — embedded, LAN-accessible (Phase 4) |
| AI orchestration | Custom Python — direct prompt control |
| Model backend | Ollama (local, default) · any OpenAI-spec endpoint (DeepSeek, Qwen, LM Studio, vLLM) |
| MSF bridge | pymetasploit3 + msfrpc |
| Recon tools | nmap, masscan |
| Storage | SQLite (solo) / PostgreSQL (team, Phase 4) |
| Packaging | PyInstaller / pipx |

---

## Build Roadmap

```
Phase 1 — Foundation              ██████████  COMPLETE  ✓
Phase 2 — Core Attack Loop        ██████████  COMPLETE  ✓
Phase 3 — Goal-Directed AI        ██████████  COMPLETE  ✓
Phase 4 — Intelligence & Reporting ██████████  COMPLETE  ✓
Phase 5 — Full Platform           ░░░░░░░░░░  Planned
```

### Phase 1 — Foundation ✓
- [x] Project skeleton, config system, structured logging
- [x] SpectreNet theme (dark navy + cyan palette)
- [x] Convention-based wrapper autodiscovery (`wrappers/custom/` drop-in)
- [x] nmap + masscan wrappers with normalized JSON output
- [x] Recon engine orchestrating wrappers via registry
- [x] Swappable model interface + Ollama backend
- [x] SQLite session storage + immutable audit log
- [x] CVE knowledge base with service lookup
- [x] TUI shell (Textual) + CLI entry point (`spectrenet` / `snet`)

### Phase 2 — Core Attack Loop ✓
- [x] msfvenom payload generation wrapper (SHA-256 hash, normalized output)
- [x] Metasploit RPC bridge (`MsfBridge`, injectable client, graceful fallback)
- [x] Native Python exploit module system (autodiscovered from `engines/exploit_modules/`)
- [x] Exploit engine (native modules + MSF dispatch, unified result type)
- [x] AI mission planner — natural language → structured `MissionPlan` with risk tagging
- [x] AI step reasoner — session state → next `PlanStep`, intrusive steps flagged automatically
- [x] Approval-gated execution pipeline (blocking `Y` / `N` / `S` prompt per intrusive action)
- [x] Session audit extended with full approval log
- [x] TUI `mission` command + async approval gate wired end-to-end
- [x] CLI `--model` flag (Ollama / classic mode switch)

### Phase 3 — Goal-Directed AI Loop ✓
- [x] `MsfConsole` — pymetasploit3 RPC console wrapper with poll-based output
- [x] `SessionInteractor` — meterpreter / shell session command dispatch
- [x] `GoalEngine` — async autonomous goal-directed loop (plan → execute → observe → repeat)
- [x] `GoalPanel` + `SessionPanel` — live TUI widgets for goal status and session interaction
- [x] TUI redesign — real-time styled activity feed + natural-language `ai>` input

### Phase 4 — Intelligence & Reporting ✓
- [x] `OutputInterpreter` — structured finding extraction from recon, web vuln, and session output
- [x] sqlmap, nuclei, nikto wrappers + `WebVulnEngine` orchestrator
- [x] `ExploitMap` — SQLite service + version → MSF module knowledge base (10 seeded entries)
- [x] `ReportWriter` — AI-generated Markdown pentest report at mission end
- [x] `GoalEngine` recon execution — AI loop actually runs tools and reads results
- [x] `GoalEngine` failure-aware replanning — failed steps injected into AI state for next cycle
- [x] OpenAI-compatible backend — DeepSeek, Qwen, LM Studio, vLLM, or any OpenAI-spec endpoint

### Phase 5 — Full Platform
- Web dashboard (FastAPI + React)
- Live network map (terminal rendering)
- PostgreSQL team backend
- Tauri desktop GUI
- Fine-tuned security-domain model (LoRA on Llama 3.1)

---

## Requirements

SpectreNet runs without any external tools installed — the TUI and all Python logic work out of the box. External tools unlock specific capabilities as listed below.

### System

| Requirement | Version | Notes |
|---|---|---|
| **OS** | Linux, macOS, Windows | Linux recommended for full tool support |
| **Python** | 3.11+ | |
| **pip** | any recent | Comes with Python |

### Python Packages (auto-installed)

Installed automatically when you run `pip install -e .`:

| Package | Purpose |
|---|---|
| `textual` ≥ 0.50 | Terminal UI framework |
| `rich` ≥ 13.7 | Styled terminal output |
| `pyyaml` ≥ 6.0 | Config file parsing |
| `httpx` ≥ 0.27 | HTTP client for AI backends |

Optional Python package for Metasploit integration:

```bash
pip install pymetasploit3        # enables msf console mode and session management
```

### External Security Tools

All tools are **optional** — SpectreNet runs without them and shows `✗` next to unavailable tools in the status bar. Install only what you need.

| Tool | What it unlocks | Install |
|---|---|---|
| **nmap** | Network scanning, port/service/OS detection | [nmap.org/download](https://nmap.org/download.html) |
| **masscan** | High-speed port scanning across large ranges | [github.com/robertdavidgraham/masscan](https://github.com/robertdavidgraham/masscan) |
| **sqlmap** | Automated SQL injection detection and exploitation | [sqlmap.org](https://sqlmap.org) |
| **nikto** | Web server vulnerability scanning | [github.com/sullo/nikto](https://github.com/sullo/nikto) |
| **nuclei** | Template-based CVE and vulnerability scanning | [github.com/projectdiscovery/nuclei](https://github.com/projectdiscovery/nuclei) |
| **gobuster** | Directory and DNS brute-forcing | [github.com/OJ/gobuster](https://github.com/OJ/gobuster) |
| **hydra** | Login brute-force (SSH, FTP, HTTP, SMB...) | [github.com/vanhauser-thc/thc-hydra](https://github.com/vanhauser-thc/thc-hydra) |
| **msfvenom** | Payload generation (part of Metasploit) | see below |
| **Metasploit Framework** | MSF console mode, exploit modules, sessions | [metasploit.com](https://www.metasploit.com/download) |

**Quick install on Kali / Parrot / Debian:**
```bash
sudo apt install nmap masscan sqlmap nikto gobuster hydra metasploit-framework
# nuclei (Go binary — install separately)
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
```

**macOS (Homebrew):**
```bash
brew install nmap masscan sqlmap nikto gobuster hydra
brew install --cask metasploit
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
```

### AI Backend (optional)

SpectreNet's AI mode requires **one** of the following:

| Option | Cost | Setup |
|---|---|---|
| **Ollama** (local) | Free | Install from [ollama.com](https://ollama.com), then `ollama pull llama3.1:70b` |
| **DeepSeek API** | Free tier available | Sign up at [platform.deepseek.com](https://platform.deepseek.com) |
| **Qwen / other OpenAI-spec API** | Varies | Any OpenAI-compatible endpoint works |
| **LM Studio / vLLM** (local) | Free | Point SpectreNet at your local server URL |

Classic mode has **no AI requirement** — it works fully offline with just the external tools above.

### Metasploit RPC (for MSF console mode)

If Metasploit is installed, start the RPC daemon before launching SpectreNet:

```bash
msfrpcd -P msf -S false
```

SpectreNet connects automatically. If it's not running, MSF features are silently disabled — everything else still works.

---

## Installation

```bash
# Clone
git clone https://github.com/BroJustLeaveMeAlone/SpectreNet.git
cd SpectreNet

# Install
pip install -e .

# Optional: Metasploit bridge
pip install -e ".[msf]"

# Launch
spectrenet
# or
snet
```

### AI mode with Ollama

```bash
# Install Ollama — https://ollama.com
ollama pull llama3.1:70b

# Launch SpectreNet and choose AI mode from the startup screen
spectrenet
```

### AI mode with a free API (e.g. DeepSeek)

```bash
spectrenet
# Press 2 at startup → select "OpenAI-compatible"
# Enter: https://api.deepseek.com  /  deepseek-chat  /  your-api-key
```

---

## Configuration

Create `config.yaml` in the working directory to override defaults:

```yaml
operator_name: alice           # shown in the audit log
model_backend: ollama          # ollama | openai | none
model_name: llama3.1:70b
ollama_url: http://localhost:11434
openai_base_url: https://api.deepseek.com  # or http://localhost:1234 for LM Studio
openai_api_key: sk-...
storage_backend: sqlite
db_path: spectrenet.db
server_port: 7777
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

Autodiscovered on next startup. No config edits needed.

---

## Adding Native Exploit Modules

Drop a Python file into `spectrenet/engines/exploit_modules/modules/` that subclasses `ExploitModule`:

```python
from spectrenet.engines.exploit_modules.base import ExploitModule, ExploitResult

class MyExploit(ExploitModule):
    name = "my/exploit"
    description = "Example exploit module"
    target_ports = [8080]

    def check(self, host: str, port: int) -> bool:
        # return True if target appears vulnerable
        ...

    def run(self, host: str, port: int, options: dict) -> ExploitResult:
        # execute and return ExploitResult
        ...
```

Autodiscovered on next startup. No config edits needed.

---

## Approval-Gated AI Mode

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

Recon and passive enumeration never require approval.

---

## Docs

| Document | Path |
|---|---|
| Architecture spec | [`docs/superpowers/specs/2026-06-06-spectrenet-architecture-design.md`](docs/superpowers/specs/2026-06-06-spectrenet-architecture-design.md) |
| Phase 1 implementation plan | [`docs/superpowers/plans/2026-06-06-spectrenet-phase1-foundation.md`](docs/superpowers/plans/2026-06-06-spectrenet-phase1-foundation.md) |
| Phase 2 implementation plan | [`docs/superpowers/plans/2026-06-06-spectrenet-phase2-core-attack-loop.md`](docs/superpowers/plans/2026-06-06-spectrenet-phase2-core-attack-loop.md) |
| Phase 3 design spec | [`docs/superpowers/specs/2026-06-06-spectrenet-phase3-design.md`](docs/superpowers/specs/2026-06-06-spectrenet-phase3-design.md) |
| Phase 3 implementation plan | [`docs/superpowers/plans/2026-06-06-spectrenet-phase3-goal-loop.md`](docs/superpowers/plans/2026-06-06-spectrenet-phase3-goal-loop.md) |
| Phase 4 design spec | [`docs/superpowers/specs/2026-06-07-spectrenet-phase4-design.md`](docs/superpowers/specs/2026-06-07-spectrenet-phase4-design.md) |
| Phase 4 implementation plan | [`docs/superpowers/plans/2026-06-07-spectrenet-phase4-intelligence-reporting.md`](docs/superpowers/plans/2026-06-07-spectrenet-phase4-intelligence-reporting.md) |

---

## Legal

SpectreNet is designed for **authorized penetration testing, red team operations, and security research** within controlled environments.

**You are responsible for ensuring you have explicit written authorization before targeting any system.**

Using this tool against systems without authorization is illegal in most jurisdictions. The authors accept no liability for unauthorized or unlawful use.

---

<div align="center">

*Built for operators.*

</div>
