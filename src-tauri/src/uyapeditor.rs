//! "Orijinal UYAP Editör'de aç" (masaüstü): belgeyi resmi UYAP Doküman Editörü'nde açar.
//!
//! 1) Bilgisayarda kurulu editör aranır: resmi kurulum (Windows Program Files / Linux /usr/share/UYAPEditor /
//!    macOS /Applications), uyap-editor-modern (uyap-dokuman) ya da CanEditor'un daha önce kurduğu kopya.
//! 2) Yoksa CanEditor kendisi kurar: resmi Linux paketindeki platformdan bağımsız editör jar'ları YALNIZCA
//!    rayp.adalet.gov.tr'den, işletim sistemine uygun resmi OpenJDK 14.0.2 YALNIZCA download.java.net'ten
//!    (SHA-256 sabit) indirilir. Editör Java 6–14 ister; 14.0.2 UYAP'ın desteklediği sürümdür.

use serde::Serialize;
use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

const EDITOR_ADRESI: &str = "https://rayp.adalet.gov.tr/resimler/2/dosya/uyapeditor_5.4.20_amd64.zip";
const ANA_SINIF: &str = "tr.com.havelsan.uyap.system.editor.common.WPAppManager";
const JDK_ON: &str = "https://download.java.net/java/GA/jdk14.0.2/205943a0976c4ed48cb16f1043c5c647/12/GPL/";

static DURUM: Mutex<String> = Mutex::new(String::new());

fn durum_yaz(m: &str) {
    if let Ok(mut d) = DURUM.lock() {
        *d = m.to_string();
    }
}

#[tauri::command]
pub fn uyap_editor_durum() -> String {
    DURUM.lock().map(|d| d.clone()).unwrap_or_default()
}

/// (dosya adı, SHA-256) — işletim sistemine göre resmi OpenJDK 14.0.2
fn jdk_paketi() -> Option<(&'static str, &'static str)> {
    if cfg!(windows) {
        Some(("openjdk-14.0.2_windows-x64_bin.zip", "20600c0bda9d1db9d20dbe1ab656a5f9175ffb990ef3df6af5d994673e4d8ff9"))
    } else if cfg!(target_os = "macos") {
        // Apple Silicon'da Rosetta 2 ile çalışır (JDK 14'ün arm64 sürümü yok)
        Some(("openjdk-14.0.2_osx-x64_bin.tar.gz", "386a96eeef63bf94b450809d69ceaa1c9e32a97230e0a120c1b41786b743ae84"))
    } else if cfg!(target_os = "linux") && cfg!(target_arch = "x86_64") {
        Some(("openjdk-14.0.2_linux-x64_bin.tar.gz", "91310200f072045dc6cef2c8c23e7e6387b37c46e9de49623ce0fa461a24623d"))
    } else {
        None
    }
}

#[derive(Serialize, Clone)]
enum Baslatici {
    /// Kendi başlatıcısı olan kurulum (exe / sh / uyap-dokuman / .app)
    Program(PathBuf, Vec<String>),
    /// Jar klasörü + java
    Java(PathBuf, PathBuf),
}

fn veri(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let d = app.path().app_data_dir().map_err(|e| e.to_string())?.join("uyap-editor");
    fs::create_dir_all(&d).map_err(|e| e.to_string())?;
    Ok(d)
}

fn kucuk(p: &Path) -> String {
    p.file_name().map(|s| s.to_string_lossy().to_lowercase()).unwrap_or_default()
}

/// kök altında (en fazla `derinlik` seviye) editor_lib.jar içeren klasörleri bulur
fn jar_ara(kok: &Path, derinlik: u32, bulunan: &mut Vec<PathBuf>) {
    if derinlik == 0 || bulunan.len() > 4 {
        return;
    }
    let Ok(rd) = fs::read_dir(kok) else { return };
    for e in rd.flatten() {
        let p = e.path();
        if p.is_dir() {
            let ad = kucuk(&p);
            if ad.starts_with('.') || ad == "windows" || ad == "$recycle.bin" || ad == "node_modules" {
                continue;
            }
            if p.join("editor_lib.jar").is_file() && p.join("editor_lib2.jar").is_file() {
                bulunan.push(p.clone());
                continue;
            }
            jar_ara(&p, derinlik - 1, bulunan);
        }
    }
}

fn javaw_bul(d: &Path) -> Option<PathBuf> {
    let adlar: &[&str] = if cfg!(windows) { &["bin/javaw.exe", "bin/java.exe"] } else { &["bin/java", "Contents/Home/bin/java"] };
    for alt in ["jre", "jdk", "java", "runtime", "."] {
        for a in adlar {
            let p = d.join(alt).join(a);
            if p.is_file() {
                return Some(p);
            }
        }
    }
    if let Ok(rd) = fs::read_dir(d) {
        for e in rd.flatten() {
            let ad = kucuk(&e.path());
            if (ad.starts_with("jdk") || ad.starts_with("jre") || ad.contains("openjdk")) && e.path().is_dir() {
                for a in adlar {
                    let p = e.path().join(a);
                    if p.is_file() {
                        return Some(p);
                    }
                }
            }
        }
    }
    None
}

