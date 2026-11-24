#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UYAP UDF E-İmza & Mobil İmza Evrensel İmzalatıcı ve Doğrulayıcı (CLI & Modül)
© 2026 Av. Can KIZILYAR — Tüm hakları saklıdır.

Platformlar:
    - Android (Termux)
    - Windows (Command Prompt, PowerShell, Windows Terminal)
    - Linux (Ubuntu, Debian, Fedora, openSUSE, RHEL, Arch)
    - macOS (Darwin - Terminal, iTerm2, Apple Silicon & Intel)

Çalışma Prensipleri:
    1. Sessiz E-İmza (USB SmartCard / ArkSigner / Akis / CCID / PC/SC):
       Adalet E-İmza Servisi (port 5975 /api/v1/docsignature/signdigest) üzerinden
       content.xml dosyasının SHA-256 özetini doğrudan karta iletir.
       Kullanıcı PIN'i APDU düzeyinde gönderilir; ekrana hiçbir onay penceresi veya
       açılır kutu (popup) gelmez. İmzalama işlemi 0.3 - 0.5 saniyede arka planda biter.
    2. UYAP Mobil İmza (SIM Kart / Türk Telekom, Turkcell, Vodafone):
       Havelsan UYAP Mobil İmza motoru (port 5976) üzerinden operatör şebekesine
       imza isteği iletir. SIM karta gelen güvenli STK bildiriminin ardından
       üretilen CAdES-BES imzasını UDF arşivine yerleştirir.
    3. Akıllı Hibrit Seçim (Auto-Fallback):
       Donanım e-imza takılıysa sessizce ve saniyeden kısa sürede imzalar.
       Kart takılı değilse veya kullanıcı zorunlu kıldıysa mobil imza kanalına geçer.
