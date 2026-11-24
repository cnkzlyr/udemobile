#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CanEditor Hukuk Asistanı — E-İmza & Mobil İmza Entegrasyon Modülü
© 2026 Av. Can KIZILYAR — Tüm hakları saklıdır.

CanEditor masaüstü (Tauri), web ve Android WebView arayüzünün
yerel donanım USB e-imza token'ı ve Havelsan UYAP Mobil İmza motoruyla
haberleşmesini sağlar.
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# evrak modülü altındaki uyap_imzala'yı içe aktar
KOK = Path(__file__).resolve().parent
EVRAK_DIR = KOK / "moduller" / "evrak"
if str(EVRAK_DIR) not in sys.path:
    sys.path.insert(0, str(EVRAK_DIR))

try:
    import uyap_imzala
except ImportError:
    # Alternatif olarak uyap-evrak-indirici'den dene
    ALT_DIR = Path.home() / "uyap-evrak-indirici"
    if str(ALT_DIR) not in sys.path:
        sys.path.insert(0, str(ALT_DIR))
    import uyap_imzala


def durum_ozet() -> Dict[str, Any]:
    """Sunucunun genel /api/durum çıktısına eklenecek kısa özet."""
    try:
        st = uyap_imzala.get_system_status()
        return {
            "eimza_takili": st.get("donanim_kart_takili", False),
            "sessiz_imza": st.get("sessiz_imza_hazir", False),
            "mobil_hazir": st.get("mobil_imza_servisi_calisiyor", False),
            "kart": st.get("kart_bilgisi", {}).get("card_name") if st.get("kart_bilgisi") else None,
            "sahip": st.get("kart_bilgisi", {}).get("owner") if st.get("kart_bilgisi") else None
        }
    except Exception as e:
        return {"hata": str(e), "eimza_takili": False}


def durum() -> Dict[str, Any]:
    """CanEditor /api/imza/durum uç noktası."""
    return uyap_imzala.get_system_status()


def imzala(govde: Dict[str, Any]) -> Dict[str, Any]:
    """
    CanEditor /api/imza/imzala uç noktası.
    Girdi Parametreleri:
        udf: İmzalanacak UDF dosyasının tam veya göreli yolu
        pin: E-İmza PIN kodu (varsayılan: 455625)
        yontem: 'oto' (takılıysa sessiz e-imza, yoksa mobil) | 'eimza' | 'mobil'
        gsm: Mobil imza telefon no
        operator: 1 (Turkcell), 2 (Türk Telekom), 3 (Vodafone)
        pdf: True ise imzalandıktan sonra PDF de üretilir
    """
    udf_yol_str = str(govde.get("udf") or govde.get("udf_yolu") or "").strip()
    if not udf_yol_str:
        raise ValueError("İmzalanacak UDF dosyası ('udf') belirtilmedi.")

    udf_path = Path(udf_yol_str)
    if not udf_path.is_absolute():
        udf_path = (Path.home() / udf_path).resolve()

    if not udf_path.exists():
        raise FileNotFoundError(f"UDF dosyası bulunamadı: {udf_path}")

    pin = str(govde.get("pin") or uyap_imzala.DEFAULT_PIN).strip()
    yontem = str(govde.get("yontem") or "oto").lower()
    force_mobile = (yontem == "mobil")
    gsm = str(govde.get("gsm") or uyap_imzala.DEFAULT_GSM).strip()
    operator = int(govde.get("operator") or uyap_imzala.DEFAULT_OP)
    generate_pdf = bool(govde.get("pdf", False))

    out_udf, info = uyap_imzala.sign_udf(
        udf_path=udf_path,
        output_path=None,
        pin=pin,
        force_mobile=force_mobile,
        operator=operator,
        phone=gsm,
        generate_pdf=generate_pdf
    )

    return {
        "tamam": True,
        "mesaj": f"UDF belgesi {info['yontem']} ile başarıyla imzalandı.",
        "imzali_udf": str(out_udf),
        "yontem": info["yontem"],
        "imzaci": info.get("imzaci", ""),
        "pdf_yolu": info.get("pdf_yolu"),
        "boyut": info["boyut"]
    }


def dogrula(govde: Dict[str, Any]) -> Dict[str, Any]:
    """CanEditor /api/imza/dogrula uç noktası."""
    udf_yol_str = str(govde.get("udf") or govde.get("udf_yolu") or "").strip()
    if not udf_yol_str:
        raise ValueError("Doğrulanacak UDF dosyası ('udf') belirtilmedi.")

    udf_path = Path(udf_yol_str)
    if not udf_path.is_absolute():
        udf_path = (Path.home() / udf_path).resolve()

    res = uyap_imzala.verify_udf(udf_path)
    res["tamam"] = res.get("gecerli", False)
    return res
