# SpectreNet Phase 3 — Goal-Directed AI Loop & Session Layer

**Date:** 2026-06-06
**Status:** Approved

---

## Vision

SpectreNet is a first-class offensive security framework. Metasploit is the default backend today — not a dependency. Over time, native Python capabilities replace MSF module by module (Phase 4+: ModuleCatalog). Phase 3 builds the session layer and the autonomous AI loop.

---

## Scope

Phase 3 adds:
1. `MsfConsole` — RPC console command wrapper
2. `SessionInteractor` — post-exploitation session interface
3. `GoalEngine` — autonomous goal-directed AI loop
4. `GoalPanel` — TUI widget: current goal + AI status
5. `SessionPanel` — session interaction (terminal mode + menu mode)
6. Updated `app.py` — new layout integrating all panels

**Out of scope (Phase 4):** ModuleCatalog (usage database, native-preferred module resolution).

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│                      TUI                          │
│  GoalPanel (header) │ ActivityFeed │ ai> input   │
│  SessionPanel (overlay on session select)         │
└──────────┬──────────────────┬────────────────────┘
           │                  │
  ┌────────▼────────┐  ┌──────▼──────────────┐
  │   GoalEngine    │  │  SessionInteractor   │
  │  (AI loop)      │  │  (post-ex cmds)      │
  └────────┬────────┘  └──────┬──────────────┘
           │                  │
  ┌────────▼──────────────────▼──────────────┐
  │              MsfConsole                   │
  │        (RPC console API wrapper)          │
  └────────────────┬─────────────────────────┘
                   │
  ┌────────────────▼─────────────────────────┐
  │          MsfBridge (existing)             │
  │        pymetasploit3 RPC client           │
  └──────────────────────────────────────────┘
```

**New files:**
- `spectrenet/msf/console.py`
- `spectrenet/msf/session_interactor.py`
- `spectrenet/ai/goal_engine.py`
- `spectrenet/tui/goal_panel.py`
- `spectrenet/tui/session_panel.py`

**Updated files:**
- `spectrenet/tui/app.py`

---

## Component Designs

### MsfConsole (`spectrenet/msf/console.py`)

Wraps `client.consoles.console()` from the pymetasploit3 RPC API.

```python
class MsfConsole:
    def __init__(self, client=None)   # injectable for tests
    def open() -> bool                # create console via RPC
    def send(command: str) -> str     # write command, poll until done, return output
    def close() -> None               # destroy console
```

`send()` polls `console.read()` until `busy == False`, then returns the accumulated output as a plain string. The caller handles display and parsing. An injectable `client` makes this fully unit-testable without live MSF.

---

### SessionInteractor (`spectrenet/msf/session_interactor.py`)

Wraps a single active Metasploit session. Session-type-aware: meterpreter uses `run_with_output()`; shell uses `write`/`read`.

```python
class SessionInteractor:
    def __init__(self, client, session_id: str)
    def run(command: str) -> str     # send command, return output
    def session_type() -> str        # "meterpreter" | "shell"
```

Returns output as plain text. `GoalEngine` feeds this output back into session state for the next reasoning cycle.

---

### GoalEngine (`spectrenet/ai/goal_engine.py`)

The autonomous operator. Runs as a Textual background worker.

```python
class GoalEngine:
    def __init__(self, model, exploit_engine, msf_bridge)
    def set_goal(goal: str) -> None          # set or replace goal mid-run
    async def start() -> None                # begin async loop (Textual worker)
    def stop() -> None                       # graceful stop
    def handle_input(text: str) -> None      # route operator natural-language input
```

**Loop:**

```
set_goal(goal_text)
  └─ StepReasoner.next_step(state) → PlanStep | None
       ├─ None (done)   → emit SUCCESS event, stop
       ├─ recon step    → wrappers/scan → update state
       ├─ exploit step  → requires_approval → ApprovalGate
       │    └─ approved → ExploitEngine.run_msf() → poll for session
       │         └─ session opened → SessionInteractor.run(post_ex_cmd) → output
       │              └─ update state → next_step()
       └─ dead end      → emit SUGGESTION event, pause
