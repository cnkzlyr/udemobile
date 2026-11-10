//! CanEditor masaüstü e-imza köprüsü (Windows / macOS / Linux)
//!
//! Tasarım: CMS / CAdES-BES imza yapısı TÜM platformlarda ortak olan `esign.js` içinde üretilir.
//! Bu modül yalnızca platforma özgü "ham" işlemleri sağlar:
//!   * `pkcs11_list`  — takılı akıllı kart / token üzerindeki imza sertifikalarını listeler
//!   * `pkcs11_sign`  — PIN ile oturum açıp imzalı öznitelikleri (signedAttrs) kartta imzalar
//!   * `http_post`    — UYAP mobil imza SOAP servisine istek (WebView CORS kısıtını aşmak için)
//!
//! Sürücüler: Türkiye'de kullanılan nitelikli e-imza kartlarının PKCS#11 kütüphaneleri
//! (Havelsan UYAP Editörü smartcard-config.xml ile aynı liste) işletim sistemine göre otomatik aranır.
//! Kütüphane bulunamazsa kullanıcıya sürücü kurulum bağlantıları gösterilir.

use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
use cryptoki::context::{CInitializeArgs, Pkcs11};
use cryptoki::mechanism::Mechanism;
use cryptoki::object::{Attribute, AttributeType, KeyType, ObjectClass};
use cryptoki::session::UserType;
use cryptoki::types::AuthPin;
use std::path::{Path, PathBuf};
use std::time::Duration;

/// Havelsan UYAP smartcard-config.xml + yaygın Türk e-imza sağlayıcı sürücüleri
const LIB_BASE_NAMES: &[&str] = &[
    "akisp11",      // TÜBİTAK AKİS (Kamu SM, E-Güven, TürkTrust, E-Tuğra AKİS kartları)
    "eTPKCS11",     // SafeNet / Aladdin eToken (E-Tuğra, e-imzaTR)
    "eTPkcs11",
    "aetpkss1",     // SafeSign (A.E.T.)
    "cmp11",        // CardOS (Atos)
    "dkck201",      // Datakey
    "gclib",        // Gemplus
    "siecap11",     // T-Kart
    "iidp11",       // Net-iD
    "asepkcs",      // Athena / NXP
    "IDPrimePKCS11", // Thales IDPrime
    "idprimepkcs11",
    "ArkSignerPkcs11", // ArkSigner
    "arksigner-pkcs11",
    "opensc-pkcs11", // OpenSC (genel)
];

fn candidate_dirs() -> Vec<PathBuf> {
    let mut v: Vec<PathBuf> = Vec::new();
    if cfg!(windows) {
        let win = std::env::var("SystemRoot").unwrap_or_else(|_| "C:\\Windows".into());
        v.push(PathBuf::from(&win).join("System32"));
        v.push(PathBuf::from("C:\\Program Files\\OpenSC Project\\OpenSC\\pkcs11"));
        v.push(PathBuf::from("C:\\Program Files\\Akis"));
        v.push(PathBuf::from("C:\\Program Files\\ArkSigner"));
        v.push(PathBuf::from("C:\\Program Files (x86)\\ArkSigner"));
        v.push(PathBuf::from("C:\\Program Files\\SafeNet\\Authentication\\SAC\\x64"));
    } else if cfg!(target_os = "macos") {
        for d in ["/usr/local/lib", "/opt/homebrew/lib", "/usr/lib", "/Library/OpenSC/lib", "/Library/OpenSC/lib/pkcs11",
                  "/Library/Frameworks/eToken.framework/Versions/A", "/Applications/AKIS.app/Contents/MacOS", "/usr/local/AKIS"] {
            v.push(PathBuf::from(d));
        }
    } else {
        for d in ["/usr/lib", "/usr/lib64", "/usr/lib/x86_64-linux-gnu", "/usr/lib/aarch64-linux-gnu", "/usr/local/lib",
                  "/usr/lib/pkcs11", "/usr/lib/x86_64-linux-gnu/pkcs11", "/usr/lib64/pkcs11", "/opt/akis/lib", "/usr/lib/akis",
                  "/opt/arksigner/lib", "/opt/safenet/lib"] {
            v.push(PathBuf::from(d));
        }
    }
    v
}

