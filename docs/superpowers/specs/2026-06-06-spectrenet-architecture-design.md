# SpectreNet — Architecture Design Spec

**Version:** 0.2 — Resolved Architecture  
**Date:** 2026-06-06  
**Catchphrase:** Always one step ahead

---

## 1. Identity & Branding

| Property | Value |
|---|---|
| Name | SpectreNet |
| CLI command | `spectrenet` / `snet` |
| Catchphrase | "Always one step ahead" |
| Primary color | Very dark navy blue (`#050d1a` range) |
| Accent color | Cyan (`#00c8ff` range) |
| Logo | Ghost icon with circuit-line details |
| Wordmark | SPECTRE in white, NET in cyan |
| Aesthetic | Modern, high-tech, professional — dark theme with purposeful cyan accents. Reference: Warp, Raycast, Linear. Not retro terminal. |

---

## 2. Project Overview

SpectreNet is a next-generation AI-assisted offensive security framework for authorized penetration testing and red team operations. It runs as a standalone tool on a pentest machine and supports teams of 1–5 operators sharing sessions.

Two operational modes:

- **Classic Mode** — modernized msfconsole-style interface, no AI dependency. Full engine access, operator drives every step.
- **AI Mode** — AI core active, operating either autonomously or in approval-gated mode where intrusive actions require explicit operator sign-off.

Both modes share the same engine layer, knowledge base, and storage. The AI is an optional layer, not a hard dependency.

---

## 3. Design Principles

- **AI-optional** — fully functional without any AI backend
- **Swappable model backend** — one config value switches between Ollama, OpenAI-compatible API, or cloud
- **Cross-platform** — Linux, Windows, macOS; Python core with platform-agnostic subprocess wrappers
- **Team-aware** — SQLite for solo use, PostgreSQL for shared team sessions
- **Operator-in-the-loop** — in approval-gated mode, every intrusive action requires explicit confirmation
- **Audit-first** — every action logged with timestamp, operator identity, tool, parameters, output hash
- **Extensible** — wrappers, modules, and prompts are pluggable without modifying core code

---

## 4. Architecture Layers

The framework is organized into six vertical layers. Data flows top-down during a session. The AI core sits between the interface and engine layers and is bypassed entirely in Classic mode.

### 4.1 Interface Layer

| Surface | Technology | Primary Use |
|---|---|---|
| Terminal UI (TUI) | Python / Textual + Rich | Day-to-day operator use, scripting, CI pipelines |
| Desktop GUI | Tauri (cross-platform) | Guided workflows, visual network map, drag-and-drop |
| Web Dashboard | FastAPI (embedded server) | Shared session overview, multi-operator coordination |

All three surfaces apply the SpectreNet design language: dark navy background, cyan accents, clean typography, high-information-density panels.

### 4.2 Mode Selector

| Mode | AI Active | Interaction Model |
|---|---|---|
| Classic | No | Operator drives all steps manually |
| AI — Autonomous | Yes | AI plans and executes the full attack chain without approval gates |
| AI — Approval-Gated | Yes | AI plans steps; operator must approve intrusive actions before execution |

### 4.3 AI Core

Active only in AI mode. Four sub-components implement the full reasoning loop:

| Component | Responsibility |
|---|---|
| Mission Planner | Parses natural language mission input into a structured, ordered attack plan |
| Step Reasoner | Given current state (recon results, session status), decides the optimal next action |
| Output Interpreter | Parses raw tool output (nmap XML, nuclei JSON, msf console text) into structured findings |
| Report Writer | Synthesizes the full session into a structured pentest report at mission end |

The AI core communicates with the Model Interface via a single `complete(system_prompt, user_prompt)` method. No model-specific logic lives in the AI core.

### 4.4 Approval Gate (AI Approval-Gated Mode)

When the AI plans an intrusive action, execution fully pauses. The TUI renders a structured action card:

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

**Responses:**
- **Y** — action executes, result logged, AI continues mission plan
- **N** — action denied and logged, AI replans from current state
- **S** — entire mission step skipped, AI advances to next planned step

**Gate applies to:** exploit execution, payload delivery, lateral movement, persistence, any post-exploitation action.  
**Gate never applies to:** recon, passive enumeration.  
**Classic mode:** gate does not exist — operator drives every step manually.  
**Timeout:** none — the gate blocks indefinitely until the operator responds.

