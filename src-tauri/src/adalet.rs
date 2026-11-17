//! Masaüstü (öncelikle Windows): resmi Adalet E-İmza uygulamasını CanEditor'a GÖMÜLÜ Java ile çalıştırır.
//!
//! Neden: Kart sürücüsü (AKİS / ArkSigner PKCS#11 kütüphanesi) kurulu olmayan bilgisayarda PKCS#11 yolu kartı göremez.
//! Resmi Adalet E-İmza uygulaması (TÜBİTAK MA3) PKCS#11 kütüphanesi bulamayınca kartla doğrudan APDU ile konuşur;
//! okuyucuya işletim sisteminin PC/SC katmanı (Windows: winscard.dll + Windows'un kendi CCID sürücüsü) ile ulaşır.
//! ACR39 ve ArkSigner standart CCID cihazlarıdır: ek sürücü gerekmez. Java, kurulum paketine gömülüdür
//! (CI'da jlink ile hazırlanır: resources/eimza/jre). Kullanıcı Java ya da sürücü indirmez.
//!
//! Resmi uygulamanın kendisi dağıtılmaz: ilk kullanımda YALNIZCA cdn.uyap.gov.tr'den (resmi güncelleme adresi
//! latest.json) otomatik indirilir; paketteki platformdan bağımsız eimza-tray-*.jar çıkarılır.
//! Uygulama 127.0.0.1:5975'te çalışır; Chrome'daki UYAP portalları da aynı servisi kullanabilir.

use serde::Serialize;
use std::fs;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

const PORT: u16 = 5975;
const SURUM_ADRESI: &str = "https://cdn.uyap.gov.tr/framework/public/latest.json";
const IZINLI_ON_EK: &str = "https://cdn.uyap.gov.tr/";

static DURUM: Mutex<String> = Mutex::new(String::new());
static SUREC: Mutex<Option<Child>> = Mutex::new(None);
static KURULUYOR: Mutex<bool> = Mutex::new(false);

fn durum_yaz(m: &str) {
    if let Ok(mut d) = DURUM.lock() {
        *d = m.to_string();
    }
}

fn veri_dizini(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let d = app.path().app_data_dir().map_err(|e| e.to_string())?.join("adalet-eimza");
    fs::create_dir_all(&d).map_err(|e| e.to_string())?;
    Ok(d)
}

fn jar_yolu(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    Ok(veri_dizini(app)?.join("eimza-tray.jar"))
}

/// Gömülü Java'nın kök dizini (JAVA_HOME). Tüm masaüstü paketlerinde bulunur (CI: jlink):
/// resources/eimza/jre-<mimari> (macOS universal: aarch64 + x86_64 ayrı) ya da resources/eimza/jre.
/// Kullanıcı Java kurmaz; Hukuk Asistanı görevleri de (UDF→PDF) bu Java'yı kullanır.
pub fn gomulu_jre(app: &tauri::AppHandle) -> Option<PathBuf> {
    let eimza = app.path().resource_dir().ok()?.join("eimza");
    let java = if cfg!(windows) { "java.exe" } else { "java" };
    [eimza.join(format!("jre-{}", std::env::consts::ARCH)), eimza.join("jre")]
        .into_iter()
        .find(|d| d.join("bin").join(java).is_file())
}

/// Gömülü Java çalıştırılabilir dosyası. Yoksa None.
fn java_yolu(app: &tauri::AppHandle) -> Option<PathBuf> {
    let kok = gomulu_jre(app)?.join("bin");
    let adaylar: &[&str] = if cfg!(windows) { &["javaw.exe", "java.exe"] } else { &["java"] };
    adaylar.iter().map(|a| kok.join(a)).find(|p| p.is_file())
}

/// Windows e-imza ajanı (Unicode PC/SC sağlayıcısı): resources/eimza/eimza-win-agent.jar
fn ajan_yolu(app: &tauri::AppHandle) -> Option<PathBuf> {
    let p = app.path().resource_dir().ok()?.join("eimza").join("eimza-win-agent.jar");
    if p.is_file() { Some(p) } else { None }
}