fn file_names(base: &str) -> Vec<String> {
    if cfg!(windows) {
        vec![format!("{}.dll", base)]
    } else if cfg!(target_os = "macos") {
        vec![format!("lib{}.dylib", base), format!("{}.dylib", base), format!("{}.so", base), format!("lib{}.so", base)]
    } else {
        vec![format!("lib{}.so", base), format!("{}.so", base)]
    }
}

/// Sistemde bulunan PKCS#11 kütüphaneleri (öncelik sırasıyla, tekrarsız)
pub fn find_libraries(extra: Option<&str>) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    let mut push = |p: &Path| {
        let s = p.to_string_lossy().to_string();
        if p.is_file() && !out.iter().any(|x| x.eq_ignore_ascii_case(&s)) {
            out.push(s);
        }
    };
    if let Some(e) = extra {
        if !e.trim().is_empty() {
            push(Path::new(e.trim()));
        }
    }
    if let Ok(e) = std::env::var("CANEDITOR_PKCS11") {
        push(Path::new(&e));
    }
    let dirs = candidate_dirs();
    for base in LIB_BASE_NAMES {
        for d in &dirs {
            for f in file_names(base) {
                push(&d.join(f));
            }
        }
    }
    // Ek tarama: adında "pkcs11" / "p11" geçen kütüphaneler (bilinmeyen sağlayıcılar için)
    for d in &dirs {
        if let Ok(rd) = std::fs::read_dir(d) {
            for ent in rd.flatten() {
                let n = ent.file_name().to_string_lossy().to_lowercase();
                let lib_ext = n.ends_with(".dll") || n.ends_with(".so") || n.ends_with(".dylib");
                if lib_ext && (n.contains("pkcs11") || n.contains("p11")) && !n.contains("p11-kit") && !n.contains("pkcs11-spy") {
                    push(&ent.path());
                }
            }
        }
    }
    out
}

#[derive(serde::Serialize, Clone)]
pub struct CardCert {
    pub lib: String,
    pub slot: u64,
    #[serde(rename = "keyId")]
    pub key_id: String,
    pub label: String,
    #[serde(rename = "tokenLabel")]
    pub token_label: String,
    pub reader: String,
    #[serde(rename = "certB64")]
    pub cert_b64: String,
}

#[derive(serde::Serialize)]
pub struct CardList {
    pub cards: Vec<CardCert>,
    pub libs: Vec<String>,
    pub message: String,
}

fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{:02x}", x)).collect()
}
fn unhex(s: &str) -> Vec<u8> {
    (0..s.len() / 2).filter_map(|i| u8::from_str_radix(&s[i * 2..i * 2 + 2], 16).ok()).collect()
}

fn open_lib(lib: &str) -> Result<Pkcs11, String> {
    let p = Pkcs11::new(lib).map_err(|e| format!("{} yüklenemedi: {}", lib, e))?;
    match p.initialize(CInitializeArgs::OsThreads) {
        Ok(_) => Ok(p),
        Err(e) => {
            let s = e.to_string();
            if s.contains("AlreadyInitialized") || s.contains("ALREADY_INITIALIZED") {
                Ok(p)
            } else {
                Err(format!("{} başlatılamadı: {}", lib, s))
            }
        }
    }
}

fn list_in_lib(lib: &str) -> Result<Vec<CardCert>, String> {
    let p = open_lib(lib)?;
    let mut out = Vec::new();
    let slots = p.get_slots_with_token().map_err(|e| e.to_string())?;
    for slot in slots {
        let token_label = p.get_token_info(slot).map(|t| t.label().trim().to_string()).unwrap_or_default();
        let reader = p.get_slot_info(slot).map(|s| s.slot_description().trim().to_string()).unwrap_or_default();
        let session = match p.open_ro_session(slot) {
            Ok(s) => s,
            Err(_) => continue,
        };
        let certs = session
            .find_objects(&[Attribute::Class(ObjectClass::CERTIFICATE)])
            .unwrap_or_default();
        for h in certs {
            let attrs = session
                .get_attributes(h, &[AttributeType::Value, AttributeType::Id, AttributeType::Label])
                .unwrap_or_default();
            let mut value = Vec::new();
            let mut id = Vec::new();
            let mut label = String::new();
            for a in attrs {
                match a {
                    Attribute::Value(v) => value = v,
                    Attribute::Id(v) => id = v,
                    Attribute::Label(v) => label = String::from_utf8_lossy(&v).trim().to_string(),
                    _ => {}
                }
            }
            if value.is_empty() {
                continue;
            }
            out.push(CardCert {
                lib: lib.to_string(),
                slot: slot.id(),
                key_id: hex(&id),
                label,
                token_label: token_label.clone(),
                reader: reader.clone(),
                cert_b64: B64.encode(&value),
            });
        }
    }
    Ok(out)
}

