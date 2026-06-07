# SpectreNet Desktop GUI

Tauri 2 desktop application wrapping the SpectreNet team server dashboard.

## Prerequisites

- Rust + Cargo (stable)  →  https://rustup.rs
- Tauri CLI 2            →  `cargo install tauri-cli --version "^2"`
- SpectreNet team server →  `python -m spectrenet.server.app` (runs on port 8888)

## Development

```bash
# Start the team server first
python -m spectrenet.server.app

# Then run the Tauri dev build (hot-reload)
cd gui
cargo tauri dev
```

## Production build

```bash
cd gui
cargo tauri build
```

Outputs are in `gui/src-tauri/target/release/bundle/`.

## Architecture

```
gui/
├── src/
│   └── index.html      ← Frontend (vanilla JS, no bundler needed)
└── src-tauri/
    ├── src/main.rs     ← Tauri Rust backend + IPC commands
    ├── Cargo.toml
    ├── build.rs
    └── tauri.conf.json
```

The GUI talks to the team server via Tauri's `invoke()` IPC bridge
(`api_get` / `api_post` / `server_ping` commands defined in `main.rs`).
Real-time updates arrive via SSE from `http://localhost:8888/api/events`.