### 4.5 Engine Layer

| Engine | Tools / Capabilities |
|---|---|
| Recon | nmap, masscan, whatweb, shodan-cli, subdomain enumeration |
| Web Vulnerability | sqlmap, nuclei, nikto, Burp Suite integration, custom fuzzer, web crawler |
| Exploit | Metasploit RPC bridge, native Python modules, searchsploit integration, msfvenom |
| Post-Exploitation | Session management, lateral movement, loot collection, persistence |

### 4.6 Tool Wrapper Layer

Every external tool is wrapped by a structured adapter normalizing output to a common JSON schema. This enables AI reasoning over results and gives Classic mode clean, structured output.

**Wrapper autodiscovery — convention-based:**

```
wrappers/
  builtin/       ← ships with SpectreNet
    nmap.py
    sqlmap.py
    nuclei.py
    msfvenom.py
    ...
  custom/        ← drop third-party wrappers here; auto-registered on startup
```

On startup, the framework scans both directories for any Python file exporting a class implementing the `ToolWrapper` interface:

- `tool_name: str` — unique identifier
- `run(**kwargs) -> dict` — executes the tool via subprocess, returns normalized JSON
- `schema: dict` — describes the output structure

If a wrapper's tool binary is absent, it registers as `unavailable` — surfaced as a startup warning, not a crash. No config edits required to add a wrapper.

**Output schemas:**

| Wrapper | Output Schema |
|---|---|
| nmap | `{ hosts: [ { ip, ports: [ { port, service, version } ] } ] }` |
| sqlmap | `{ injectable: bool, payloads: [], databases: [] }` |
| Burp Suite | `{ issues: [ { severity, type, url, evidence } ] }` |
| Custom Fuzzer | `{ findings: [ { input, response_code, anomaly } ] }` |
| Web Crawler | `{ pages: [], forms: [], endpoints: [], js_files: [] }` |
| msfvenom | `{ payload_path, hash, delivery_method }` |

### 4.7 Knowledge Base

Always active — available in both Classic and AI modes.

| Store | Technology | Contents |
|---|---|---|
| CVE Database | SQLite / PostgreSQL | CVE IDs, CVSS scores, affected versions, patch status |
| Exploit Map | SQLite / PostgreSQL | service + version → available exploits, success rate, reliability |
| Session History | SQLite / PostgreSQL | Full action log, findings, loot, session state |
| Vector Store | ChromaDB (embedded) | Semantic search over CVE descriptions and exploit write-ups |

### 4.8 Model Interface

A thin abstraction layer. All AI core components call `complete(system_prompt, user_prompt)`. Backend configured at startup:

| Backend | When to Use |
|---|---|
| Ollama (local) | Phase 1 default — zero cost, no internet, no refusals. Recommended: Llama 3.1 70B or Mistral |
| OpenAI-compatible API | Any endpoint following the OpenAI chat completions spec — LM Studio, vLLM, custom servers |
| Cloud APIs | OpenAI, Anthropic — quality benchmark; not recommended for operational use |
| Custom trained model | Phase 4 — fine-tuned security-domain model via same interface |

### 4.9 Storage Layer

| Backend | Use Case | Setup |
|---|---|---|
| SQLite | Single operator, offline, air-gapped | Zero setup — file-based, ships with Python |
| PostgreSQL | Teams of 2–5, shared sessions, concurrent operators | Requires PostgreSQL server; configured via `config.yaml` |

### 4.10 Team Session Architecture

**Lead operator** initializes a PostgreSQL-backed session with a session name and starts the embedded FastAPI server (default port `7777`). Teammates connect by pointing their local SpectreNet TUI at `http://<lead-ip>:7777`. The web dashboard is served from this same FastAPI process.

**Authentication:** Named profiles only. Each operator's name is stored in `~/.spectrenet/config.yaml` and passed to the server on join. No passwords, no account management — the team is trusted. Operator identity is recorded in the audit log against every action.

**Conflict handling:** The session DB tracks which operator is actively working each target host. If a second operator targets a host already in use:

```
[!] WARNING: operator "bob" is currently running recon against 192.168.1.45
    Proceed anyway? [Y/N]
```

No hard lock — operator can proceed. Both actions are logged with their operator identities.

### 4.11 Output Layer

| Output | Format | Contents |
|---|---|---|
| Live Network Map | Terminal graph (NetworkX) or visual graph in GUI | Hosts, open ports, exploited nodes, lateral movement paths, session status |
| Audit Log + Report | JSON (raw) + Markdown/PDF (report) | Full action log, findings by severity, exploitation timeline, recommendations, loot inventory |

---

## 5. Build Phases

### Phase 1 — Foundation
- Project skeleton (Python monorepo, config system, logging)
- **Plugin/wrapper registration system** (convention-based autodiscovery — first task of Phase 1)
- Terminal UI shell (Textual/Rich, command parser, autocomplete, SpectreNet dark navy + cyan theme)
- Model interface abstraction + Ollama backend
- Recon engine (nmap + masscan wrappers, structured output)
- SQLite session storage
- Basic knowledge base (CVE/service map, SQLite)

### Phase 2 — Core Attack Loop
- Metasploit RPC bridge (`pymetasploit3` + `msfrpc`)
- Native Python exploit module system (no MSF dependency)
- `msfvenom` wrapper — payload generation
- AI mission planner + step reasoner
- Approval-gated execution pipeline (blocking prompt, Y/N/S)

### Phase 3 — Full Intelligence
- Web vulnerability engine (sqlmap, nuclei, nikto, Burp integration)
- Custom fuzzer and web crawler
- Live network map (NetworkX backend, terminal + GUI render)
- Post-exploitation engine (sessions, pivot, loot)
- Failure reasoning and retry logic
- AI report writer
- Desktop GUI (Tauri) — basic functional shell
- PostgreSQL support + embedded FastAPI server for team use
- Web dashboard (served from FastAPI, LAN-accessible)

### Phase 4 — Custom Model
- Fine-tuning dataset assembled from Phase 1–3 session logs
- Security-domain LoRA fine-tune on Llama 3.1 or equivalent base
- Custom model backend registered in model interface
- Evaluation against Ollama baseline on internal lab benchmarks

---

## 6. Technology Stack

| Component | Technology |
|---|---|
| Core language | Python 3.11+ |
| Terminal UI | Textual + Rich |
| Desktop GUI | Tauri (Rust + WebView) |
| Web dashboard | FastAPI (embedded, LAN server) |
| AI orchestration | Custom (Python) |
| MSF bridge | pymetasploit3 + msfrpc |
| Recon | nmap, masscan, shodan-cli |
| Web vulns | sqlmap, nuclei, nikto |
| Network map | NetworkX + rich-graph |
| Vector search | ChromaDB (embedded) |
| SQLite | Built-in (Python stdlib) |
| PostgreSQL | psycopg2 |
| Packaging | PyInstaller / pipx |

---

## 7. Operational Notes

**Intended Use:** Authorized penetration testing, red team operations, and security research within controlled environments. All operators are responsible for ensuring explicit written authorization before targeting any system.

**Air-Gap Compatibility:** Ollama runs locally. CVE database can be seeded offline. PostgreSQL can be self-hosted. No component requires cloud connectivity in production.

**Audit Trail:** Every action — operator or AI-initiated — is written to the session log with timestamp, operator identity, tool invoked, parameters, and output hash. This log is immutable during a session and is the basis for the final report.

**Training Data Generation:** Phase 1–3 session logs serve as raw training data for the Phase 4 custom model. Successful attack chains are automatically tagged for fine-tuning.

---

## 8. Resolved Design Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Plugin/wrapper registration | Convention-based autodiscovery from `wrappers/` directory |
| 2 | Approval-gate UX | Blocking prompt (Y/N/S), indefinite wait, default-deny |
| 3 | Web dashboard deployment | Embedded FastAPI server, LAN-accessible, port 7777 |
| 4 | Multi-operator conflict | Warn and allow — no hard locks |
| 5 | Team authentication | Named profiles only, implicit trust, local config |
| 6 | msfvenom phase placement | Phase 2 — ships with exploit engine for complete loop |

---

*SpectreNet — Always one step ahead*