/// Takılı kartlardaki sertifikaları listeler (tüm bulunan sürücüler denenir)
#[tauri::command(async)]
pub fn pkcs11_list(lib_path: Option<String>) -> Result<CardList, String> {
    let libs = find_libraries(lib_path.as_deref());
    if libs.is_empty() {
        return Ok(CardList {
            cards: vec![],
            libs,
            message: driver_help(),
        });
    }
    let mut cards = Vec::new();
    let mut errors = Vec::new();
    for lib in &libs {
        match list_in_lib(lib) {
            Ok(mut c) => cards.append(&mut c),
            Err(e) => errors.push(e),
        }
        if !cards.is_empty() {
            break; // ilk kartı bulan sürücü yeterli (aynı kart birden çok sürücüde tekrar görünmesin)
        }
    }
    let message = if cards.is_empty() {
        format!(
            "Takılı e-imza kartı bulunamadı. Kartı/token'ı takıp birkaç saniye bekleyin.\nDenenen sürücüler: {}{}",
            libs.iter().map(|l| Path::new(l).file_name().map(|f| f.to_string_lossy().to_string()).unwrap_or_default()).collect::<Vec<_>>().join(", "),
            if errors.is_empty() { String::new() } else { format!("\nAyrıntı: {}", errors.join(" | ")) }
        )
    } else {
        String::new()
    };
    Ok(CardList { cards, libs, message })
}

fn driver_help() -> String {
    let os = if cfg!(windows) { "Windows" } else if cfg!(target_os = "macos") { "macOS" } else { "Linux" };
    format!(
        "Bu bilgisayarda e-imza kartı sürücüsü (PKCS#11) bulunamadı ({}).\n\
         Kartınızı veren kuruluşun sürücüsünü kurun:\n\
         • AKİS (Kamu SM / E-Güven / TürkTrust): https://kamusm.bilgem.tubitak.gov.tr/islemler/surucu_yukleme_servisi/\n\
         • E-Tuğra / SafeNet eToken: https://www.e-tugra.com.tr/surucu-yukleme\n\
         • e-imzaTR: https://www.e-imzatr.com/destek\n\
         • ArkSigner: https://www.arksigner.com/indir\n\
         Kurulumdan sonra kartı çıkarıp takın. Özel bir sürücü yolu varsa İmza penceresinden 'Sürücü yolu' alanına girebilirsiniz.",
        os
    )
}

const DIGESTINFO_SHA256: [u8; 19] = [0x30, 0x31, 0x30, 0x0d, 0x06, 0x09, 0x60, 0x86, 0x48, 0x01, 0x65, 0x03, 0x04, 0x02, 0x01, 0x05, 0x00, 0x04, 0x20];

fn friendly(e: &str) -> String {
    if e.contains("PinIncorrect") || e.contains("PIN_INCORRECT") {
        "Hatalı PIN girildi. Tekrar yanlış girilirse kart bloke olabilir!".into()
    } else if e.contains("PinLocked") || e.contains("PIN_LOCKED") {
        "E-imza PIN'iniz bloke olmuş. Sertifika sağlayıcınızla görüşün.".into()
    } else if e.contains("PinLenRange") || e.contains("PIN_LEN_RANGE") {
        "PIN uzunluğu geçersiz.".into()
    } else if e.contains("TokenNotPresent") || e.contains("DeviceRemoved") {
        "Kart çıkarıldı veya okunamıyor.".into()
    } else {
        e.to_string()
    }
}