/// JVM seçeneği için yol: Windows'un "\\?\" önekini atar (Java -javaagent bunu çözemez).
fn duz_yol(p: &std::path::Path) -> String {
    let s = p.display().to_string();
    s.strip_prefix(r"\\?\").map(|x| x.to_string()).unwrap_or(s)
}

fn port_acik() -> bool {
    let a: SocketAddr = ([127, 0, 0, 1], PORT).into();
    TcpStream::connect_timeout(&a, Duration::from_millis(700)).is_ok()
}

fn surec_canli() -> bool {
    if let Ok(mut g) = SUREC.lock() {
        if let Some(c) = g.as_mut() {
            match c.try_wait() {
                Ok(None) => return true,
                _ => {
                    *g = None;
                }
            }
        }
    }
    false
}

#[derive(Serialize)]
pub struct AdaletDurum {
    /// Gömülü Java pakette var mı
    jre: bool,
    /// Resmi uygulama kurulu mu
    kurulu: bool,
    /// 127.0.0.1:5975 yanıt veriyor mu (gömülü ya da bilgisayara ayrıca kurulmuş resmi uygulama)
    port: bool,
    calisiyor: bool,
    kuruluyor: bool,
    surum: String,
    durum: String,
}

#[tauri::command]
pub fn adalet_durum(app: tauri::AppHandle) -> AdaletDurum {
    let surum = veri_dizini(&app)
        .ok()
        .and_then(|d| fs::read_to_string(d.join("surum.txt")).ok())
        .unwrap_or_default()
        .trim()
        .to_string();
    AdaletDurum {
        jre: java_yolu(&app).is_some(),
        kurulu: jar_yolu(&app).map(|p| p.is_file()).unwrap_or(false),
        port: port_acik(),
        calisiyor: surec_canli(),
        kuruluyor: KURULUYOR.lock().map(|g| *g).unwrap_or(false),
        surum,
        durum: DURUM.lock().map(|d| d.clone()).unwrap_or_default(),
    }
}

fn ajan() -> Result<ureq::Agent, String> {
    // İşletim sisteminin güvendiği kök sertifikalar (Windows: schannel) — Kamu SM kökleri dahil
    let tls = native_tls::TlsConnector::new().map_err(|e| e.to_string())?;
    Ok(ureq::AgentBuilder::new()
        .tls_connector(std::sync::Arc::new(tls))
        .timeout_connect(Duration::from_secs(20))
        .timeout_read(Duration::from_secs(120))
        .redirects(0)
        .build())
}

/// Resmi uygulamayı cdn.uyap.gov.tr'den indirip kurar (yalnızca o adresten, HTTPS).
#[tauri::command(async)]
pub fn adalet_kur(app: tauri::AppHandle) -> Result<String, String> {
    {
        let mut k = KURULUYOR.lock().map_err(|e| e.to_string())?;
        if *k {
            return Err("Kurulum zaten sürüyor".into());
        }
        *k = true;
    }
    let sonuc = kur_ic(&app);
    if let Ok(mut k) = KURULUYOR.lock() {
        *k = false;
    }
    match &sonuc {
        Ok(s) => durum_yaz(&format!("Adalet E-İmza {} kuruldu", s)),
        Err(e) => durum_yaz(&format!("Kurulum hatası: {}", e)),
    }
    sonuc
}

fn kur_ic(app: &tauri::AppHandle) -> Result<String, String> {
    durum_yaz("Adalet E-İmza sürüm bilgisi alınıyor (cdn.uyap.gov.tr)…");
    let a = ajan()?;
    let js: serde_json::Value = a
        .get(SURUM_ADRESI)
        .call()
        .map_err(|e| format!("Sürüm bilgisi alınamadı: {}", e))?
        .into_json()
        .map_err(|e| e.to_string())?;
    let r = &js["releases"];
    // macOS paketi düz .zip'tir ve içindeki JAR tüm platformlarda aynıdır (ek araç gerekmeden açılır)
    let m = if r["mac_arm"].is_object() { &r["mac_arm"] } else { &r["mac_intel"] };
    let url = m["downloadUrl"].as_str().ok_or("downloadUrl yok")?.to_string();
    let surum = m["latestVersion"].as_str().unwrap_or("?").to_string();
    if !url.starts_with(IZINLI_ON_EK) {
        return Err(format!("Beklenmeyen indirme adresi: {}", url));
    }
    durum_yaz(&format!("Adalet E-İmza {} indiriliyor (cdn.uyap.gov.tr, ~80 MB)…", surum));
    let yan = a.get(&url).call().map_err(|e| format!("İndirme başarısız: {}", e))?;
    let toplam: u64 = yan.header("Content-Length").and_then(|s| s.parse().ok()).unwrap_or(0);
    let dizin = veri_dizini(app)?;
    let gecici_zip = dizin.join("paket.zip.tmp");
    {
        let mut okur = yan.into_reader();
        let mut f = fs::File::create(&gecici_zip).map_err(|e| e.to_string())?;
        let mut tampon = vec![0u8; 1 << 16];
        let mut sayac: u64 = 0;
        let mut son_yuzde = u64::MAX;
        loop {
            let n = okur.read(&mut tampon).map_err(|e| format!("İndirme kesildi: {}", e))?;
            if n == 0 {
                break;
            }
            f.write_all(&tampon[..n]).map_err(|e| e.to_string())?;
            sayac += n as u64;
            if toplam > 0 {
                let y = sayac * 100 / toplam;
                if y != son_yuzde {
                    son_yuzde = y;
                    durum_yaz(&format!("Adalet E-İmza {} indiriliyor… %{}", surum, y));
                }
            }
        }
    }
    durum_yaz("Paket açılıyor…");
    let dosya = fs::File::open(&gecici_zip).map_err(|e| e.to_string())?;
    let mut arsiv = zip::ZipArchive::new(dosya).map_err(|e| format!("Paket açılamadı: {}", e))?;
    let gecici_jar = dizin.join("eimza-tray.jar.tmp");
    let mut bulundu = false;
    for i in 0..arsiv.len() {
        let mut g = arsiv.by_index(i).map_err(|e| e.to_string())?;
        let ad = g.name().to_string();
        let kisa = ad.rsplit('/').next().unwrap_or("");
        if !g.is_dir() && !ad.contains("__MACOSX") && kisa.starts_with("eimza-tray") && kisa.ends_with(".jar") {
            let mut o = fs::File::create(&gecici_jar).map_err(|e| e.to_string())?;
            std::io::copy(&mut g, &mut o).map_err(|e| e.to_string())?;
            bulundu = true;
            break;
        }
    }
    let _ = fs::remove_file(&gecici_zip);
    if !bulundu {
        return Err("Pakette Adalet E-İmza uygulaması (eimza-tray-*.jar) bulunamadı".into());
    }
    let jar = jar_yolu(app)?;
    let _ = fs::remove_file(&jar);
    fs::rename(&gecici_jar, &jar).map_err(|e| e.to_string())?;
    fs::write(dizin.join("surum.txt"), &surum).map_err(|e| e.to_string())?;
    Ok(surum)
}

/// Başlatma ayarlarının sürümü: değişince CanEditor'un ÖNCEKİ sürümünün başlattığı Adalet süreci yeniden başlatılır
/// (ör. 3.18.7'nin başlattığı süreç Unicode PC/SC ajanı olmadan çalışıyordu: ArkSigner görünmüyordu).
const BASLATMA_SURUMU: &str = "2-unicode-pcsc";

/// CanEditor'un kendi başlattığı (jar yolu bizim veri dizinimizde olan) Adalet sürecini kapatır.
/// Bilgisayara ayrıca kurulmuş resmi Adalet E-İmza'ya dokunmaz.
#[cfg(windows)]
fn eski_sureci_kapat(jar: &std::path::Path) {
    use std::os::windows::process::CommandExt;
    let yol = duz_yol(jar).replace('\'', "''");
    let betik = format!(
        "Get-CimInstance Win32_Process -Filter \"Name='javaw.exe' OR Name='java.exe'\" | Where-Object {{ $_.CommandLine -and $_.CommandLine.Contains('{}') }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}",
        yol
    );
    let _ = Command::new("powershell")
        .args(["-NoProfile", "-NonInteractive", "-Command", &betik])
        .creation_flags(0x0800_0000)
        .status();
}
#[cfg(not(windows))]
fn eski_sureci_kapat(_jar: &std::path::Path) {}

/// Adalet E-İmza'yı başlatır (zaten 5975'te güncel bir servis çalışıyorsa dokunmaz).
#[tauri::command(async)]
pub fn adalet_baslat(app: tauri::AppHandle) -> Result<String, String> {
    if port_acik() {
        let dizin = veri_dizini(&app)?;
        let jar = jar_yolu(&app)?;
        let isaret = fs::read_to_string(dizin.join("calisan.txt")).unwrap_or_default();
        // Port bizim eski sürecimizdeyse (işaret eski/yok) ve bu pakette ajan varsa: yeni ayarlarla yeniden başlat
        if isaret.trim() != BASLATMA_SURUMU && ajan_yolu(&app).is_some() && jar.is_file() && !surec_canli() {
            durum_yaz("Adalet E-İmza yeni ayarlarla yeniden başlatılıyor…");
            eski_sureci_kapat(&jar);
            for _ in 0..30 {
                if !port_acik() {
                    break;
                }
                std::thread::sleep(Duration::from_millis(500));
            }
        }
        if port_acik() {
            return Ok("çalışıyor".into());
        }
    }
    if surec_canli() {
        return Ok("başlatılıyor".into());
    }
    let java = java_yolu(&app).ok_or("Gömülü Java bu pakette yok (CanEditor kurulumunu güncelleyin)")?;
    let jar = jar_yolu(&app)?;
    if !jar.is_file() {
        return Err("Adalet E-İmza kurulu değil".into());
    }
    let dizin = veri_dizini(&app)?;
    let ev = dizin.join("ev");
    let tmp = dizin.join("tmp");
    let _ = fs::create_dir_all(&ev);
    let _ = fs::create_dir_all(&tmp);
    let gunluk_yolu = dizin.join("adalet.log");
    if fs::metadata(&gunluk_yolu).map(|m| m.len() > 5_000_000).unwrap_or(false) {
        let _ = fs::remove_file(&gunluk_yolu);
    }
    let gunluk = fs::OpenOptions::new().create(true).append(true).open(&gunluk_yolu).map_err(|e| e.to_string())?;
    let gunluk2 = gunluk.try_clone().map_err(|e| e.to_string())?;
    let mut k = Command::new(&java);
    k.args([
        "-Xms64m",
        "-Xmx512m",
        "-XX:+UseSerialGC",
        "-Dfile.encoding=UTF-8",
        "-Djava.awt.headless=false",
        "--add-opens=java.smartcardio/sun.security.smartcardio=ALL-UNNAMED",
        "--add-exports=jdk.crypto.cryptoki/sun.security.pkcs11.wrapper=ALL-UNNAMED",
    ])
    .arg(format!("-Djava.io.tmpdir={}", tmp.display()))
    .arg("-jar")
    .arg(&jar)
    .current_dir(&ev)
    .stdin(Stdio::null())
    .stdout(Stdio::from(gunluk))
    .stderr(Stdio::from(gunluk2));
    // JAVA_TOOL_OPTIONS: kart tarayan alt Java süreçleri (probe) de aynı ayarları alır.
    // Ajan: JDK'nın Windows PC/SC sağlayıcısı Türkçe karakterli okuyucu adlarını bozar (ArkSigner:
    // "Microsoft Usbccid Akıllı Kart Okuyucusu (WUDF) 0" hiç açılamıyordu) → Unicode PC/SC sağlayıcısı.
    // Yollar boşluk içerebilir (Program Files, kullanıcı adı): tırnaklanır.
    let mut jto = format!("-Dfile.encoding=UTF-8 \"-Djava.io.tmpdir={}\"", duz_yol(&tmp));
    if let Some(a) = ajan_yolu(&app) {
        jto = format!("-javaagent:\"{}\" {}", duz_yol(&a), jto);
    }
    k.env("JAVA_TOOL_OPTIONS", jto);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        k.creation_flags(0x0800_0000); // CREATE_NO_WINDOW: siyah konsol penceresi açılmaz
    }
    let c = k.spawn().map_err(|e| format!("Java başlatılamadı: {}", e))?;
    if let Ok(mut g) = SUREC.lock() {
        *g = Some(c);
    }
    let _ = fs::write(dizin.join("calisan.txt"), BASLATMA_SURUMU);
    durum_yaz("Adalet E-İmza başlatılıyor…");
    Ok("başlatılıyor".into())
}

