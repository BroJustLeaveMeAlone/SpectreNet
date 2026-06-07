// SpectreNet Desktop App — Tauri 2 backend
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;

/// Proxy GET request to the SpectreNet team server (avoids CORS in prod builds).
#[tauri::command]
async fn api_get(path: String) -> Result<String, String> {
    let url = format!("http://localhost:8888{}", path);
    let resp = reqwest::get(&url)
        .await
        .map_err(|e| e.to_string())?
        .text()
        .await
        .map_err(|e| e.to_string())?;
    Ok(resp)
}

/// Proxy POST request to the SpectreNet team server.
#[tauri::command]
async fn api_post(path: String, body: String) -> Result<String, String> {
    let url    = format!("http://localhost:8888{}", path);
    let client = reqwest::Client::new();
    let resp   = client
        .post(&url)
        .header("Content-Type", "application/json")
        .body(body)
        .send()
        .await
        .map_err(|e| e.to_string())?
        .text()
        .await
        .map_err(|e| e.to_string())?;
    Ok(resp)
}

/// Check if the team server is reachable.
#[tauri::command]
async fn server_ping() -> bool {
    reqwest::get("http://localhost:8888/api/sessions")
        .await
        .map(|r| r.status().is_success())
        .unwrap_or(false)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_http::init())
        .invoke_handler(tauri::generate_handler![api_get, api_post, server_ping])
        .setup(|app| {
            let window = app.get_webview_window("main").expect("main window");
            #[cfg(debug_assertions)]
            window.open_devtools();
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running SpectreNet");
}

fn main() {
    run()
}