/// signedAttrs (DER SET) verisini kartta imzalar. RSA: CKM_SHA256_RSA_PKCS (desteklenmezse CKM_RSA_PKCS + DigestInfo),
/// EC: CKM_ECDSA (SHA-256 özeti üzerinde; ham r||s döner, esign.js DER'e çevirir).
#[tauri::command(async)]
pub fn pkcs11_sign(
    lib_path: String,
    slot: u64,
    key_id: String,
    pin: String,
    data_b64: String,
    digest_b64: String,
    key_type: Option<String>,
) -> Result<String, String> {
    let data = B64.decode(data_b64.as_bytes()).map_err(|e| e.to_string())?;
    let digest = B64.decode(digest_b64.as_bytes()).map_err(|e| e.to_string())?;
    let p = open_lib(&lib_path)?;
    let slots = p.get_slots_with_token().map_err(|e| e.to_string())?;
    let s = slots
        .into_iter()
        .find(|s| s.id() == slot)
        .ok_or_else(|| "Kart bulunamadı (çıkarılmış olabilir).".to_string())?;
    let session = p.open_ro_session(s).map_err(|e| friendly(&e.to_string()))?;
    session
        .login(UserType::User, Some(&AuthPin::new(pin)))
        .map_err(|e| friendly(&e.to_string()))?;
    let id = unhex(&key_id);
    let mut tmpl = vec![Attribute::Class(ObjectClass::PRIVATE_KEY)];
    if !id.is_empty() {
        tmpl.push(Attribute::Id(id));
    }
    let keys = session.find_objects(&tmpl).map_err(|e| e.to_string())?;
    let key = *keys
        .first()
        .ok_or_else(|| "Sertifikaya ait özel anahtar kartta bulunamadı.".to_string())?;
    let mut is_ec = key_type.as_deref() == Some("EC");
    if let Ok(attrs) = session.get_attributes(key, &[AttributeType::KeyType]) {
        for a in attrs {
            if let Attribute::KeyType(kt) = a {
                is_ec = kt == KeyType::EC;
            }
        }
    }
    let sig = if is_ec {
        session.sign(&Mechanism::Ecdsa, key, &digest).map_err(|e| friendly(&e.to_string()))?
    } else {
        match session.sign(&Mechanism::Sha256RsaPkcs, key, &data) {
            Ok(v) => v,
            Err(_) => {
                let mut di = DIGESTINFO_SHA256.to_vec();
                di.extend_from_slice(&digest);
                session.sign(&Mechanism::RsaPkcs, key, &di).map_err(|e| friendly(&e.to_string()))?
            }
        }
    };
    let _ = session.logout();
    Ok(B64.encode(sig))
}

/// UYAP mobil imza SOAP isteği (yalnızca UYAP alan adına izin verilir)
#[tauri::command(async)]
pub fn http_post(url: String, body: String, content_type: String, soap_action: String) -> Result<String, String> {
    let allowed = url.starts_with("http://vatandas.uyap.gov.tr/") || url.starts_with("https://vatandas.uyap.gov.tr/");
    if !allowed {
        return Err("İzin verilmeyen adres".into());
    }
    let agent = ureq::AgentBuilder::new()
        .timeout_connect(Duration::from_secs(20))
        .timeout_read(Duration::from_secs(200))
        .build();
    // Havelsan Doküman Editörü (Apache Axis 1.3) ile aynı başlıklar
    let mut req = agent
        .post(&url)
        .set("Content-Type", &content_type)
        .set("Accept", "application/soap+xml, application/dime, multipart/related, text/*")
        .set("User-Agent", "Axis/1.3")
        .set("Cache-Control", "no-cache")
        .set("Pragma", "no-cache");
    if !soap_action.is_empty() {
        req = req.set("SOAPAction", &soap_action);
    }
    match req.send_string(&body) {
        Ok(r) => r.into_string().map_err(|e| e.to_string()),
        Err(ureq::Error::Status(_, r)) => r.into_string().map_err(|e| e.to_string()),
        Err(e) => Err(format!("UYAP mobil imza servisine bağlanılamadı: {}", e)),
    }
}
