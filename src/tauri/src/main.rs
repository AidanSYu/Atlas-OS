// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command as StdCommand, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Manager, State};

#[cfg(windows)]
const ATLAS_BACKEND_EXE: &str = "atlas-backend.exe";
#[cfg(not(windows))]
const ATLAS_BACKEND_EXE: &str = "atlas-backend";

/// State to track the running backend sidecar process.
/// PostgreSQL and Qdrant are no longer external - they run embedded
/// inside the Python process (SQLite + Qdrant path mode).
struct SidecarState {
    backend: Mutex<Option<Child>>,
}

/// Launch the Python backend from resources (onedir bundle).
#[tauri::command]
async fn start_backend(app: AppHandle, state: State<'_, SidecarState>) -> Result<String, String> {
    if check_backend_health().await {
        return Ok("Backend already running (external)".to_string());
    }

    // Scope the MutexGuard so it is dropped before any .await
    {
        let mut backend_guard = state.backend.lock().map_err(|e| e.to_string())?;
        if backend_guard.is_some() {
            return Ok("Backend already running".to_string());
        }

        let resource_dir = app
            .path_resolver()
            .resource_dir()
            .ok_or_else(|| "Resource dir not found (not bundled?)".to_string())?;
        let backend_dir = resource_dir.join("atlas-backend");
        let backend_exe = backend_dir.join(ATLAS_BACKEND_EXE);

        if !backend_exe.exists() {
            return Err(format!(
                "Backend executable not found at {:?}. Run build-backend.ps1 to build.",
                backend_exe
            ));
        }

        let mut cmd = StdCommand::new(&backend_exe);
        cmd.env("PYTHONDONTWRITEBYTECODE", "1");
        if let Some(cache_dir) = app.path_resolver().app_cache_dir() {
            let _ = std::fs::create_dir_all(&cache_dir);
            cmd.env("PYTHONPYCACHEPREFIX", cache_dir);
        }

        let child = cmd
            .current_dir(&backend_dir)
            .stdout(Stdio::inherit())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("Failed to spawn backend: {}", e))?;

        *backend_guard = Some(child);
    } // MutexGuard dropped here

    // Wait for backend to be ready
    for _ in 0..30 {
        tokio::time::sleep(std::time::Duration::from_secs(1)).await;
        if check_backend_health().await {
            return Ok("Backend started successfully".to_string());
        }
    }

    Err("Backend failed to start within timeout".to_string())
}

/// Stop the backend process.
#[tauri::command]
async fn stop_backend(state: State<'_, SidecarState>) -> Result<String, String> {
    let mut backend_guard = state.backend.lock().map_err(|e| e.to_string())?;
    if let Some(mut child) = backend_guard.take() {
        child
            .kill()
            .map_err(|e| format!("Failed to kill backend: {}", e))?;
        Ok("Backend stopped".to_string())
    } else {
        Ok("Backend was not running".to_string())
    }
}

/// Check if backend is healthy.
#[tauri::command]
async fn check_health() -> Result<bool, String> {
    Ok(check_backend_health().await)
}

/// Get app data directory path.
#[tauri::command]
fn get_app_data_dir(app: tauri::AppHandle) -> Result<String, String> {
    app.path_resolver()
        .app_data_dir()
        .map(|p| p.to_string_lossy().to_string())
        .ok_or_else(|| "Failed to get app data directory".to_string())
}

/// Helper function to check backend health.
async fn check_backend_health() -> bool {
    match reqwest::get("http://127.0.0.1:8000/health").await {
        Ok(response) => response.status().is_success(),
        Err(_) => false,
    }
}

fn main() {
    env_logger::init();

    tauri::Builder::default()
        .manage(SidecarState {
            backend: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            start_backend,
            stop_backend,
            check_health,
            get_app_data_dir,
        ])
        .setup(|app| {
            let _window = app.get_window("main").unwrap();

            log::info!("Atlas Desktop App starting (embedded DB mode)...");
            if let Some(data_dir) = app.path_resolver().app_data_dir() {
                log::info!("App data directory: {:?}", data_dir);
            }

            let app_handle = app.handle();
            tauri::async_runtime::spawn(async move {
                #[cfg(debug_assertions)]
                {
                    // Dev mode: never launch sidecar — wait for `python run_server.py` instead.
                    log::info!("Dev mode: waiting for external Python backend on http://127.0.0.1:8000");
                    log::info!("Run: .\\scripts\\dev\\run_backend.ps1");
                    let mut ready = false;
                    for i in 1..=60 {
                        tokio::time::sleep(std::time::Duration::from_secs(1)).await;
                        if check_backend_health().await {
                            log::info!("Backend ready after {}s", i);
                            ready = true;
                            break;
                        }
                        if i % 10 == 0 {
                            log::warn!("Still waiting for backend... ({}s elapsed)", i);
                        }
                    }
                    if !ready {
                        log::error!("Backend not found after 60s. Start it with: .\\scripts\\dev\\run_backend.ps1");
                    }
                    let _ = app_handle; // suppress unused warning
                }
                #[cfg(not(debug_assertions))]
                {
                    // Release mode: auto-launch the bundled sidecar.
                    tokio::time::sleep(std::time::Duration::from_secs(1)).await;
                    match start_backend(app_handle.clone(), app_handle.state::<SidecarState>()).await {
                        Ok(msg) => log::info!("{}", msg),
                        Err(e) => log::error!("Failed to start backend: {}", e),
                    }
                }
            });

            Ok(())
        })
        .on_window_event(|event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event.event() {
                log::info!("Window close requested, shutting down backend...");
                let app = event.window().app_handle();
                let state = app.state::<SidecarState>();
                if let Ok(mut g) = state.backend.lock() {
                    if let Some(mut child) = g.take() {
                        let _ = child.kill();
                    }
                };
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