/// Kurulu editörü bul (resmi / modern / CanEditor'un kurduğu).
fn bul(app: &tauri::AppHandle) -> Option<Baslatici> {
    // CanEditor'un kendi kurduğu kopya
    if let Ok(v) = veri(app) {
        let jars = v.join("editor");
        if jars.join("editor_lib.jar").is_file() {
            if let Some(j) = javaw_bul(&v) {
                return Some(Baslatici::Java(jars, j));
            }
        }
    }
    let ev = std::env::var("HOME").or_else(|_| std::env::var("USERPROFILE")).unwrap_or_default();
    if cfg!(target_os = "linux") {
        for p in [format!("{}/.local/bin/uyap-dokuman", ev), "/usr/local/bin/uyap-dokuman".into(), "/usr/bin/uyap-dokuman".into()] {
            if Path::new(&p).is_file() {
                return Some(Baslatici::Program(PathBuf::from(p), vec![]));
            }
        }
        for d in ["/usr/share/UYAPEditor", "/opt/UYAPEditor", "/opt/uyapeditor"] {
            let sh = Path::new(d).join("dokuman.sh");
            if sh.is_file() {
                return Some(Baslatici::Program(PathBuf::from("bash"), vec![sh.display().to_string()]));
            }
        }
    }
    let mut kokler: Vec<PathBuf> = Vec::new();
    if cfg!(windows) {
        for v in ["ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "LOCALAPPDATA", "APPDATA"] {
            if let Ok(p) = std::env::var(v) {
                kokler.push(PathBuf::from(p));
            }
        }
        kokler.push(PathBuf::from("C:\\"));
        kokler.push(PathBuf::from(&ev));
    } else if cfg!(target_os = "macos") {
        kokler.push(PathBuf::from("/Applications"));
        kokler.push(PathBuf::from(format!("{}/Applications", ev)));
    } else {
        kokler.push(PathBuf::from("/opt"));
        kokler.push(PathBuf::from(format!("{}/.local/share", ev)));
    }
    let mut bulunan = Vec::new();
    for k in &kokler {
        jar_ara(k, if cfg!(target_os = "macos") { 5 } else { 3 }, &mut bulunan);
    }
    for d in bulunan {
        // macOS .app paketi: open -a
        if cfg!(target_os = "macos") {
            let mut p = d.as_path();
            while let Some(u) = p.parent() {
                if p.extension().map(|e| e == "app").unwrap_or(false) {
                    return Some(Baslatici::Program(PathBuf::from("open"), vec!["-a".into(), p.display().to_string()]));
                }
                p = u;
            }
        }
        // klasörde / üstünde editörün kendi .exe başlatıcısı
        if cfg!(windows) {
            for yer in [d.clone(), d.parent().map(|x| x.to_path_buf()).unwrap_or(d.clone())] {
                if let Ok(rd) = fs::read_dir(&yer) {
                    for e in rd.flatten() {
                        let ad = kucuk(&e.path());
                        if ad.ends_with(".exe") && (ad.contains("dokuman") || ad.contains("doküman") || ad.contains("editor") || ad.contains("uyap"))
                            && !ad.contains("unins") && !ad.contains("sablon") && !ad.contains("update")
                        {
                            return Some(Baslatici::Program(e.path(), vec![]));
                        }
                    }
                }
            }
        }
        let ust = d.parent().map(|x| x.to_path_buf()).unwrap_or(d.clone());
        if let Some(j) = javaw_bul(&d).or_else(|| javaw_bul(&ust)) {
            return Some(Baslatici::Java(d, j));
        }
    }
    None
}

fn ajan() -> ureq::Agent {
    let mut b = ureq::AgentBuilder::new().timeout_connect(Duration::from_secs(20)).timeout_read(Duration::from_secs(120));
    if let Ok(t) = native_tls::TlsConnector::new() {
        b = b.tls_connector(std::sync::Arc::new(t));
    }
    b.build()
}