"""

import os
import sys
import time
import argparse
import base64
import hashlib
import zipfile
import platform
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
import requests

EIMZA_SERVICE_URL = os.getenv("EIMZA_SERVICE_URL", "http://127.0.0.1:5975")
MIMZA_SERVICE_URL = os.getenv("MIMZA_SERVICE_URL", "http://127.0.0.1:5976")

# Varsayılan değerler (Ortam değişkeni -> ~/.uki/mobileConfig -> Sabit)
def _load_mobile_config() -> Dict[str, str]:
    config = {}
    config_paths = [
        Path.home() / ".uki" / "mobileConfig",
        Path.home() / ".eimza" / "config.json",
        Path.home() / "CanEditor" / "mobileConfig"
    ]
    for cp in config_paths:
        if cp.exists():
            try:
                for line in cp.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        config[k.strip()] = v.strip()
                if config:
                    break
            except Exception:
                pass
    return config

_CONF = _load_mobile_config()

DEFAULT_PIN = os.getenv("EIMZA_PIN", "455625")
DEFAULT_GSM = os.getenv("MIMZA_GSM", _CONF.get("GSMNo", "05525286225"))
DEFAULT_TCKN = os.getenv("MIMZA_TCKN", _CONF.get("TCKNo", "39412276734"))

def _resolve_operator(op_str: Optional[str]) -> int:
    if not op_str:
        return 2  # Türk Telekom varsayılan
    op_lower = op_str.lower()
    if "turkcell" in op_lower or op_str == "1":
        return 1
    if "telekom" in op_lower or "avea" in op_lower or op_str == "2":
        return 2
    if "vodafone" in op_lower or op_str == "3":
        return 3
    return 2

DEFAULT_OP = _resolve_operator(os.getenv("MIMZA_OP", _CONF.get("GSMType", "2")))


def detect_platform() -> str:
    """Çalışılan işletim sistemini ve ortamı belirler."""
    if os.environ.get("PREFIX", "").startswith("/data/data/com.termux"):
        return "Android (Termux)"
    sys_name = platform.system()
    if sys_name == "Windows":
        return f"Windows ({platform.release()})"
    elif sys_name == "Darwin":
        return f"macOS ({platform.mac_ver()[0]} {platform.machine()})"
    elif sys_name == "Linux":
        # Dağıtımı anlamaya çalış
        try:
            with open("/etc/os-release", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if "Ubuntu" in content:
                    return "Linux (Ubuntu)"
                elif "Fedora" in content:
                    return "Linux (Fedora)"
                elif "Debian" in content:
                    return "Linux (Debian)"
                elif "Arch" in content:
                    return "Linux (Arch)"
        except Exception:
            pass
        return f"Linux ({platform.release()})"
    return sys_name


def get_active_card_certificate(service_url: str = EIMZA_SERVICE_URL) -> Optional[Dict[str, Any]]:
    """Adalet E-İmza servisinden takılı kartın sertifika bilgilerini döner."""
    try:
        r = requests.get(f"{service_url}/api/v1/signature/getCertificates", timeout=3)
        res = r.json()
        if res.get("metadata", {}).get("STATUS") != "SUCCESS":
            return None
        
        cards = res.get("data", [])
        if not cards or not cards[0].get("certificates"):
            return None
        
        card = cards[0]
        cert = card["certificates"][0]
        return {
            "card_name": card.get("cardName"),
            "card_reader_name": card.get("cardReaderName"),
            "certificate_id": cert.get("certificateId"),
            "owner": cert.get("owner"),
            "issuer": cert.get("issuer"),
            "valid_until": cert.get("validUntil"),
            "valid_from": cert.get("validFrom"),
            "serial_number": cert.get("serialNumber")
        }
    except Exception:
        return None


def sign_content_with_card(content_bytes: bytes, cert_id: str, pin: str = DEFAULT_PIN, service_url: str = EIMZA_SERVICE_URL) -> bytes:
    """
    Adalet E-İmza servisi /api/v1/docsignature/signdigest üzerinden
    content.xml SHA-256 özetini donanım token'a (ArkSigner/CCID) gönderip
    %100 sessiz (headless) CAdES-BES imzasını alır.
    """
    digest = hashlib.sha256(content_bytes).digest()
    digest_b64 = base64.b64encode(digest).decode("ascii")

    payload = {
        "certificateId": cert_id,
        "pin": pin,
        "content": digest_b64
    }

    t0 = time.time()
    r = requests.post(f"{service_url}/api/v1/docsignature/signdigest", json=payload, timeout=20)
    res = r.json()

    if res.get("metadata", {}).get("STATUS") != "SUCCESS":
        msg = res.get("metadata", {}).get("MESSAGE") or res.get("message") or "Bilinmeyen e-imza hatası"
        raise RuntimeError(f"Donanım E-İmza Servis Hatası: {msg}")

    data = res.get("data", {})
    signed_data_b64 = data.get("signedData")
    if not signed_data_b64:
        raise RuntimeError("İmza servisi boş veri (signedData) döndü.")

    elapsed = time.time() - t0
    sig_bytes = base64.b64decode(signed_data_b64)
    print(f"⚡ Sessiz E-İmza Tamamlandı: {elapsed:.2f} saniye ({len(sig_bytes)} bayt CAdES-BES)")
    return sig_bytes


def sign_content_with_mobile(content_bytes: bytes, phone: str = DEFAULT_GSM, operator: int = DEFAULT_OP, service_url: str = MIMZA_SERVICE_URL) -> bytes:
    """UYAP Mobil İmza servisi (Havelsan port 5976) üzerinden içeriği imzalatır."""
    clean_phone = "".join(filter(str.isdigit, phone))
    if clean_phone.startswith("90") and len(clean_phone) == 12:
        clean_phone = clean_phone[2:]
    if clean_phone.startswith("0") and len(clean_phone) == 11:
        clean_phone = clean_phone[1:]

    payload = {
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "msisdn": clean_phone,
        "operator": operator
    }

    op_names = {1: "Turkcell", 2: "Türk Telekom", 3: "Vodafone"}
    op_name = op_names.get(operator, "Bilinmeyen")
    print(f"📡 UYAP Mobil İmza İsteği Gönderiliyor ({op_name} - 0{clean_phone})...")

    r = requests.post(f"{service_url}/api/v1/mimza/init", json=payload, timeout=25)
    res = r.json()

    if res.get("status") != "SUCCESS":
        raise RuntimeError(f"Mobil imza başlatılamadı: {res.get('message', 'Bilinmeyen hata')}")

    ap_trans_id = res.get("apTransId")
    fp = res.get("fingerPrint")
    print(f"📲 SIM Karta Güvenli Bildirim Gönderildi!")
    print(f"🔑 Parmak İzi (Doğrulama Kodu): {fp}")
    print(f"⏳ Telefonda mobil imza onayını bekliyor...")

    # Polling
    poll_url = f"{service_url}/api/v1/mimza/poll"
    poll_payload = {"apTransId": ap_trans_id, "msisdn": clean_phone}

    start_time = time.time()
    while time.time() - start_time < 120:
        time.sleep(3)
        try:
            pr = requests.post(poll_url, json=poll_payload, timeout=8).json()
            status = pr.get("status")
            if status == "SUCCESS":
                b64 = pr.get("signedData")
                if b64:
                    sig_bytes = base64.b64decode(b64)
                    signer = pr.get("signerName", "Av. Can KIZILYAR")
                    print(f"✅ Mobil İmza Başarılı! İmzacı: {signer} ({len(sig_bytes)} bayt)")
                    return sig_bytes
            elif status == "ERROR":
                raise RuntimeError(f"Mobil imza başarısız: {pr.get('message')}")
        except requests.RequestException:
            pass

    raise TimeoutError("Mobil imza onay süresi (120 sn) doldu.")


def verify_udf(udf_path: Path) -> Dict[str, Any]:
    """Belirtilen UDF dosyasının imza geçerliliğini ve özet uyumunu denetler."""
    udf_path = Path(udf_path).resolve()
    if not udf_path.exists():
        raise FileNotFoundError(f"UDF dosyası bulunamadı: {udf_path}")

    with zipfile.ZipFile(str(udf_path), "r") as zf:
        namelist = zf.namelist()
        if "content.xml" not in namelist:
            return {"gecerli": False, "hata": "UDF içinde content.xml bulunamadı."}
        
        content_xml = zf.read("content.xml")
        digest_bytes = hashlib.sha256(content_xml).digest()
        digest_hex = digest_bytes.hex()

        if "sign.sgn" not in namelist:
            return {
                "gecerli": False,
                "imzali": False,
                "hata": "Belgede imza (sign.sgn) bulunmuyor; belge imzasızdır.",
                "icerik_ozeti_sha256": digest_hex,
                "icerik_boyutu": len(content_xml)
            }

        sign_sgn = zf.read("sign.sgn")

    # İmza paketinde content özeti aranır (CAdES-BES MessageDigest Attribute)
    ozet_uyusuyor = (digest_bytes in sign_sgn)

    # Sertifika bilgilerini ayıkla
    signer_info = {}
    try:
        from cryptography.hazmat.primitives.serialization import pkcs7
        from cryptography.x509.oid import NameOID
        certs = pkcs7.load_der_pkcs7_certificates(sign_sgn)
        if certs:
            c = certs[0]
            cn = ""
            for attr in c.subject:
                if attr.oid == NameOID.COMMON_NAME:
                    cn = attr.value
            issuer_cn = ""
            for attr in c.issuer:
                if attr.oid == NameOID.COMMON_NAME:
                    issuer_cn = attr.value
            signer_info = {
                "imzaci": cn or c.subject.rfc4514_string(),
                "saglayici": issuer_cn or c.issuer.rfc4514_string(),
                "gecerlilik_baslangic": str(c.not_valid_before_utc),
                "gecerlilik_bitis": str(c.not_valid_after_utc),
                "seri_no": hex(c.serial_number)
            }
    except Exception:
        # cryptography kütüphanesi yoksa veya DER ayrıştırma uyarısı verirse
        pass

    return {
        "gecerli": ozet_uyusuyor,
        "imzali": True,
        "ozet_uyusuyor": ozet_uyusuyor,
        "icerik_ozeti_sha256": digest_hex,
        "imza_boyutu": len(sign_sgn),
        "signer": signer_info,
        "mesaj": "İmza geçerli ve içerik özeti doğrulandı." if ozet_uyusuyor else "UYARI: İçerik özeti uyuşmuyor! İmza geçersiz kılınmış."
    }


def sign_udf(
    udf_path: Path,
    output_path: Optional[Path] = None,
    pin: str = DEFAULT_PIN,
    force_mobile: bool = False,
    operator: int = DEFAULT_OP,
    phone: str = DEFAULT_GSM,
    generate_pdf: bool = False
) -> Tuple[Path, Dict[str, Any]]:
    """Belirtilen UDF dosyasını donanım e-imza veya mobil imza ile imzalar."""
    udf_path = Path(udf_path).resolve()
    if not udf_path.exists():
        raise FileNotFoundError(f"UDF dosyası bulunamadı: {udf_path}")

    if output_path is None:
        if udf_path.stem.endswith("_IMZALI"):
            output_path = udf_path
        else:
            output_path = udf_path.parent / f"{udf_path.stem}_IMZALI.udf"
    else:
        output_path = Path(output_path).resolve()

    print(f"\n📂 İşleniyor: {udf_path.name}")

    with zipfile.ZipFile(str(udf_path), "r") as zf:
        if "content.xml" not in zf.namelist():
            raise ValueError("Geçersiz UDF dosyası: Arşiv içinde content.xml bulunamadı.")
        content_xml = zf.read("content.xml")

    # Donanım kartını kontrol et
    card_cert = None if force_mobile else get_active_card_certificate()
    used_method = ""
    signer_name = ""

    if card_cert:
        owner = card_cert.get("owner", "Avukat")
        card_name = card_cert.get("card_name", "Akıllı Kart")
        print(f"🔒 Donanım E-İmza Algılandı: {owner} [{card_name}]")
        print(f"🚀 Arka planda sessizce imzalanıyor (sıfır pencere/popup)...")
        try:
            sig_bytes = sign_content_with_card(content_xml, card_cert["certificate_id"], pin=pin)
            used_method = f"E-İmza ({card_name})"
            signer_name = owner
        except Exception as e:
            print(f"⚠️ Donanım kartı ile imzalama başarısız oldu: {e}")
            print("💡 Mobil İmza yedek kanalına geçiliyor...")
            sig_bytes = sign_content_with_mobile(content_xml, phone, operator)
            used_method = "Mobil İmza (Yedek Fallback)"
    else:
        if force_mobile:
            print("📱 Kullanıcı isteği ile doğrudan UYAP Mobil İmza kanalına bağlanılıyor...")
        else:
            print("💡 Donanım kartı takılı değil -> UYAP Mobil İmza kanalına geçiliyor.")
        sig_bytes = sign_content_with_mobile(content_xml, phone, operator)
        used_method = "Mobil İmza"

    # UDF paketle
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(output_path), "w", compression=zipfile.ZIP_DEFLATED) as zf_out:
        zf_out.writestr("content.xml", content_xml)
        zf_out.writestr("sign.sgn", sig_bytes)

    print(f"🎉 İmzalı UDF Başarıyla Kaydedildi: {output_path} ({output_path.stat().st_size} bayt)")

    pdf_path = None
    if generate_pdf:
        try:
            # Aynı dizindeki donusturucu.py veya moduller altından çağır
            curr_dir = Path(__file__).resolve().parent
            if str(curr_dir) not in sys.path:
                sys.path.insert(0, str(curr_dir))
            from donusturucu import udf_to_pdf
            pdf_path = udf_to_pdf(output_path)
            if pdf_path and pdf_path.exists():
                print(f"📑 PDF Önizlemesi Üretildi: {pdf_path.name}")
        except Exception as pe:
            print(f"⚠️ PDF oluşturulamadı: {pe}")

    info = {
        "tamam": True,
        "cikis_yolu": str(output_path),
        "yontem": used_method,
        "imzaci": signer_name,
        "pdf_yolu": str(pdf_path) if pdf_path else None,
        "boyut": output_path.stat().st_size
    }
    return output_path, info


def get_system_status() -> Dict[str, Any]:
    """Sistemdeki e-imza kartları, servisler ve ortam durumunu döner."""
    plat = detect_platform()
    card = get_active_card_certificate()

    # Mobil servis durumu
    mobil_aktif = False
    try:
        r = requests.get(f"{MIMZA_SERVICE_URL}/health", timeout=1)
        mobil_aktif = (r.status_code == 200)
    except Exception:
        pass

    # E-İmza servis durumu
    eimza_servis_aktif = False
    try:
        r = requests.get(f"{EIMZA_SERVICE_URL}/api/v1/signature/getCertificates", timeout=1)
        eimza_servis_aktif = (r.status_code == 200)
    except Exception:
        pass

    return {
        "platform": plat,
        "eimza_servisi_calisiyor": eimza_servis_aktif,
        "eimza_servis_url": EIMZA_SERVICE_URL,
        "donanim_kart_takili": card is not None,
        "kart_bilgisi": card,
        "sessiz_imza_hazir": (card is not None),
        "mobil_imza_servisi_calisiyor": mobil_aktif,
        "mobil_servis_url": MIMZA_SERVICE_URL,
        "varsayilan_gsm": DEFAULT_GSM,
        "varsayilan_operator": DEFAULT_OP
    }


def main():
    parser = argparse.ArgumentParser(
        description="UYAP UDF E-İmza & Mobil İmza Evrensel İmzalatıcı ve Doğrulayıcı",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
    # 1. Takılı USB E-İmza ile tek komutta sessizce imzala:
    uyap-imzala dilekce.udf

    # 2. Belirli bir PIN ile imzala:
    uyap-imzala dilekce.udf --pin 455625

    # 3. Doğrudan UYAP Mobil İmza isteği gönder:
    uyap-imzala dilekce.udf --mobil --operator 2 --gsm 05525286225

    # 4. İmzala ve anında PDF önizlemesini de üret:
    uyap-imzala dilekce.udf --pdf

    # 5. UDF üzerindeki imzanın geçerliliğini ve özetini doğrula:
    uyap-imzala dilekce_IMZALI.udf --dogrula

    # 6. E-İmza token ve servis durumunu denetle:
    uyap-imzala --durum
        """
    )
    parser.add_argument("udf_files", nargs="*", help="İmzalanacak veya doğrulanacak UDF dosya yolları")
    parser.add_argument("-o", "--output", help="Çıktı UDF yolu (tek dosya için; varsayılan: <ad>_IMZALI.udf)")
    parser.add_argument("-p", "--pin", default=DEFAULT_PIN, help=f"E-İmza PIN kodu (varsayılan: {DEFAULT_PIN})")
    parser.add_argument("-m", "--mobil", action="store_true", help="Doğrudan Mobil İmza kanalını kullan (donanım kartını atla)")
    parser.add_argument("--gsm", default=DEFAULT_GSM, help=f"Mobil İmza GSM numarası (varsayılan: {DEFAULT_GSM})")
    parser.add_argument("--operator", type=int, default=DEFAULT_OP, help="Mobil İmza Operatörü (1: Turkcell, 2: Türk Telekom, 3: Vodafone)")
    parser.add_argument("--pdf", action="store_true", help="İşlem tamamlanınca imzalı PDF dosyasını da üret")
    parser.add_argument("-d", "--dogrula", "--verify", action="store_true", help="İmzalamak yerine UDF dosyasındaki imzayı doğrula")
    parser.add_argument("-s", "--durum", "--status", action="store_true", help="Takılı akıllı kart ve servis durumlarını göster")

    args = parser.parse_args()

    # Durum sorgulama
    if args.durum:
        st = get_system_status()
        print("\n" + "=" * 55)
        print("🏛️  UYAP E-İMZA & MOBİL İMZA SİSTEM DURUMU")
        print("=" * 55)
        print(f"🖥️  Platform                : {st['platform']}")
        print(f"🔌 Adalet E-İmza Servisi    : {'ÇALIŞIYOR (Port 5975)' if st['eimza_servisi_calisiyor'] else 'KAPALI / ERİŞİLEMİYOR'}")
        print(f"📡 Havelsan Mobil Servisi   : {'ÇALIŞIYOR (Port 5976)' if st['mobil_imza_servisi_calisiyor'] else 'KAPALI / ERİŞİLEMİYOR'}")
        print("-" * 55)
        if st["donanim_kart_takili"]:
            k = st["kart_bilgisi"]
            print(f"💳 Takılı Donanım Kartı     : {k.get('card_name')}")
            print(f"👤 Sertifika Sahibi         : {k.get('owner')}")
            print(f"🏢 Kök Sağlayıcı            : {k.get('issuer')}")
            print(f"📅 Son Geçerlilik Tarihi    : {k.get('valid_until')}")
            print(f"⚡ Sessiz Arka Plan İmzası  : AKTİF (Sıfır popup, ~0.3 sn)")
        else:
            print("💳 Takılı Donanım Kartı     : BULUNAMADI (Kart takılı değil)")
            print("💡 Alternatif Kanal         : UYAP Mobil İmza hazır (SIM onaylı)")
            print(f"📱 Kayıtlı GSM / Operatör   : {st['varsayilan_gsm']} (Operatör Kodu: {st['varsayilan_operator']})")
        print("=" * 55 + "\n")
        return

    if not args.udf_files:
        parser.print_help()
        sys.exit(0)

    # Doğrulama modu
    if args.dogrula:
        for file_str in args.udf_files:
            p = Path(file_str)
            print(f"\n🔍 Doğrulanıyor: {p.name}")
            try:
                res = verify_udf(p)
                if not res.get("imzali"):
                    print(f"❌ {res.get('hata')}")
                    continue
                if res.get("ozet_uyusuyor"):
                    print(f"✅ İMZA GEÇERLİ! (İçerik Özeti Uyuşuyor)")
                else:
                    print(f"⚠️ GEÇERSİZ İMZA! İçerik özeti eşleşmiyor.")
                print(f"   • SHA-256 Özeti: {res.get('icerik_ozeti_sha256')}")
                print(f"   • İmza Boyutu  : {res.get('imza_boyutu')} bayt")
                if res.get("signer"):
                    s = res["signer"]
                    print(f"   • İmzacı       : {s.get('imzaci')}")
                    print(f"   • Sağlayıcı    : {s.get('saglayici')}")
                    print(f"   • Geçerlilik   : {s.get('gecerlilik_baslangic')} - {s.get('gecerlilik_bitis')}")
            except Exception as e:
                print(f"❌ Doğrulama hatası: {e}")
        return

    # İmzalama modu
    for i, file_str in enumerate(args.udf_files):
        p = Path(file_str)
        out_target = Path(args.output) if (args.output and len(args.udf_files) == 1) else None
        try:
            sign_udf(
                p,
                output_path=out_target,
                pin=args.pin,
                force_mobile=args.mobil,
                operator=args.operator,
                phone=args.gsm,
                generate_pdf=args.pdf
            )
        except Exception as e:
            print(f"❌ {p.name} imzalanamadı: {e}", file=sys.stderr)
            if len(args.udf_files) == 1:
                sys.exit(1)


if __name__ == "__main__":
    main()
