//! Masaüstü: birleşik Hukuk Asistanı sunucusunu (asistan/sunucu.py) bulur veya başlatır.
//!
//! Sunucu; avukatasistan (UETS e-tebligat, süre, TickTick/Notion/Telegram), UYAP evrak indirici/katalog
//! ve NAPS2 A4 PDF motorunu 127.0.0.1:8765'te tek JSON API olarak sunar. Arayüz (asistan.js) bu komutu
//! çağırır; dönen port + eşleştirme anahtarıyla sunucuya bağlanır.
//!
//! Kurulum paketlerinde sunucu PyInstaller ile dondurulmuş ikili olarak gelir (resources/sidecar/…):
//! kullanıcı Python kurmaz. Gömülü Java da sunucuya ve görevlerine CANASISTAN_JAVA_HOME ile verilir.
//! İkili yoksa (geliştirme) sistemdeki Python ile resources/asistan/sunucu.py denenir.

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

/// Pakete gömülü sunucu ikilisi (PyInstaller, scripts/asistan_paketle.py): Python kurulumu gerektirmez.
/// resources/sidecar/asistan-sunucu-<mimari>/asistan-sunucu[.exe]
fn gomulu_sunucu(app: &tauri::AppHandle) -> Option<PathBuf> {
    let ad = if cfg!(windows) { "asistan-sunucu.exe" } else { "asistan-sunucu" };
    let p = app
        .path()
        .resource_dir()
        .ok()?
        .join("sidecar")
        .join(format!("asistan-sunucu-{}", std::env::consts::ARCH))
        .join(ad);
    if !p.is_file() {
        return None;
    }
    #[cfg(unix)]
    {
        // Paketleyici çalıştırma iznini kaybettiyse geri ver (yazılabilir kurulumlarda)
        use std::os::unix::fs::PermissionsExt;
        if let Ok(m) = std::fs::metadata(&p) {
            if m.permissions().mode() & 0o111 == 0 {
                let mut iz = m.permissions();
                iz.set_mode(iz.mode() | 0o755);
                let _ = std::fs::set_permissions(&p, iz);
            }
        }
    }
    Some(p)
}

/// Sunucu ve görevlerine verilen ortam: gömülü Java ve CanEditor'un indirdiği resmî UYAP Editör jar'ları.
fn ortam_ekle(app: &tauri::AppHandle, c: &mut Command, veri: &PathBuf) {
    c.env("CANASISTAN_VERI", veri).env("PYTHONIOENCODING", "utf-8");
    if let Some(jre) = crate::adalet::gomulu_jre(app) {
        c.env("CANASISTAN_JAVA_HOME", jre);
    }
    if let Ok(d) = app.path().app_data_dir() {
        c.env("CANASISTAN_UYAP_JARS", d.join("uyap-editor").join("editor"));
    }
    // v4.10.0: resmî Havelsan UYAP Editör jar'ları ve Times New Roman/Arial TTF'leri pakete gömülüdür
    // (asistan/jars/uyap-editor, asistan/fonts). UDF→PDF artık kullanıcının UYAP Editör kurmasını beklemez;
    // fontlar JVM'e kaydedildiği için PDF Helvetica'ya düşmez (bozuk dönüşümün kök nedeni).
    // EN: bundled official jars + fonts so UDF->PDF never falls back to the lossy path.
    if let Ok(r) = app.path().resource_dir() {
        for kok in [r.join("asistan"), r.join("_up_").join("asistan")] {
            if kok.join("jars").join("uyap-editor").join("editor_lib.jar").is_file() {
                c.env("CANASISTAN_PAKET_JARS", kok.join("jars").join("uyap-editor"));
                c.env("CANASISTAN_FONTS", kok.join("fonts"));
                break;
            }
        }
    }
    // Gömülü görünmez tarayıcı (Chrome for Testing: chrome-headless-shell + chromedriver):
    // kullanıcı Chrome kurmaz, tarayıcı hiçbir zaman ön planda açılmaz.
    if let Ok(r) = app.path().resource_dir() {
        let kok = r.join(format!("tarayici-{}", std::env::consts::ARCH));
        let uz = if cfg!(windows) { ".exe" } else { "" };
        let kabuk = kok.join("chrome").join(format!("chrome-headless-shell{uz}"));
        let surucu = kok.join(format!("chromedriver{uz}"));
        if kabuk.is_file() {
            c.env("CANASISTAN_CHROME", kabuk);
        }
        if surucu.is_file() {
            c.env("CANASISTAN_CHROMEDRIVER", surucu);
        }
    }
    c.env("CANASISTAN_GORUNMEZ", "1");
}

fn python_adaylari() -> Vec<(&'static str, Vec<&'static str>)> {
    if cfg!(windows) {
        vec![("py", vec!["-3"]), ("python", vec![]), ("python3", vec![])]
    } else {
        vec![("python3", vec![]), ("python", vec![])]
    }
}

