#!/usr/bin/env python3
"""
UYAP UDF E-İmza Modülü & CLI
Telefona bağlı E-İmza (ArkSigner / CCID) üzerinden UDF dosyalarını CAdES-BES formatında imzalar.

Kullanım:
    uyap-imzala dilekce.udf
    uyap-imzala dilekce.udf --pin 455625 --output dilekce_imzali.udf
    uyap-imzala dilekce.udf --pdf
"""

import os
import sys
import argparse
import base64
import zipfile
from pathlib import Path
import requests

EIMZA_SERVICE_URL = "http://127.0.0.1:5975"
DEFAULT_PIN = os.getenv("EIMZA_PIN", "455625")


def get_active_certificate():
    """Adalet E-İmza servisinden takılı kartın sertifika ID ve bilgilerini döner."""
    try:
        r = requests.get(f"{EIMZA_SERVICE_URL}/api/v1/signature/getCertificates", timeout=5)
        res = r.json()
        if res.get("metadata", {}).get("STATUS") != "SUCCESS":
            raise RuntimeError(f"Sertifika alınamadı: {res.get('metadata', {}).get('MESSAGE')}")
        
        cards = res.get("data", [])
        if not cards or not cards[0].get("certificates"):
            raise RuntimeError("Takılı e-imza kartında geçerli sertifika bulunamadı.")
        
        card = cards[0]
        cert = card["certificates"][0]
        return {
            "card_name": card.get("cardName"),
            "certificate_id": cert.get("certificateId"),
            "owner": cert.get("owner"),
            "issuer": cert.get("issuer"),
            "valid_until": cert.get("validUntil")
        }
    except requests.RequestException as e:
        raise ConnectionError(f"E-İmza servisi (port 5975) ile bağlantı kurulamadı: {e}")


def sign_content_xml(content_xml_bytes: bytes, cert_id: str, pin: str) -> bytes:
    """E-İmza kartına content.xml'i gönderip CAdES-BES imza baytlarını (sign.sgn) alır."""
    content_b64 = base64.b64encode(content_xml_bytes).decode("ascii")
    payload = {
        "certificateId": cert_id,
        "password": pin,
        "content": content_b64
    }
    
    r = requests.post(f"{EIMZA_SERVICE_URL}/api/v1/signature/sign", json=payload, timeout=30)
    res = r.json()
    
    if res.get("metadata", {}).get("STATUS") != "SUCCESS":
        msg = res.get("metadata", {}).get("MESSAGE", "Bilinmeyen hata")
        raise RuntimeError(f"İmzalama işlemi başarısız: {msg}")
    
    sdata = res.get("data") or {}
    sig_b64 = sdata.get("signedData") if isinstance(sdata, dict) else sdata
    if not sig_b64:
        raise RuntimeError("Servis imza verisi (signedData) döndürmedi.")
    
    return base64.b64decode(sig_b64)


def sign_udf(udf_path: Path, output_path: Path = None, pin: str = DEFAULT_PIN) -> Path:
    """Belirtilen UDF dosyasını imzalar ve yeni UDF olarak kaydeder."""
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
    
    # 1. content.xml oku
    with zipfile.ZipFile(str(udf_path), "r") as zf:
        if "content.xml" not in zf.namelist():
            raise ValueError("Geçersiz UDF dosyası: Arşiv içinde content.xml bulunamadı.")
        content_xml = zf.read("content.xml")
        
    # 2. Sertifika bilgilerini al
    cert_info = get_active_certificate()
    print(f"🔑 E-İmza Sahibi: {cert_info['owner']} ({cert_info['card_name']})")
    print(f"🔒 Sertifika ID: {cert_info['certificate_id'][:16]}...")
    
    # 3. İmzalat
    print("⏳ Kart imzalamayı yürütüyor (PIN doğrulanıyor)...")
    sig_bytes = sign_content_xml(content_xml, cert_info["certificate_id"], pin)
    print(f"✅ İmza verisi alındı: {len(sig_bytes)} bayt (CAdES-BES)")
    
    # 4. Yeni UDF paketle
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(output_path), "w", compression=zipfile.ZIP_DEFLATED) as zf_out:
        zf_out.writestr("content.xml", content_xml)
        zf_out.writestr("sign.sgn", sig_bytes)
        
    print(f"🎉 İmzalı UDF oluşturuldu: {output_path} ({output_path.stat().st_size} bayt)")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="UYAP UDF E-İmza Aracı")
    parser.add_argument("udf_file", help="İmzalanacak UDF dosyasının yolu")
    parser.add_argument("-o", "--output", help="Çıktı UDF dosyasının yolu (varsayılan: <dosya>_IMZALI.udf)")
    parser.add_argument("-p", "--pin", default=DEFAULT_PIN, help="E-İmza PIN kodu (varsayılan: 455625)")
    parser.add_argument("--pdf", action="store_true", help="İmzaladıktan sonra PDF önizlemesini de üret")
    
    args = parser.parse_args()
    
    try:
        out_udf = sign_udf(Path(args.udf_file), Path(args.output) if args.output else None, args.pin)
        
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