/// Resmi servise istek (WebView'den doğrudan erişilemez: servis CORS'u yalnızca uyap.gov.tr'ye açık).
#[tauri::command(async)]
pub fn adalet_istek(method: String, path: String, body: String) -> Result<String, String> {
    let izinli = path.starts_with("/api/v1/signature/getCertificates")
        || path.starts_with("/api/v1/docsignature/")
        || path.starts_with("/client/info");
    if !izinli || path.contains("..") {
        return Err("İzin verilmeyen istek".into());
    }
    if !port_acik() {
        return Err("Adalet E-İmza servisi çalışmıyor".into());
    }
    let a = ureq::AgentBuilder::new()
        .timeout_connect(Duration::from_secs(5))
        .timeout_read(Duration::from_secs(300)) // PIN girişi + imza
        .build();
    let url = format!("http://127.0.0.1:{}{}", PORT, path);
    let sonuc = if method.eq_ignore_ascii_case("POST") {
        a.post(&url).set("Content-Type", "application/json").send_string(&body)
    } else {
        a.get(&url).call()
    };
    match sonuc {
        Ok(r) => r.into_string().map_err(|e| e.to_string()),
        Err(ureq::Error::Status(_, r)) => r.into_string().map_err(|e| e.to_string()),
        Err(e) => Err(format!("Adalet E-İmza: {}", e)),
    }
}