/// Bizim başlattığımız sunucu hâlâ çalışıyor mu? (çalışıyorsa ikinci kez başlatılmaz: port çakışmasın)
fn surec_yasiyor() -> bool {
    match SUREC.lock() {
        Ok(mut s) => match s.as_mut() {
            Some(c) => matches!(c.try_wait(), Ok(None)),
            None => false,
        },
        Err(_) => false,
    }
}

fn gunluk_yolu(veri: &PathBuf) -> PathBuf {
    veri.join("sunucu.log")
}

/// Sunucu günlüğünün sonu (hata iletisine eklenir: kullanıcı/destek gerçek nedeni görür)
fn gunluk_sonu(veri: &PathBuf) -> String {
    let t = std::fs::read_to_string(gunluk_yolu(veri)).unwrap_or_default();
    let satirlar: Vec<&str> = t.lines().rev().take(6).collect();
    satirlar.into_iter().rev().collect::<Vec<_>>().join(" | ")
}

fn surec_kaydet(c: &mut Command, veri: &PathBuf) -> Result<(), String> {
    c.stdin(Stdio::null());
    match std::fs::File::create(gunluk_yolu(veri)) {
        Ok(f) => {
            let f2 = f.try_clone().map_err(|e| e.to_string())?;
            c.stdout(Stdio::from(f)).stderr(Stdio::from(f2));
        }
        Err(_) => {
            c.stdout(Stdio::null()).stderr(Stdio::null());
        }
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        c.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    let ch = c.spawn().map_err(|e| e.to_string())?;
    if let Ok(mut s) = SUREC.lock() {
        *s = Some(ch);
    }
    Ok(())
}

fn baslat(app: &tauri::AppHandle, veri: &PathBuf) -> Result<(), String> {
    // 1) Gömülü ikili (kurulum paketleri): Python gerekmez
    if let Some(exe) = gomulu_sunucu(app) {
        let mut c = Command::new(&exe);
        c.arg("--port").arg(PORT.to_string());
        ortam_ekle(app, &mut c, veri);
        return surec_kaydet(&mut c, veri).map_err(|e| format!("Gömülü asistan sunucusu başlatılamadı: {e}"));
    }
    // 2) Geliştirme / taşınabilir kurulum: sistemdeki Python ile kaynak koddan
    let betik = sunucu_betigi(app).ok_or("Asistan sunucusu pakette bulunamadı")?;
    let mut son_hata = String::from("Python 3 bulunamadı. python.org'dan Python 3 kurun ya da sunucuyu elle başlatın.");
    for (komut, on_ek) in python_adaylari() {
        let mut c = Command::new(komut);
        c.args(&on_ek).arg(&betik).arg("--port").arg(PORT.to_string());
        ortam_ekle(app, &mut c, veri);
        match surec_kaydet(&mut c, veri) {
            Ok(()) => return Ok(()),
            Err(e) => son_hata = format!("{komut}: {e}"),
        }
    }
    Err(son_hata)
}

/// Arayüzün çağırdığı komut: sunucu yoksa başlatır, port + anahtarı döner.
/// async + spawn_blocking: Tauri eşzamanlı komutları ana (arayüz) iş parçacığında çalıştırır; bağlantı
/// denetimi ve sunucu başlatma beklemesi arayüzü dondurmasın (evrak aramasında donma buradan geliyordu).
#[tauri::command]
pub async fn asistan_baglanti(app: tauri::AppHandle) -> Result<Baglanti, String> {
    tauri::async_runtime::spawn_blocking(move || baglanti_hazirla(&app))
        .await
        .map_err(|e| e.to_string())?
}

fn baglanti_hazirla(app: &tauri::AppHandle) -> Result<Baglanti, String> {
    let app = app.clone();
    let veri = uygulama_veri_dizini(&app)?;
    let mut dizinler = vec![veri.clone()];
    if let Some(v) = varsayilan_veri_dizini() {
        dizinler.push(v);
    }
    let mut baslatildi = false;
    if !ayakta() {
        // Önceki çağrının başlattığı sunucu hâlâ açılıyorsa yenisi başlatılmaz, onu beklenir
        if !surec_yasiyor() {
            baslat(&app, &veri)?;
            baslatildi = true;
        }
        // İlk açılışta (modüllerin kopyalanması + Windows Defender taraması) 30-60 sn sürebilir
        let bas = Instant::now();
        while !ayakta() {
            if !surec_yasiyor() {
                return Err(format!("Asistan sunucusu kapandı. {}", gunluk_sonu(&veri)));
            }
            if bas.elapsed() > Duration::from_secs(90) {
                return Err(format!("Asistan sunucusu açılıyor, henüz yanıt vermedi. {}", gunluk_sonu(&veri)));
            }
            std::thread::sleep(Duration::from_millis(250));
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
