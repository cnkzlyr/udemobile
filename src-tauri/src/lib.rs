use std::io::{Cursor, Read, Write};
use zip::write::SimpleFileOptions;
use zip::{ZipArchive, ZipWriter};

// DEĞİŞİM: Artık REST API değil, Tauri Command kullanıyoruz
#[tauri::command]
fn extract_udf(data: Vec<u8>) -> Result<String, String> {
    let reader = Cursor::new(data);
    let mut archive = ZipArchive::new(reader).map_err(|e| e.to_string())?;
    let mut content_file = archive.by_name("content.xml").map_err(|e| e.to_string())?;
    let mut xml_content = String::new();
    content_file.read_to_string(&mut xml_content).map_err(|e| e.to_string())?;
    Ok(xml_content)
}

// DEĞİŞİM: Sıkıştırılan dosyayı RAM'den direkt uygulamaya fırlatıyoruz
#[tauri::command]
fn package_udf(xml_content: String) -> Result<Vec<u8>, String> {
    let mut buffer = Cursor::new(Vec::new());
    {
        let mut zip = ZipWriter::new(&mut buffer);
        let options = SimpleFileOptions::default()
            .compression_method(zip::CompressionMethod::Deflated)
            .unix_permissions(0o755);
        zip.start_file("content.xml", options).map_err(|e| e.to_string())?;
        zip.write_all(xml_content.as_bytes()).map_err(|e| e.to_string())?;
        zip.finish().map_err(|e| e.to_string())?;
    }
    Ok(buffer.into_inner())
}


// ---------------------------------------------------------------------------
// Dahili güncelleyici: indirme ve kurulum (harici crate gerektirmez; curl kullanır —
// Windows 10+, macOS ve çoğu Linux dağıtımında yerleşik gelir)
// ---------------------------------------------------------------------------
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;

static UPDATE_DL: Mutex<Option<Child>> = Mutex::new(None);

#[derive(serde::Serialize)]
struct PlatformInfo {
    os: String,
    arch: String,
    appimage: bool,
}

#[derive(serde::Serialize)]
struct DownloadProgress {
    bytes: u64,
    finished: bool,
    ok: bool,
}

#[tauri::command]
fn platform_info() -> PlatformInfo {
    let os = match std::env::consts::OS {
        "windows" => "windows",
        "macos" => "macos",
        _ => "linux",
    };
    PlatformInfo {
        os: os.to_string(),
        arch: std::env::consts::ARCH.to_string(),
        appimage: std::env::var("APPIMAGE").map(|v| !v.is_empty()).unwrap_or(false),
    }
}

fn update_dir() -> PathBuf {
    std::env::temp_dir().join("caneditor-update")
}

fn safe_file_name(name: &str) -> Result<String, String> {
    if name.is_empty() || name.contains('/') || name.contains('\\') || name.contains("..") {
        return Err("Geçersiz dosya adı".into());
    }
    Ok(name.to_string())
}

#[tauri::command]
fn start_update_download(url: String, file_name: String) -> Result<String, String> {
    // Yalnızca bu deponun GitHub release dosyalarına izin ver
    if !url.starts_with("https://github.com/cnkzlyr/udemobile/releases/download/") {
        return Err("İzin verilmeyen indirme adresi".into());
    }
    let name = safe_file_name(&file_name)?;
    let dir = update_dir();
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let path = dir.join(&name);
    let _ = std::fs::remove_file(&path);

    let mut guard = UPDATE_DL.lock().map_err(|e| e.to_string())?;
    if let Some(mut old) = guard.take() {
        let _ = old.kill();
    }
    let mut cmd = Command::new(if cfg!(windows) { "curl.exe" } else { "curl" });
    cmd.args(["-L", "--fail", "--silent", "--show-error", "--retry", "3", "-o"])
        .arg(&path)
        .arg(&url);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }
    let child = cmd
        .spawn()
        .map_err(|e| format!("curl başlatılamadı: {} (curl yüklü olmalı)", e))?;
    *guard = Some(child);
    Ok(path.to_string_lossy().to_string())
}

#[tauri::command]
fn update_download_progress(path: String) -> Result<DownloadProgress, String> {
    let bytes = std::fs::metadata(&path).map(|m| m.len()).unwrap_or(0);
    let mut guard = UPDATE_DL.lock().map_err(|e| e.to_string())?;
    let (finished, ok) = match guard.as_mut() {
        Some(child) => match child.try_wait() {
            Ok(Some(status)) => (true, status.success()),
            Ok(None) => (false, false),
            Err(_) => (true, false),
        },
        None => (true, false),
    };
    if finished {
        *guard = None;
    }
    Ok(DownloadProgress { bytes, finished, ok })
}

#[tauri::command]
fn install_update(app: tauri::AppHandle, path: String) -> Result<(), String> {
    let p = PathBuf::from(&path);
    // Yalnızca kendi güncelleme klasörümüzdeki dosyalar çalıştırılabilir
    if !p.starts_with(update_dir()) || !p.is_file() {
        return Err("Güncelleme dosyası bulunamadı".into());
    }
    let lower = path.to_lowercase();

    if cfg!(windows) {
        Command::new(&p).spawn().map_err(|e| format!("Kurulum başlatılamadı: {}", e))?;
        app.exit(0);
    } else if cfg!(target_os = "macos") {
        Command::new("open").arg(&p).spawn().map_err(|e| e.to_string())?;
        // .dmg açılır; kullanıcı uygulamayı Applications'a sürükler
    } else if lower.ends_with(".appimage") {
        let target = std::env::var("APPIMAGE").map_err(|_| "APPIMAGE yolu bulunamadı".to_string())?;
        let target = PathBuf::from(target);
        let staged = target.with_extension("update-new");
        std::fs::copy(&p, &staged).map_err(|e| format!("Kopyalanamadı: {}", e))?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let _ = std::fs::set_permissions(&staged, std::fs::Permissions::from_mode(0o755));
        }
        std::fs::rename(&staged, &target).map_err(|e| format!("Değiştirilemedi: {}", e))?;
        Command::new(&target).spawn().map_err(|e| e.to_string())?;
        app.exit(0);
    } else {
        Command::new("xdg-open").arg(&p).spawn().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[derive(serde::Serialize)]
pub struct StartupFile {
    pub name: String,
    pub path: String,
    pub data: Vec<u8>,
}

#[tauri::command]
fn get_startup_file() -> Option<StartupFile> {
    for arg in std::env::args().skip(1) {
        if arg.starts_with("--") || arg.starts_with("-") {
            continue;
        }
        let p = std::path::Path::new(&arg);
        if p.is_file() {
            if let Ok(data) = std::fs::read(p) {
                let name = p
                    .file_name()
                    .map(|n| n.to_string_lossy().to_string())
                    .unwrap_or_else(|| "Belge.udf".to_string());
                return Some(StartupFile {
                    name,
                    path: p.to_string_lossy().to_string(),
                    data,
                });
            }
        }
    }
    None
}

#[tauri::command]
fn read_file_binary(path: String) -> Result<Vec<u8>, String> {
    let p = std::path::Path::new(&path);
    std::fs::read(p).map_err(|e| format!("Dosya okunamadı: {}", e))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            extract_udf,
            package_udf,
            platform_info,
            start_update_download,
            update_download_progress,
            install_update,
            get_startup_file,
            read_file_binary
        ])
        .run(tauri::generate_context!())
        .expect("Tauri motoru başlatılamadı");
}
