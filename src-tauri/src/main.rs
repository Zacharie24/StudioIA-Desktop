// StudioIA — Shell Tauri 2
// ----------------------------------------------------------------------------
// Fenêtre native + tray. Au lancement :
//   1. démarre le backend FastAPI (runtime\python\python.exe -m uvicorn ... :8080)
//      en processus enfant invisible (aucune console),
//   2. affiche un splash local pendant que le backend démarre,
//   3. dès que /api/system/stats répond 200, la fenêtre navigue vers
//      http://127.0.0.1:8080 (le dashboard StudioIA),
//   4. à la fermeture : tue proprement l'arbre du backend.
//
// Dev :  cargo run   (dans src-tauri/)
// Prod : l'installeur place le .exe à la racine de l'application ; la racine
//        de l'app est résolue en remontant vers le dossier contenant web/main.py
//        (ou via la variable d'environnement STUDIOIA_APP_ROOT).

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, RunEvent, WebviewUrl, WebviewWindowBuilder, WindowEvent,
};
use tauri_plugin_updater::UpdaterExt;

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: u16 = 8080;
const HEALTH_PATH: &str = "/api/system/stats";
// CREATE_NO_WINDOW = 0x08000000 : pas de console pour le backend.
const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const STARTUP_TIMEOUT: Duration = Duration::from_secs(120);
// Dossier des données utilisateur par défaut (isolé du dossier d'app) :
// %USERPROFILE%\StudioIA. Surchargé par la variable STUDIOIA_DATA_DIR.
const DEFAULT_DATA_DIR_NAME: &str = "StudioIA";

// ---------------------------------------------------------------------------
// Résolution de la racine de l'application
// ---------------------------------------------------------------------------
fn app_root() -> PathBuf {
    if let Ok(p) = std::env::var("STUDIOIA_APP_ROOT") {
        let p = PathBuf::from(p);
        if p.join("web").join("main.py").exists() {
            return p;
        }
    }
    if let Ok(exe) = std::env::current_exe() {
        let mut dir = exe.parent().map(|p| p.to_path_buf()).unwrap_or_default();
        for _ in 0..6 {
            if dir.join("web").join("main.py").exists() {
                return dir;
            }
            if !dir.pop() {
                break;
            }
        }
        return dir;
    }
    std::env::current_dir().unwrap_or_default()
}

// ---------------------------------------------------------------------------
// Backend : spawn + santé
// ---------------------------------------------------------------------------
fn spawn_backend(root: &PathBuf) -> Option<Child> {
    let python = root.join("runtime").join("python").join("python.exe");
    if !python.exists() {
        eprintln!("[shell] python runtime introuvable : {}", python.display());
        return None;
    }
    // Définir STUDIOIA_DATA_DIR pour isoler les données utilisateur hors du
    // dossier d'app (sauf si déjà défini par l'installateur ou l'utilisateur).
    // Le backend (child) hérite de l'environnement : core/paths.py le lira.
    let mut cmd = Command::new(python);
    if std::env::var_os("STUDIOIA_DATA_DIR").is_none() {
        if let Ok(profile) = std::env::var("USERPROFILE") {
            cmd.env(
                "STUDIOIA_DATA_DIR",
                PathBuf::from(profile).join(DEFAULT_DATA_DIR_NAME),
            );
        }
    }
    cmd
        .args([
            "-m",
            "uvicorn",
            "web.main:app",
            "--host",
            BACKEND_HOST,
            "--port",
            &BACKEND_PORT.to_string(),
            "--log-level",
            "warning",
        ])
        .current_dir(root)
        .creation_flags(CREATE_NO_WINDOW)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .ok()
}

/// Vrai si /api/system/stats répond HTTP 200.
fn backend_ready() -> bool {
    let addr = format!("{BACKEND_HOST}:{BACKEND_PORT}");
    let Ok(mut stream) = TcpStream::connect_timeout(
        &addr.parse().unwrap(),
        Duration::from_millis(400),
    ) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(1500)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));
    let req = format!(
        "GET {HEALTH_PATH} HTTP/1.1\r\nHost: {BACKEND_HOST}\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }
    let mut buf = [0u8; 64];
    match stream.read(&mut buf) {
        Ok(n) => String::from_utf8_lossy(&buf[..n]).starts_with("HTTP/1.1 200"),
        Err(_) => false,
    }
}

fn backend_url() -> tauri::Url {
    tauri::Url::parse(&format!("http://{BACKEND_HOST}:{BACKEND_PORT}")).expect("URL backend valide")
}

// ---------------------------------------------------------------------------
// État du shell (pour tuer le backend à la sortie)
// ---------------------------------------------------------------------------
struct BackendState(Mutex<Option<Child>>);

/// Le TrayIcon DOIT rester vivant pendant toute la durée de vie de l'app
/// (le dropper le retire du tray). On le conserve dans l'état géré.
struct TrayState(Mutex<Option<tauri::tray::TrayIcon>>);

fn kill_backend_tree(app: &AppHandle) {
    let child = app.state::<BackendState>().0.lock().unwrap().take();
    if let Some(mut c) = child {
        // taskkill /PID <pid> /T /F : tue tout l'arbre de processus (uvicorn
        // + sous-processus éventuels), sans laisser d'orphelins.
        let _ = Command::new("taskkill")
            .args([
                "/PID",
                &c.id().to_string(),
                "/T",
                "/F",
                "/fi",
                "STATUS eq RUNNING",
            ])
            .creation_flags(CREATE_NO_WINDOW)
            .output();
        let _ = c.kill();
    }
}

