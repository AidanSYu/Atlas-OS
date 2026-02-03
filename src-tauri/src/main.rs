// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command as StdCommand};
use std::sync::Mutex;
use std::time::Duration;
use tauri::api::process::{Command, CommandChild, CommandEvent};
use tauri::{Manager, State};

#[cfg(windows)]
const PG_EXE: &str = "postgres.exe";
#[cfg(windows)]
const INITDB_EXE: &str = "initdb.exe";
#[cfg(windows)]
const PSQL_EXE: &str = "psql.exe";
#[cfg(windows)]
const QDRANT_EXE: &str = "qdrant.exe";
#[cfg(not(windows))]
const PG_EXE: &str = "postgres";
#[cfg(not(windows))]
const INITDB_EXE: &str = "initdb";
#[cfg(not(windows))]
const PSQL_EXE: &str = "psql";
#[cfg(not(windows))]
const QDRANT_EXE: &str = "qdrant";

/// State to track running sidecar and resource processes
struct SidecarState {
    backend: Mutex<Option<CommandChild>>,
    postgres: Mutex<Option<Child>>,
    qdrant: Mutex<Option<Child>>,
}

/// Launch the Python backend sidecar
#[tauri::command]
async fn start_backend(state: State<'_, SidecarState>) -> Result<String, String> {
    let mut rx = {
        let mut backend_guard = state.backend.lock().map_err(|e| e.to_string())?;
        if backend_guard.is_some() {
            return Ok("Backend already running".to_string());
        }
        let (rx, child) = Command::new_sidecar("atlas-backend")
            .map_err(|e| format!("Failed to create sidecar command: {}", e))?
            .spawn()
            .map_err(|e| format!("Failed to spawn backend: {}", e))?;
        *backend_guard = Some(child);
        rx
    };

    // Log backend output
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => log::info!("[Backend] {}", line),
                CommandEvent::Stderr(line) => log::error!("[Backend] {}", line),
                CommandEvent::Error(err) => log::error!("[Backend Error] {}", err),
                CommandEvent::Terminated(payload) => {
                    log::info!("[Backend] Terminated with code: {:?}", payload.code);
                    break;
                }
                _ => {}
            }
        }
    });

    // Wait for backend to be ready (simple health check)
    for _ in 0..30 {
        tokio::time::sleep(std::time::Duration::from_secs(1)).await;
        if check_backend_health().await {
            return Ok("Backend started successfully".to_string());
        }
    }

    Err("Backend failed to start within timeout".to_string())
}

/// Stop the backend sidecar
#[tauri::command]
async fn stop_backend(state: State<'_, SidecarState>) -> Result<String, String> {
    let mut backend_guard = state.backend.lock().map_err(|e| e.to_string())?;
    
    if let Some(child) = backend_guard.take() {
        child.kill().map_err(|e| format!("Failed to kill backend: {}", e))?;
        Ok("Backend stopped".to_string())
    } else {
        Ok("Backend was not running".to_string())
    }
}

/// Wait for a TCP port to become reachable (returns true) or timeout (returns false).
async fn wait_for_port(host: &str, port: u16, timeout_secs: u64) -> bool {
    let addr = format!("{}:{}", host, port);
    for _ in 0..timeout_secs {
        if tokio::net::TcpStream::connect(&addr).await.is_ok() {
            return true;
        }
        tokio::time::sleep(Duration::from_secs(1)).await;
    }
    false
}