fn indir(url: &str, hedef: &Path, etiket: &str) -> Result<(), String> {
    let r = ajan().get(url).call().map_err(|e| format!("{} indirilemedi: {}", etiket, e))?;
    let toplam: u64 = r.header("Content-Length").and_then(|s| s.parse().ok()).unwrap_or(0);
    let mut okur = r.into_reader();
    let gecici = hedef.with_extension("tmp");
    let mut f = fs::File::create(&gecici).map_err(|e| e.to_string())?;
    let mut b = vec![0u8; 1 << 16];
    let mut n: u64 = 0;
    let mut son = u64::MAX;
    loop {
        let k = okur.read(&mut b).map_err(|e| format!("{} indirme kesildi: {}", etiket, e))?;
        if k == 0 {
            break;
        }
        f.write_all(&b[..k]).map_err(|e| e.to_string())?;
        n += k as u64;
        if toplam > 0 && n * 100 / toplam != son {
            son = n * 100 / toplam;
            durum_yaz(&format!("{} indiriliyor… %{}", etiket, son));
        }
    }
    drop(f);
    fs::rename(&gecici, hedef).map_err(|e| e.to_string())
}

fn sha256(p: &Path) -> Result<String, String> {
    use sha2::{Digest, Sha256};
    let mut f = fs::File::open(p).map_err(|e| e.to_string())?;
    let mut h = Sha256::new();
    let mut b = vec![0u8; 1 << 16];
    loop {
        let n = f.read(&mut b).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        h.update(&b[..n]);
    }
    Ok(h.finalize().iter().map(|x| format!("{:02x}", x)).collect())
}

/// .deb (ar) → data.tar.xz → usr/share/UYAPEditor/*.jar
fn deb_ac(deb: &[u8], hedef: &Path) -> Result<usize, String> {
    if !deb.starts_with(b"!<arch>\n") {
        return Err("Debian paketi değil".into());
    }
    let mut i = 8;
    while i + 60 <= deb.len() {
        let ad = String::from_utf8_lossy(&deb[i..i + 16]).trim().trim_end_matches('/').to_string();
        let boy: usize = String::from_utf8_lossy(&deb[i + 48..i + 58]).trim().parse().map_err(|_| "ar başlığı bozuk")?;
        let icerik = &deb[i + 60..(i + 60 + boy).min(deb.len())];
        i += 60 + boy + (boy & 1);
        if ad.starts_with("data.tar") {
            let mut ham = Vec::new();
            if ad.ends_with(".xz") {
                lzma_rs::xz_decompress(&mut std::io::BufReader::new(icerik), &mut ham).map_err(|e| format!("xz: {:?}", e))?;
            } else {
                return Err(format!("desteklenmeyen sıkıştırma: {}", ad));
            }
            let mut ar = tar::Archive::new(std::io::Cursor::new(ham));
            let mut n = 0;
            for e in ar.entries().map_err(|e| e.to_string())? {
                let mut e = e.map_err(|e| e.to_string())?;
                let yol = e.path().map_err(|e| e.to_string())?.to_string_lossy().trim_start_matches("./").to_string();
                if let Some(kisa) = yol.strip_prefix("usr/share/UYAPEditor/") {
                    if kisa.ends_with(".jar") && !kisa.contains('/') {
                        let mut o = fs::File::create(hedef.join(kisa)).map_err(|e| e.to_string())?;
                        std::io::copy(&mut e, &mut o).map_err(|e| e.to_string())?;
                        n += 1;
                    }
                }
            }
            return Ok(n);
        }
    }
    Err("data.tar bulunamadı".into())
}