// ---------------------------------------------------------------------------
// Tray : menu + clic
// ---------------------------------------------------------------------------
fn show_main_window(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.unminimize();
        let _ = w.set_focus();
    }
}

fn build_tray(app: &tauri::App) -> tauri::Result<tauri::tray::TrayIcon> {
    let open = MenuItem::with_id(app, "open", "Ouvrir StudioIA", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quitter StudioIA", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&open, &quit])?;

    // Icône embarquée (png 32x32) — indépendante de la config fenêtre.
    let icon = tauri::image::Image::from_bytes(include_bytes!("../icons/32x32.png"))?;

    TrayIconBuilder::with_id("main-tray")
        .icon(icon)
        .tooltip("StudioIA")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "open" => show_main_window(app),
            "quit" => {
                kill_backend_tree(app);
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_main_window(tray.app_handle());
            }
        })
        .build(app)
}

// ---------------------------------------------------------------------------
// Mise à jour automatique (tauri-plugin-updater + GitHub Releases)
// ---------------------------------------------------------------------------
// Vérifie une version au démarrage (arrière-plan) et, si dispo, télécharge
// l'installateur signé 'StudioIA-Setup.exe', le lance en silencieux puis quitte
// l'app pour laisser l'installateur remplacer le shell et les fichiers. Ne
// touche JAMAIS aux données utilisateur (%USERPROFILE%\StudioIA isolé) ni aux
// modèles Ollama. Silencieux en cas d'échec (offline / pas de release / refus).
fn spawn_update_check(handle: AppHandle) {
    tauri::async_runtime::spawn(async move {
        // Laisse le backend démarrer (le dashboard s'afficher) avant d'engager
        // un éventuel téléchargement.
        std::thread::sleep(Duration::from_secs(10));

        let Ok(updater) = handle.updater() else {
            return;
        };
        let Ok(Some(update)) = updater.check().await else {
            return; // à jour, ou réseau indisponible
        };
        eprintln!("[updater] version disponible : {}", update.version);

        // download() renvoie déjà les octets VÉRIFIÉS par signature (pubkey).
        match update.download(|_, _| {}, || {}).await {
            Ok(bytes) => {
                // Écrit l'installateur Inno Setup dans un fichier temporaire,
                // puis le lance en silencieux (aucune dialog box).
                let setup = std::env::temp_dir().join("StudioIA-Setup.exe");
                if std::fs::write(&setup, &bytes).is_ok() {
                    let _ = Command::new(&setup)
                        .args(["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"])
                        .spawn();
                }
                // Quitte l'app pour laisser l'installateur remplacer l'exe
                // (le dossier d'install est réinscriptible, sans admin).
                let _ = handle.exit(0);
            }
            Err(e) => eprintln!("[updater] échec du téléchargement : {e}"),
        }
    });
}

// ---------------------------------------------------------------------------
// Point d'entrée
// ---------------------------------------------------------------------------
fn main() {
    tauri::Builder::default()
        .manage(BackendState(Mutex::new(None)))
        .manage(TrayState(Mutex::new(None)))
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            let root = app_root();
            let handle = app.handle().clone();

            // 1. Démarre le backend s'il n'est pas déjà en ligne.
            if !backend_ready() {
                if let Some(child) = spawn_backend(&root) {
                    *app.state::<BackendState>().0.lock().unwrap() = Some(child);
                }
            }

            // 2. Tray (ouvert avant la fenêtre pour un accès même pendant le splash).
            //    Le TrayIcon doit rester vivant : stocké dans l'état géré.
            let tray = build_tray(app)?;
            *app.state::<TrayState>().0.lock().unwrap() = Some(tray);

            // 3. Fenêtre : splash local d'abord, navigation quand le backend répond.
            let window = WebviewWindowBuilder::new(
                app,
                "main",
                WebviewUrl::App("index.html".into()),
            )
            .title("StudioIA")
            .inner_size(1280.0, 820.0)
            .min_inner_size(960.0, 600.0)
            .build()?;

            // 3b. Mise à jour automatique (arrière-plan), avant de bouger `handle`.
            spawn_update_check(handle.clone());

            // 4. Attente du backend en arrière-plan, puis navigation.
            std::thread::spawn(move || {
                let start = Instant::now();
                while !backend_ready() && start.elapsed() < STARTUP_TIMEOUT {
                    std::thread::sleep(Duration::from_millis(500));
                }
                if let Some(w) = handle.get_webview_window("main") {
                    if backend_ready() {
                        let _ = w.navigate(backend_url());
                    } else {
                        // Splash -> message d'erreur sans quitter le domaine local.
                        let _ = w.eval(include_str!("../static/erreur.js"));
                    }
                }
            });

            // 5. Le bouton fermer minimise dans le tray (comportement "app native").
            let w_close = window.clone();
            window.on_window_event(move |event| {
                if let WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let _ = w_close.hide();
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("échec de la construction Tauri")
        .run(|app_handle, event| match event {
            RunEvent::ExitRequested { .. } => kill_backend_tree(app_handle),
            _ => {}
        });
}