/// Start PostgreSQL from bundled resources (if present). Creates DB cluster on first run.
#[tauri::command]
async fn start_postgres(app: tauri::AppHandle, state: State<'_, SidecarState>) -> Result<String, String> {
    {
        let guard = state.postgres.lock().map_err(|e| e.to_string())?;
        if guard.is_some() {
            return Ok("PostgreSQL already running".to_string());
        }
    }

    let resource_dir = app.path_resolver().resource_dir()
        .ok_or_else(|| "Resource dir not found (not bundled?)".to_string())?;
    let app_data = app.path_resolver().app_data_dir()
        .ok_or_else(|| "App data dir not found".to_string())?;

    let postgres_bin_dir = resource_dir.join("postgres").join("bin");
    let postgres_exe = postgres_bin_dir.join(PG_EXE);
    let initdb_exe = postgres_bin_dir.join(INITDB_EXE);
    let psql_exe = postgres_bin_dir.join(PSQL_EXE);

    if !postgres_exe.exists() {
        return Err(format!(
            "PostgreSQL binary not found at {:?}. Run the download script (see src-tauri/resources/README.md).",
            postgres_exe
        ));
    }

    std::fs::create_dir_all(&app_data).map_err(|e| e.to_string())?;
    let pg_data = app_data.join("postgres_data");

    // First run: initdb
    if !pg_data.join("PG_VERSION").exists() {
        if !initdb_exe.exists() {
            return Err(format!("initdb not found at {:?}", initdb_exe));
        }
        log::info!("Initializing PostgreSQL data at {:?}", pg_data);
        let status = StdCommand::new(&initdb_exe)
            .current_dir(&postgres_bin_dir)
            .args(["-D", pg_data.to_str().unwrap(), "-U", "postgres"])
            .env("PATH", postgres_bin_dir.to_str().unwrap_or(""))
            .status()
            .map_err(|e| format!("initdb failed: {}", e))?;
        if !status.success() {
            return Err("initdb failed".to_string());
        }
    }

    // Start postgres (-k . for Unix socket dir; Windows uses TCP only)
    let mut args: Vec<String> = vec![
        "-D".into(), pg_data.to_string_lossy().into_owned(),
        "-p".into(), "5432".into(),
    ];
    #[cfg(not(windows))]
    args.extend(["-k".into(), ".".into()]);
    let path_env = {
        let path = std::env::var("PATH").unwrap_or_default();
        #[cfg(windows)]
        let path = {
            let lib_dir = resource_dir.join("postgres").join("lib");
            if lib_dir.exists() {
                format!("{};{}", lib_dir.to_string_lossy(), path)
            } else {
                format!("{};{}", postgres_bin_dir.to_string_lossy(), path)
            }
        };
        #[cfg(not(windows))]
        let path = format!("{}:{}", postgres_bin_dir.to_string_lossy(), path);
        path
    };
    let mut child = StdCommand::new(&postgres_exe)
        .current_dir(&postgres_bin_dir)
        .args(&args)
        .env("PATH", path_env)
        .spawn()
        .map_err(|e| format!("Failed to start postgres: {}", e))?;

    // Wait for port 5432
    if !wait_for_port("127.0.0.1", 5432, 15).await {
        let _ = child.kill();
        return Err("PostgreSQL did not become ready in time".to_string());
    }

    // Bootstrap: create user and database (idempotent: ignore errors if exist)
    if psql_exe.exists() {
        let _ = StdCommand::new(&psql_exe)
            .current_dir(&postgres_bin_dir)
            .args(["-U", "postgres", "-p", "5432", "-h", "127.0.0.1", "-t", "-c",
                   "SELECT 1 FROM pg_roles WHERE rolname='atlas'"])
            .env("PGPASSWORD", "")
            .env("PATH", postgres_bin_dir.to_str().unwrap_or(""))
            .output();
        let create_user = StdCommand::new(&psql_exe)
            .current_dir(&postgres_bin_dir)
            .args(["-U", "postgres", "-p", "5432", "-h", "127.0.0.1", "-t", "-c",
                   "CREATE USER atlas WITH PASSWORD 'atlas_secure_password';"])
            .env("PGPASSWORD", "")
            .env("PATH", postgres_bin_dir.to_str().unwrap_or(""))
            .output();
        let _ = create_user;
        let create_db = StdCommand::new(&psql_exe)
            .current_dir(&postgres_bin_dir)
            .args(["-U", "postgres", "-p", "5432", "-h", "127.0.0.1", "-t", "-c",
                   "CREATE DATABASE atlas_knowledge OWNER atlas;"])
            .env("PGPASSWORD", "")
            .env("PATH", postgres_bin_dir.to_str().unwrap_or(""))
            .output();
        let _ = create_db;
    }

    let mut guard = state.postgres.lock().map_err(|e| e.to_string())?;
    *guard = Some(child);
    Ok("PostgreSQL started".to_string())
}

/// Stop PostgreSQL
#[tauri::command]
async fn stop_postgres(state: State<'_, SidecarState>) -> Result<String, String> {
    let mut guard = state.postgres.lock().map_err(|e| e.to_string())?;
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
        Ok("PostgreSQL stopped".to_string())
    } else {
        Ok("PostgreSQL was not running".to_string())
    }
}

/// Start Qdrant from bundled resources (if present).
#[tauri::command]
async fn start_qdrant(app: tauri::AppHandle, state: State<'_, SidecarState>) -> Result<String, String> {
    let mut guard = state.qdrant.lock().map_err(|e| e.to_string())?;
    if guard.is_some() {
        return Ok("Qdrant already running".to_string());
    }

    let resource_dir = app.path_resolver().resource_dir()
        .ok_or_else(|| "Resource dir not found (not bundled?)".to_string())?;
    let app_data = app.path_resolver().app_data_dir()
        .ok_or_else(|| "App data dir not found".to_string())?;

    let qdrant_exe = resource_dir.join("qdrant").join(QDRANT_EXE);
    if !qdrant_exe.exists() {
        return Err(format!(
            "Qdrant binary not found at {:?}. Run the download script (see src-tauri/resources/README.md).",
            qdrant_exe
        ));
    }

    let qdrant_data = app_data.join("qdrant_data");
    std::fs::create_dir_all(&qdrant_data).map_err(|e| e.to_string())?;

    let qdrant_dir = qdrant_exe.parent().unwrap_or(&resource_dir);
    let child = StdCommand::new(&qdrant_exe)
        .current_dir(qdrant_dir)
        .args([
            "run",
            "--storage-path", qdrant_data.to_str().unwrap(),
            "--port", "6333",
        ])
        .spawn()
        .map_err(|e| format!("Failed to start Qdrant: {}", e))?;

    *guard = Some(child);
    Ok("Qdrant started".to_string())
}