fn kur(app: &tauri::AppHandle) -> Result<Baslatici, String> {
    let v = veri(app)?;
    let (jdk_ad, jdk_sha) = jdk_paketi().ok_or("Bu işletim sistemi için Java 14 paketi yok")?;
    // 1) resmi editör jar'ları
    let jars = v.join("editor");
    if !jars.join("editor_lib.jar").is_file() {
        durum_yaz("Resmi UYAP Editör indiriliyor (rayp.adalet.gov.tr)…");
        let z = v.join("uyapeditor.zip");
        indir(EDITOR_ADRESI, &z, "Resmi UYAP Editör")?;
        durum_yaz("UYAP Editör dosyaları çıkarılıyor…");
        let mut arsiv = zip::ZipArchive::new(fs::File::open(&z).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
        let gecici = v.join("editor.yeni");
        let _ = fs::remove_dir_all(&gecici);
        fs::create_dir_all(&gecici).map_err(|e| e.to_string())?;
        let mut n = 0;
        for k in 0..arsiv.len() {
            let mut g = arsiv.by_index(k).map_err(|e| e.to_string())?;
            let ad = g.name().to_lowercase();
            if ad.starts_with("uyapeditor") && ad.ends_with(".deb") {
                let mut deb = Vec::new();
                g.read_to_end(&mut deb).map_err(|e| e.to_string())?;
                n = deb_ac(&deb, &gecici)?;
                break;
            }
        }
        let _ = fs::remove_file(&z);
        if n == 0 || !gecici.join("editor_lib.jar").is_file() {
            return Err("Pakette UYAP Editör dosyaları bulunamadı".into());
        }
        let _ = fs::remove_dir_all(&jars);
        fs::rename(&gecici, &jars).map_err(|e| e.to_string())?;
    }
    // 2) resmi OpenJDK 14.0.2
    if javaw_bul(&v).is_none() {
        durum_yaz("Java 14.0.2 indiriliyor (download.java.net, ~190 MB, bir kez)…");
        let a = v.join(jdk_ad);
        indir(&format!("{}{}", JDK_ON, jdk_ad), &a, "Java 14.0.2")?;
        if sha256(&a)? != jdk_sha {
            let _ = fs::remove_file(&a);
            return Err("Java 14 paketinin SHA-256 özeti uyuşmuyor".into());
        }
        durum_yaz("Java 14.0.2 açılıyor…");
        if jdk_ad.ends_with(".zip") {
            let mut arsiv = zip::ZipArchive::new(fs::File::open(&a).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
            arsiv.extract(&v).map_err(|e| e.to_string())?;
        } else {
            let f = fs::File::open(&a).map_err(|e| e.to_string())?;
            let mut t = tar::Archive::new(flate2::read::GzDecoder::new(f));
            t.set_preserve_permissions(true);
            t.unpack(&v).map_err(|e| e.to_string())?;
        }
        let _ = fs::remove_file(&a);
    }
    let j = javaw_bul(&v).ok_or("Java 14 açılamadı")?;
    durum_yaz("UYAP Editör kuruldu");
    Ok(Baslatici::Java(jars, j))
}

fn calistir(b: &Baslatici, dosya: &Path) -> Result<(), String> {
    let usf = dosya.extension().map(|e| e.to_string_lossy().eq_ignore_ascii_case("usf")).unwrap_or(false);
    match b {
        Baslatici::Program(p, on) => {
            let mut k = Command::new(p);
            k.args(on).arg(dosya);
            k.spawn().map_err(|e| format!("UYAP Editör başlatılamadı: {}", e))?;
        }
        Baslatici::Java(jars, java) => {
            let ayrac = if cfg!(windows) { ";" } else { ":" };
            let mut cp: Vec<String> = fs::read_dir(jars)
                .map_err(|e| e.to_string())?
                .flatten()
                .map(|e| e.path())
                .filter(|p| p.extension().map(|x| x == "jar").unwrap_or(false))
                .map(|p| p.display().to_string())
                .collect();
            cp.sort();
            let mut k = Command::new(java);
            k.arg("-Xmx768m")
                .arg("-Dfile.encoding=UTF-8")
                .arg("-cp")
                .arg(cp.join(ayrac))
                .arg(ANA_SINIF)
                .arg("getNewWPInstance")
                .arg(if usf { "EDITOR_TYPE_TEMPLATE" } else { "EDITOR_TYPE_DOCUMENT" })
                .arg(dosya)
                .current_dir(jars);
            k.spawn().map_err(|e| format!("UYAP Editör başlatılamadı: {}", e))?;
        }
    }
    Ok(())
}

/// Belgeyi resmi UYAP Editör'de aç. `yol`: diskteki belge (değiştirilmemişse) · `verib64`: belge baytları (geçici kopya).
#[tauri::command(async)]
pub fn uyap_editor_ac(app: tauri::AppHandle, yol: Option<String>, ad: Option<String>, verib64: Option<String>) -> Result<String, String> {
    use base64::Engine;
    let dosya = if let Some(y) = yol.filter(|y| Path::new(y).is_file()) {
        PathBuf::from(y)
    } else {
        let veri_b = base64::engine::general_purpose::STANDARD
            .decode(verib64.ok_or("belge yok")?.as_bytes())
            .map_err(|e| e.to_string())?;
        let mut a = ad.unwrap_or_else(|| "Belge.udf".into()).replace(['\\', '/', ':', '*', '?', '"', '<', '>', '|'], "_");
        if !a.to_lowercase().ends_with(".udf") && !a.to_lowercase().ends_with(".usf") {
            a.push_str(".udf");
        }
        let d = veri(&app)?.join("belgeler");
        fs::create_dir_all(&d).map_err(|e| e.to_string())?;
        let f = d.join(a);
        fs::write(&f, veri_b).map_err(|e| e.to_string())?;
        f
    };
    let b = match bul(&app) {
        Some(b) => b,
        None => kur(&app)?,
    };
    calistir(&b, &dosya)?;
    let nerede = match &b {
        Baslatici::Program(p, _) => p.display().to_string(),
        Baslatici::Java(j, _) => j.display().to_string(),
    };
    durum_yaz("");
    Ok(format!("UYAP Editör açılıyor: {} ({})", dosya.file_name().map(|s| s.to_string_lossy().to_string()).unwrap_or_default(), nerede))
}