```

**State** is a plain dict accumulating over the session: discovered hosts, open ports, active sessions, post-ex output, failed attempts. `StepReasoner` receives the full state each turn — naturally avoids retrying failed paths.

**Dead-end detection:** after 3 consecutive steps with no new session opened and no new state information gained, `GoalEngine` emits a `GoalSuggestion` (alternative goal text) and pauses until the operator sets a new goal or resumes.

**Session polling:** after `run_msf()` dispatches a module, `GoalEngine` polls `MsfBridge.get_sessions()` every 2 seconds for up to 60 seconds. If no new session appears, the step is marked failed and counted toward dead-end detection.

**Operator input mid-run:** natural language routed from `ai>` input to `GoalEngine.handle_input(text)`:
- `"change goal to X"` → `set_goal(X)`
- `"stop"` → `stop()`
- `"skip this step"` → drop current pending step
- `"what are you doing?"` → emit explanation event to activity feed
- Any other text → injected as guidance into state for next reasoning cycle

---

### TUI Layout

```
┌──────────────────────────────────────────────────┐
│ SpectreNet v0.x              [AI: RUNNING]        │  Header
│ Goal: compromise DC at 10.0.0.5                   │  GoalPanel
├──────────────────────────────────────────────────┤
│                                                   │
│  ◈ MISSION ACTIVE ──────────────── 10:23:41      │
│                                                   │
│  ▸ RECON    nmap scan → 10.0.0.5           ⟳    │
│    ├─ 445/tcp  open  microsoft-ds                 │
│    └─ 3389/tcp open  ms-wbt-server                │  Activity Feed
│                                                   │  (RichLog)
│  ▸ EXPLOIT  ms17_010_eternalblue           ✓    │
│    └─ Session 1 opened [meterpreter/x64/windows]  │
│                                                   │
│  ┌─ POST-EX ─────────────────────────────────┐   │
│  │ getuid   →  NT AUTHORITY\SYSTEM            │   │
│  │ sysinfo  →  WIN-DC01 / Windows Server 2019 │   │
│  └────────────────────────────────────────────┘   │
│                                                   │
│  ◈ AI  "Domain controller confirmed.              │
│         Attempting credential dump..."            │
├──────────────────────────────────────────────────┤
│ ai> _                                             │  Natural language input
└──────────────────────────────────────────────────┘
```

**Color coding:**
- Recon steps → cyan
- Exploit steps → amber
- Sessions opened → green
- AI reasoning → dim italic cyan
- Errors → red
- Post-ex output → bright white
- Timestamps → dim grey

**GoalPanel** — single line below header, colour by AI state:
- `[AI: RUNNING]` → cyan
- `[AI: DEAD END]` → amber
- `[AI: SUCCESS]` → green
- `[AI: STOPPED]` → dim

**Approval cards** keep existing box-drawing style, gain risk-level border colour: HIGH = red, MED = amber, LOW = cyan.

**SessionPanel** — overlay opened when operator clicks/selects a session from the feed:
- Default: terminal mode (raw command input → `SessionInteractor.run()` → output)
- Toggle (`?` or `/menu`): menu of common post-ex actions (sysinfo, getuid, hashdump, upload, pivot)

**Input routing:**
- AI stopped → classic command parser (`scan`, `wrappers`, `help`, `quit`); `goal <text>` sets a new goal and starts the engine
- AI running → `GoalEngine.handle_input()`
- Approval pending → Y / N / S only (existing behaviour)

The Phase 2 `mission` command is superseded by the `goal` command + GoalEngine. The old `mission` handler is removed from `app.py`.

---

## Error Handling

| Condition | Behaviour |
|-----------|-----------|
| MSF disconnects mid-run | Emit `[MSF DISCONNECTED]` event, pause loop, wait for operator |
| Session dies unexpectedly | `SessionInteractor` returns error string; `GoalEngine` updates state, replans |
| AI returns unparseable output | Log error, count as failed step; dead-end after N consecutive failures |
| Operator types during approval | Intercept: only Y/N/S accepted until gate resolves |

---

## Testing

- `MsfConsole` — unit tested with injectable fake client; tests cover `send()` polling and output return
- `SessionInteractor` — unit tested with fake client; covers meterpreter and shell session types
- `GoalEngine` — unit tested with `FakeModel` (scripted step responses) and fake `MsfBridge` (instantly opens mock session); covers success, dead-end, and operator interruption paths
- TUI panels — smoke-tested (construct + compose); no interactive tests
- No integration tests requiring live `msfrpcd`

---

## Out of Scope (Phase 4)

**ModuleCatalog:** SQLite table capturing every MSF module used (path, options, target service, outcome). Two module types: `"msf"` (RPC-backed) and `"native"` (Python `ExploitModule`). Native takes precedence when available. Grows through use; native replacements added manually over time. Eventually makes MSF optional module by module.
