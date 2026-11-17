//! Masaüstü: birleşik Hukuk Asistanı sunucusunu (asistan/sunucu.py) bulur veya başlatır.
//!
//! Sunucu; avukatasistan (UETS e-tebligat, süre, TickTick/Notion/Telegram), UYAP evrak indirici/katalog
//! ve NAPS2 A4 PDF motorunu 127.0.0.1:8765'te tek JSON API olarak sunar. Arayüz (asistan.js) bu komutu
//! çağırır; dönen port + eşleştirme anahtarıyla sunucuya bağlanır.
//!
//! Python kurulu değilse hata döner; arayüz sunucusuz özelliklere (süre hesabı, A4 PDF) devam eder ve
//! kullanıcıya elle başlatma / eşleştirme yolunu gösterir. Kod paketin içinde: resources/asistan/.

use serde::Serialize;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::Manager;

const PORT: u16 = 8765;
static SUREC: Mutex<Option<Child>> = Mutex::new(None);

#[derive(Serialize)]
pub struct Baglanti {
    port: u16,
    anahtar: String,
    baslatildi: bool,
}

/// Sunucu ayakta mı? (anahtarsız /api/merhaba uç noktası)
fn ayakta() -> bool {
    let adres = SocketAddr::from(([127, 0, 0, 1], PORT));
    let Ok(mut s) = TcpStream::connect_timeout(&adres, Duration::from_millis(400)) else { return false };
    let _ = s.set_read_timeout(Some(Duration::from_millis(800)));
    if s.write_all(b"GET /api/merhaba HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n").is_err() {
        return false;
    }
    let mut yanit = String::new();
    let _ = s.read_to_string(&mut yanit);
    yanit.contains("CanEditor Hukuk Asistan")
}

fn uygulama_veri_dizini(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let d = app.path().app_data_dir().map_err(|e| e.to_string())?.join("asistan");
    std::fs::create_dir_all(&d).map_err(|e| e.to_string())?;
    Ok(d)
}

/// Sunucunun elle başlatıldığı durumdaki varsayılan veri dizini (sunucu.py veri_dizini() ile aynı kural).
fn varsayilan_veri_dizini() -> Option<PathBuf> {
    if cfg!(windows) {
        std::env::var_os("LOCALAPPDATA").map(|d| PathBuf::from(d).join("CanEditor").join("asistan"))
    } else if let Some(x) = std::env::var_os("XDG_DATA_HOME") {
        Some(PathBuf::from(x).join("caneditor").join("asistan"))
    } else {
        std::env::var_os("HOME").map(|h| PathBuf::from(h).join(".local").join("share").join("caneditor").join("asistan"))
    }
}

fn anahtar_oku(dizinler: &[PathBuf]) -> Option<String> {
    dizinler.iter().find_map(|d| {
        std::fs::read_to_string(d.join("anahtar")).ok().map(|s| s.trim().to_string()).filter(|s| !s.is_empty())
    })
}

/// Paketteki asistan/sunucu.py; geliştirme sırasında depo kökündeki asistan/ kullanılır.
fn sunucu_betigi(app: &tauri::AppHandle) -> Option<PathBuf> {
    let mut adaylar = Vec::new();
    if let Ok(r) = app.path().resource_dir() {
        adaylar.push(r.join("asistan").join("sunucu.py"));
        adaylar.push(r.join("_up_").join("asistan").join("sunucu.py"));
    }
    adaylar.push(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("asistan").join("sunucu.py"));
    adaylar.into_iter().find(|p| p.is_file())
}

fn python_adaylari() -> Vec<(&'static str, Vec<&'static str>)> {
    if cfg!(windows) {
        vec![("py", vec!["-3"]), ("python", vec![]), ("python3", vec![])]
    } else {
        vec![("python3", vec![]), ("python", vec![])]
    }
}

fn baslat(app: &tauri::AppHandle, veri: &PathBuf) -> Result<(), String> {
    let betik = sunucu_betigi(app).ok_or("Asistan sunucusu pakette bulunamadı")?;
    let mut son_hata = String::from("Python 3 bulunamadı. python.org'dan Python 3 kurun ya da sunucuyu elle başlatın.");
    for (komut, on_ek) in python_adaylari() {
        let mut c = Command::new(komut);
        c.args(&on_ek)
            .arg(&betik)
            .arg("--port")
            .arg(PORT.to_string())
            .env("CANASISTAN_VERI", veri)
            .env("PYTHONIOENCODING", "utf-8")
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            c.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
        }
        match c.spawn() {
            Ok(ch) => {
                if let Ok(mut s) = SUREC.lock() {
                    *s = Some(ch);
                }
                return Ok(());
            }
            Err(e) => son_hata = format!("{komut}: {e}"),
        }
    }
    Err(son_hata)
}

/// Arayüzün çağırdığı komut: sunucu yoksa başlatır, port + anahtarı döner.
#[tauri::command]
pub fn asistan_baglanti(app: tauri::AppHandle) -> Result<Baglanti, String> {
    let veri = uygulama_veri_dizini(&app)?;
    let mut dizinler = vec![veri.clone()];
    if let Some(v) = varsayilan_veri_dizini() {
        dizinler.push(v);
    }
    let mut baslatildi = false;
    if !ayakta() {
        baslat(&app, &veri)?;
        baslatildi = true;
        let bas = Instant::now();
        while !ayakta() {
            if bas.elapsed() > Duration::from_secs(8) {
                return Err("Asistan sunucusu başlatıldı ama yanıt vermedi".into());
            }
            std::thread::sleep(Duration::from_millis(150));
        }
    }
    let anahtar = anahtar_oku(&dizinler).ok_or("Sunucu çalışıyor ama eşleştirme anahtarı okunamadı")?;
    Ok(Baglanti { port: PORT, anahtar, baslatildi })
}

/// Uygulama kapanırken yalnızca bizim başlattığımız sunucuyu durdurur.
pub fn kapat() {
    if let Ok(mut s) = SUREC.lock() {
        if let Some(mut c) = s.take() {
            let _ = c.kill();
        }
    }
}