/// Stop Qdrant
#[tauri::command]
async fn stop_qdrant(state: State<'_, SidecarState>) -> Result<String, String> {
    let mut guard = state.qdrant.lock().map_err(|e| e.to_string())?;
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
        Ok("Qdrant stopped".to_string())
    } else {
        Ok("Qdrant was not running".to_string())
    }
}

/// Check if backend is healthy
#[tauri::command]
async fn check_health() -> Result<bool, String> {
    Ok(check_backend_health().await)
}

/// Get app data directory path
#[tauri::command]
fn get_app_data_dir(app: tauri::AppHandle) -> Result<String, String> {
    app.path_resolver()
        .app_data_dir()
        .map(|p| p.to_string_lossy().to_string())
        .ok_or_else(|| "Failed to get app data directory".to_string())
}

/// Check if this is the first run
#[tauri::command]
fn is_first_run(app: tauri::AppHandle) -> Result<bool, String> {
    let data_dir = app.path_resolver()
        .app_data_dir()
        .ok_or_else(|| "Failed to get app data directory".to_string())?;
    
    let setup_marker = data_dir.join(".setup_complete");
    Ok(!setup_marker.exists())
}

/// Mark setup as complete
#[tauri::command]
fn mark_setup_complete(app: tauri::AppHandle) -> Result<(), String> {
    let data_dir = app.path_resolver()
        .app_data_dir()
        .ok_or_else(|| "Failed to get app data directory".to_string())?;
    
    std::fs::create_dir_all(&data_dir)
        .map_err(|e| format!("Failed to create app data directory: {}", e))?;
    
    let setup_marker = data_dir.join(".setup_complete");
    std::fs::write(&setup_marker, "1")
        .map_err(|e| format!("Failed to write setup marker: {}", e))?;
    
    Ok(())
}

/// Helper function to check backend health
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
            postgres: Mutex::new(None),
            qdrant: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            start_backend,
            stop_backend,
            start_postgres,
            stop_postgres,
            start_qdrant,
            stop_qdrant,
            check_health,
            get_app_data_dir,
            is_first_run,
            mark_setup_complete,
        ])
        .setup(|app| {
            let _window = app.get_window("main").unwrap();
            
            // Log app info
            log::info!("Atlas Desktop App starting...");
            if let Some(data_dir) = app.path_resolver().app_data_dir() {
                log::info!("App data directory: {:?}", data_dir);
            }
            
            // Auto-start services in order: Postgres -> Qdrant -> Backend (skip if binaries missing)
            let app_handle = app.handle();
            tauri::async_runtime::spawn(async move {
                tokio::time::sleep(std::time::Duration::from_secs(2)).await;

                // 1. Start bundled PostgreSQL if present
                if let Some(res_dir) = app_handle.path_resolver().resource_dir() {
                    let pg_exe = res_dir.join("postgres").join("bin").join(PG_EXE);
                    if pg_exe.exists() {
                        match start_postgres(app_handle.clone(), app_handle.state::<SidecarState>()).await {
                            Ok(msg) => log::info!("{}", msg),
                            Err(e) => log::warn!("PostgreSQL: {}", e),
                        }
                        tokio::time::sleep(std::time::Duration::from_secs(2)).await;
                    }
                }

                // 2. Start bundled Qdrant if present
                if let Some(res_dir) = app_handle.path_resolver().resource_dir() {
                    let qdrant_exe = res_dir.join("qdrant").join(QDRANT_EXE);
                    if qdrant_exe.exists() {
                        match start_qdrant(app_handle.clone(), app_handle.state::<SidecarState>()).await {
                            Ok(msg) => log::info!("{}", msg),
                            Err(e) => log::warn!("Qdrant: {}", e),
                        }
                        tokio::time::sleep(std::time::Duration::from_secs(2)).await;
                    }
                }

                // 3. Start backend sidecar
                match start_backend(app_handle.state::<SidecarState>()).await {
                    Ok(msg) => log::info!("{}", msg),
                    Err(e) => log::error!("Failed to start backend: {}", e),
                }
            });
            
            Ok(())
        })
        .on_window_event(|event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event.event() {
                log::info!("Window close requested, shutting down services...");
                let app = event.window().app_handle();
                let state = app.state::<SidecarState>();
                // Stop backend
                if let Ok(mut g) = state.backend.lock() {
                    if let Some(child) = g.take() {
                        let _ = child.kill();
                    }
                };
                // Stop Qdrant then Postgres
                if let Ok(mut g) = state.qdrant.lock() {
                    if let Some(mut child) = g.take() {
                        let _ = child.kill();
                    }
                };
                if let Ok(mut g) = state.postgres.lock() {
                    if let Some(mut child) = g.take() {
                        let _ = child.kill();
                    }
                };
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
