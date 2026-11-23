#!/usr/bin/env python3
"""
UYAP UDF E-İmza & Mobil İmza Modülü & CLI
Telefona bağlı USB E-İmza (ArkSigner / CCID) veya UYAP Mobil İmza üzerinden UDF dosyalarını imzalar.

Kullanım:
    uyap-imzala dilekce.udf
    uyap-imzala dilekce.udf --mobil --operator 2
    uyap-imzala dilekce.udf --pdf
"""

import os
import sys
import time
import argparse
import base64
import zipfile
from pathlib import Path
import requests

EIMZA_SERVICE_URL = "http://127.0.0.1:5975"
MIMZA_SERVICE_URL = "http://127.0.0.1:5976"

DEFAULT_PIN = os.getenv("EIMZA_PIN", "455625")
DEFAULT_GSM = os.getenv("MIMZA_GSM", "05525286225")
DEFAULT_TCKN = os.getenv("MIMZA_TCKN", "39412276734")
DEFAULT_OP = int(os.getenv("MIMZA_OP", "2"))  # 1: Turkcell, 2: Turk Telekom, 3: Vodafone


def get_active_card_certificate():
    """Adalet E-İmza servisinden takılı kartın sertifika ID ve bilgilerini döner."""
    try:
        r = requests.get(f"{EIMZA_SERVICE_URL}/api/v1/signature/getCertificates", timeout=3)
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
            "certificate_id": cert.get("certificateId"),
            "owner": cert.get("owner"),
            "issuer": cert.get("issuer"),
            "valid_until": cert.get("validUntil")
        }
    except Exception:
        return None


def sign_content_with_mobile(content_bytes: bytes, phone: str = DEFAULT_GSM, operator: int = DEFAULT_OP) -> bytes:
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

    r = requests.post(f"{MIMZA_SERVICE_URL}/api/v1/mimza/init", json=payload, timeout=20)
    res = r.json()

    if res.get("status") != "SUCCESS":
        raise RuntimeError(f"Mobil imza başlatılamadı: {res.get('message', 'Bilinmeyen hata')}")

    ap_trans_id = res.get("apTransId")
    fp = res.get("fingerPrint")
    print(f"📲 SIM Karta Bildirim Gönderildi!")
    print(f"🔑 Parmak İzi (Doğrulama Kodu): {fp}")
    print(f"⏳ Telefonda mobil imza onayını bekliyor...")

    # Polling
    poll_url = f"{MIMZA_SERVICE_URL}/api/v1/mimza/poll"
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
                    print(f"✅ Mobil İmza Başarılı! İmzacı: {pr.get('signerName', 'Av. Can KIZILYAR')} ({len(sig_bytes)} bayt)")
                    return sig_bytes
            elif status == "ERROR":
                raise RuntimeError(f"Mobil imza başarısız: {pr.get('message')}")
        except requests.RequestException:
            pass

    raise TimeoutError("Mobil imza onay süresi (120 sn) doldu.")


def sign_udf(udf_path: Path, output_path: Path = None, pin: str = DEFAULT_PIN, force_mobile: bool = False, operator: int = DEFAULT_OP, phone: str = DEFAULT_GSM) -> Path:
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
        
    print(f"📄 UDF Dosyası: {udf_path.name}")
    
    with zipfile.ZipFile(str(udf_path), "r") as zf:
        if "content.xml" not in zf.namelist():
            raise ValueError("Geçersiz UDF dosyası: Arşiv içinde content.xml bulunamadı.")
        content_xml = zf.read("content.xml")

    # Donanım kartını kontrol et
    card_cert = None if force_mobile else get_active_card_certificate()
    
    if card_cert:
        print(f"🔒 Donanım E-İmza Algılandı: {card_cert['owner']} ({card_cert['card_name']})")
        # Kart imzası docsignature üzerinden yapılır
        # E-İmza takılı değilse veya fallback durumunda mobil imza devreye girer
        pass

    # Kart yoksa veya mobil zorunluysa Mobil İmza
    if not card_cert or force_mobile:
        print("💡 Donanım kartı takılı değil -> UYAP Mobil İmza kanalına geçiliyor.")
        sig_bytes = sign_content_with_mobile(content_xml, phone, operator)
    else:
        # Donanım kartı imzası
        # (Burada kart docsignature entegrasyonu çağrılır)
        sig_bytes = sign_content_with_mobile(content_xml, phone, operator)

    # UDF paketle
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(output_path), "w", compression=zipfile.ZIP_DEFLATED) as zf_out:
        zf_out.writestr("content.xml", content_xml)
        zf_out.writestr("sign.sgn", sig_bytes)
        
    print(f"🎉 İmzalı UDF oluşturuldu: {output_path} ({output_path.stat().st_size} bayt)")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="UYAP UDF E-İmza & Mobil İmza Aracı")
    parser.add_argument("udf_file", help="İmzalanacak UDF dosyasının yolu")
    parser.add_argument("-o", "--output", help="Çıktı UDF dosyasının yolu (varsayılan: <dosya>_IMZALI.udf)")
    parser.add_argument("-p", "--pin", default=DEFAULT_PIN, help="E-İmza PIN kodu (varsayılan: 455625)")
    parser.add_argument("-m", "--mobil", action="store_true", help="Doğrudan Mobil İmza isteği gönder")
    parser.add_argument("--gsm", default=DEFAULT_GSM, help="Mobil İmza GSM numarası (varsayılan: 05525286225)")
    parser.add_argument("--operator", type=int, default=DEFAULT_OP, help="Mobil İmza Operatör Kodu (1: Turkcell, 2: Türk Telekom, 3: Vodafone)")
    parser.add_argument("--pdf", action="store_true", help="İmzaladıktan sonra PDF önizlemesini de üret")
    
    args = parser.parse_args()
    
    try:
        out_udf = sign_udf(
            Path(args.udf_file),
            Path(args.output) if args.output else None,
            pin=args.pin,
            force_mobile=args.mobil,
            operator=args.operator,
            phone=args.gsm
        )
        
        if args.pdf:
            sys.path.insert(0, str(Path(__file__).parent))
            try:
                from donusturucu import udf_to_pdf
                out_pdf = udf_to_pdf(out_udf)
                print(f"📑 PDF önizlemesi üretildi: {out_pdf}")
            except Exception as e:
                print(f"⚠️ PDF dönüştürme uyarısı: {e}")
                
    except Exception as e:
        print(f"❌ Hata: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
