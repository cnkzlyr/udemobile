#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır. / All rights reserved.
"""
UYAP Avukat Portal - Güvenli, Kategorili Toplu Evrak & İşlem İndirici
---------------------------------------------------------------------
Temel Yetenekler ve Güvenlik Önlemleri:
1. Chromium Entegrasyonu (CDP - Port 9223):
   - Tarayıcıyı özel hata ayıklama portuyla yönetir veya mevcut açık UYAP sekmesine bağlanır.
2. Otomatik e-İmza ile Giriş ve Oturum Kurtarma (ArkSigner localhost:5975 Köprüsü):
   - Oturum kapandığında, düştüğünde veya hata aldığında kullanıcının PIN kodu
     ile ArkSigner üzerinden otomatik challenge imzalayıp UYAP oturumunu kesintisiz tazeler.
3. Sahte HTML / Hata Sayfası Koruması (Kesin İçerik Doğrulama & Atomik Kayıt):
   - Oturum düşmesiyle dönen HTML sayfalarını veya JSON hata yanıtlarını ASLA UDF/PDF
     olarak kaydetmez. Magic bytes kontrolü yapar ve geçici (.part) dosyaya yazıp doğrular.
4. Mükerrerlik ve Eksiklik Önleme (Tam Doğruluk & İdempotent Çalışma):
   - İndirme geçmişini hem JSON indeksinde hem de diskteki gerçek dosya varlığı ve boyutuyla
     denetler. İndirilen hiçbir dosya tekrar indirilmez; yarım kalan veya silinen dosyalar
     otomatik olarak yeniden indirilir.
5. Rotasyonlu Metin Günlüğü (Rotating TXT Logger):
   - Sürekli olarak "uyap_indirici_log.txt" dosyasına anlık yazar ve anında diske flush eder.
   - Dosya boyutu 8 MB sınırına ulaştığında yeni txt'ye geçer, en fazla 3 yedek tutar.
   - Metin editörlerinde anında açılır, kasmaz ve dosya kirliliği oluşturmaz.
6. UYAP Koruma Sistemi (Anti-Ban & Anti-Flood):
   - Seri (tek tek) indirme, rastgele jitter beklemesi (3.5 - 7.0 sn) ve N dosyada dinlenme molası.
"""

# Android (Termux'suz): gömülü glibc ad çözümleyemez → bağımsız DNS çözücüyü bu süreçte de kur
# (sitecustomize'a güvenmeden; v4.4.0'da nöbetçi "Temporary failure in name resolution" veriyordu)
if __import__("os").environ.get("CANASISTAN_ANDROID") == "1":
    try:
        import sys as _s, pathlib as _p
        _s.path.insert(0, str(_p.Path(__file__).resolve().parents[2]))
        import dns_cozucu as _dns
        _dns.yama_kur()
    except Exception:  # noqa: BLE001
        pass

import base64
import csv
import datetime as dt
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import random
import re
import subprocess
import sys
import threading
import time
import pathlib
from pathlib import Path
from urllib.parse import urlencode

import argparse
import shutil
import requests
import websocket

from enrich_and_rename_documents import (
    extract_meta_from_udf,
    update_udf_properties,
    build_enriched_filename,
)

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

# ---------------------------------------------------------------------------
# Dizin ve Yapılandırma Sabitleri
# ---------------------------------------------------------------------------
# Paketlenmiş uygulamada yazılabilir veri klasörü UYAP_VERI_DIZINI ile verilir
BASE_DIR = Path(os.environ.get("UYAP_VERI_DIZINI") or Path(__file__).resolve().parent)
BASE_DIR.mkdir(parents=True, exist_ok=True)  # günlük dosyası açılmadan önce veri klasörü bulunmalı
if os.environ.get("UYAP_INDIRME_DIZINI"):
    DEFAULT_DOWNLOAD_DIR = Path(os.environ["UYAP_INDIRME_DIZINI"])
elif Path("/sdcard/Download").exists():
    DEFAULT_DOWNLOAD_DIR = Path("/sdcard/Download/UYAP_Indirilenler")
elif (BASE_DIR.parent / "UYAP_Indirilenler").exists():
    DEFAULT_DOWNLOAD_DIR = (BASE_DIR.parent / "UYAP_Indirilenler").resolve()
elif (BASE_DIR / "UYAP_Indirilenler").exists():
    DEFAULT_DOWNLOAD_DIR = (BASE_DIR / "UYAP_Indirilenler").resolve()
else:
    DEFAULT_DOWNLOAD_DIR = BASE_DIR / "UYAP_Indirilenler"
CHROME_PROFILE_DIR = BASE_DIR / ".uyap_chrome_profile"
HISTORY_FILE = BASE_DIR / "indirme_gecmisi.json"
LOG_FILE = BASE_DIR / "uyap_indirici_log.txt"
CDP_PORT = 9223
UYAP_BASE_URL = "https://avukat.uyap.gov.tr"
ARKSIGNER_URL = "http://localhost:5975"
PIN_FILE = BASE_DIR / "pin.txt"
CONFIG_FILE = BASE_DIR / ".uyap_config.json"
DEFAULT_E_IMZA_PIN = ""
if PIN_FILE.exists():
    try:
        DEFAULT_E_IMZA_PIN = PIN_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        pass
if not DEFAULT_E_IMZA_PIN:
    DEFAULT_E_IMZA_PIN = os.environ.get("UYAP_E_IMZA_PIN", "")
SIGN_CHALLENGE = "QWRhbGV0IEJha2FubMSxxJ/EsSBCaWxnaSDEsMWfbGVtIEdlbmVsIE3DvGTDvHJsw7zEn8O8IHRhcmFmxLFuZGFuIGdlbGnFn3RpcmlsZW4gdXlndWxhbWF5YSBlLWltemEgZ2lyacWfIHlhcG1hayBpc3RpeW9ydW0u"


def win_extended_path(p: Path | str) -> str:
    """Windows MAX_PATH (260 karakter) sınırlamasını aşmak için \\\\?\\ önekini uygular."""
    sp = str(p)
    if os.name == "nt":
        abs_p = os.path.abspath(sp)
        if not abs_p.startswith("\\\\?\\"):
            if abs_p.startswith("\\\\"):
                return "\\\\?\\UNC\\" + abs_p[2:]
            return "\\\\?\\" + abs_p
        return abs_p
    return sp


def safe_write_bytes(path: Path | str, data: bytes) -> Path:
    """Windows'ta 260 karakterden uzun yollara dahi güvenli atomik dosya yazar."""
    p = Path(path)
    ext_p = win_extended_path(p)
    parent_dir = os.path.dirname(ext_p)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    with open(ext_p, "wb") as f:
        f.write(data)
    return p


def safe_replace_file(src: Path | str, dst: Path | str) -> None:
    """Windows ve POSIX üzerinde uzun yollu dosyayı güvenle taşır/değiştirir."""
    ext_src = win_extended_path(src)
    ext_dst = win_extended_path(dst)
    parent_dir = os.path.dirname(ext_dst)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    os.replace(ext_src, ext_dst)


def load_user_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def mobil_imza_ayarlari() -> tuple[str, str, str]:
    """Mobil İmza bilgileri: ortam değişkenleri (UYAP_TC, UYAP_GSM, UYAP_OPERATOR) > .uyap_config.json."""
    cfg = load_user_config()
    tc = os.environ.get("UYAP_TC") or str(cfg.get("tc") or "")
    gsm = os.environ.get("UYAP_GSM") or str(cfg.get("gsm") or "")
    op = os.environ.get("UYAP_OPERATOR") or str(cfg.get("operator") or "")
    return tc.strip(), gsm.strip(), op.strip()


# Mobil İmza tekrar aralıkları (sn): telefon art arda bildirimle boğulmasın; son değer sonsuza dek tekrarlanır
MOBIL_IMZA_BEKLEMELERI = (60, 120, 300, 600)


def save_user_config(data: dict):
    try:
        cur = load_user_config()
        cur.update(data)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)
        try:
            os.chmod(CONFIG_FILE, 0o600)
        except Exception:
            pass
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Rotasyonlu Loglama Altyapısı (Maksimum 8 MB, 3 Yedek)
# ---------------------------------------------------------------------------
file_logger = logging.getLogger("UyapIndiriciLogger")
file_logger.setLevel(logging.INFO)
file_logger.propagate = False

if not file_logger.handlers:
    rf_handler = RotatingFileHandler(
        filename=str(LOG_FILE),
        maxBytes=8 * 1024 * 1024,  # 8 MB (editörlerde anında açılır, ~80.000 satır)
        backupCount=3,             # Sadece uyap_indirici_log.txt, .1, .2, .3
        encoding="utf-8"
    )
    rf_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    file_logger.addHandler(rf_handler)
else:
    rf_handler = file_logger.handlers[0]


# ---------------------------------------------------------------------------
# Yardımcı Fonksiyonlar: Metin Temizleme, Tür Çıkarımı, Dosya Doğrulama
# ---------------------------------------------------------------------------

def sanitize_path_part(value: str, default: str = "Belirtilmemis", max_len: int = 80) -> str:
    """Klasör ve dosya adları için güvenli metin üretir."""
    if not value:
        return default
    s = str(value).strip()
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(". ")
    if not s:
        return default
    if len(s) > max_len:
        s = s[:max_len].rstrip(". _")
    return s


slugify_filename = sanitize_path_part


def tr_lower(text: str) -> str:
    """Türkçe İ/ı, Ş/ş, Ğ/ğ, Ü/ü, Ö/ö, Ç/ç harflerini Unicode standardında küçük harfe dönüştürür."""
    if not text:
        return ""
    return (
        str(text)
        .replace("İ", "i")
        .replace("I", "ı")
        .replace("Ş", "ş")
        .replace("Ğ", "ğ")
        .replace("Ü", "ü")
        .replace("Ö", "ö")
        .replace("Ç", "ç")
        .lower()
    )


def tr_upper(text: str) -> str:
    """Türkçe i/İ, ı/I, ş/Ş, ğ/Ğ, ü/Ü, ö/Ö, ç/Ç harflerini Unicode standardında büyük harfe dönüştürür."""
    if not text:
        return ""
    return (
        str(text)
        .replace("i", "İ")
        .replace("ı", "I")
        .replace("ş", "Ş")
        .replace("ğ", "Ğ")
        .replace("ü", "Ü")
        .replace("ö", "Ö")
        .replace("ç", "Ç")
        .upper()
    )


def matches_evrak_filter(tur_name: str, filter_type: str) -> bool:
    """
    UYAP'taki tarihsel ve mahkeme bazlı evrak adı çeşitliliklerini dikkate alarak
    kesin pozitif ve negatif filtreleme yapar. Mükerrer veya yanlış evrakları eler.
    """
    if not tur_name:
        return False
    tn = tr_lower(tur_name)
    ft = tr_lower(filter_type)

    if ft in ("tumu", "all", "*"):
        return True

    if ft == "durusma":
        is_d = (
            (("duruşma" in tn or "durusma" in tn or "celse" in tn) and ("zapt" in tn or "tutana" in tn))
            or ("segbis" in tn and ("zapt" in tn or "tutana" in tn or "çözüm" in tn or "cozum" in tn))
        )
        is_ex = any(k in tn for k in (
            "talep", "talebi", "müzekkere", "muzekkere", "celp", "celbi",
            "davetiye", "tebligat", "tebliğ", "teblig", "çağrı", "cagri",
            "dilekçe", "dilekce", "mazeret", "tensip", "zaptolunan", "arama",
            "yakalama", "kura", "tevzi", "teslim", "tesellüm", "emanet",
            "diğer tutanak", "diger tutanak", "ifade", "sorgu", "ihzar",
            "otopsi", "muayene", "adli kontrol tutana", "vekalet", "yetki belgesi"
        ))
        return is_d and not is_ex

    if ft == "bilirkisi":
        is_b = any(k in tn for k in (
            "bilirkişi rapor", "bilirkisi rapor", "ek rapor", "uzman rapor",
            "uzman görüş", "uzman gorus", "adli tıp", "adli tip", "atk rapor",
            "kriminal", "grafoloji", "hesap rapor", "mali müşavir", "mali musavir",
            "bilirkişi heyet", "bilirkisi heyet", "inceleme rapor", "uyuşturucu inceleme", "uyusturucu inceleme"
        ))
        is_ex = any(k in tn for k in (
            "ücret", "ucret", "sarf", "teslim", "yemin", "tevdi", "süre talebi",
            "sure talebi", "çekilme", "cekilme", "itiraz", "tebliğ", "teblig"
        ))
        return is_b and not is_ex

    if ft == "karar":
        is_k = any(k in tn for k in (
            "gerekçeli karar", "gerekceli karar", "hüküm", "hukum", "kısa karar", "kisa karar",
            "ara karar", "ek karar", "ilam", "istinaf kararı", "istinaf karari", "bam kararı",
            "bam karari", "yargıtay kararı", "yargitay karari", "danıştay kararı", "danistay karari",
            "takipsizlik", "kyok", "yetkisizlik kararı", "yetkisizlik karari", "görevsizlik kararı",
            "gorevsizlik karari", "tefrik kararı", "tefrik karari", "birleştirme kararı",
            "birlestirme karari", "nihai karar"
        ))
        is_ex = any(k in tn for k in (
            "tebliğ", "teblig", "mazbata", "masraf", "harç", "harc", "itiraz", "temyiz",
            "başvuru", "basvuru"
        ))
        return is_k and not is_ex

    if ft == "tensip":
        return "tensip" in tn and not ("itiraz" in tn)

    if ft in ("layihalar", "dilekce", "dilekceler"):
        # Hem bizim hem karşı tarafın sunduğu tüm dava ve cevap layihaları, beyanlar, itirazlar
        is_layiha = any(k in tn for k in (
            "dilekçe", "dilekce", "layiha", "replik", "düplik", "duplik",
            "dava açılış", "dava acilis", "açılan dava", "acilan dava",
            "delil", "beyan", "savunma", "mütalaa", "mutalaa", "talep evrak",
            "şikayet", "sikayet", "katılan", "katilan", "itiraz dilekç", "itiraz dilekc",
            "itiraz", "ıslah", "islah", "feragat", "kabul dilekç", "kabul dilekc", "sulh dilekç",
            "ihtiyati tedbir", "tehir-i icra", "adli yardım", "adli yardim",
            "süre tutum", "sure tutum", "vekaletname", "yetki belgesi",
            "e-dilekçe", "e-dilekce", "avukat evrak"
        ))
        is_ex = any(k in tn for k in (
            "tebligat", "tebliğ", "teblig", "mazbata", "duruşma tutana", "durusma tutana",
            "celse zapt", "tensip zapt", "gerekçeli karar", "gerekceli karar",
            "kısa karar", "kisa karar", "makbuz", "tahsilat", "harç makbuz", "harc makbuz",
            "masraf makbuz", "keşif zapt"
        )) and not any(k in tn for k in ("dilekçe", "dilekce", "itiraz", "beyan", "savunma", "layiha"))
        return is_layiha and not is_ex

    if ft in ("tebligat", "tebligatlar", "mazbata"):
        # Hem Fiziki PTT hem de UETS / Elektronik Tebligat evrakları dahil edilir
        is_teb = any(k in tn for k in (
            "tebligat", "tebliğ", "teblig", "mazbata", "uets", "e-tebligat", "elektronik tebligat",
            "posta alındı", "posta alindi", "teslim tutanağı", "teslim tutanagi"
        ))
        is_ex = any(k in tn for k in (
            "duruşma tutana", "durusma tutana", "celse zapt", "tensip zapt",
            "gerekçeli karar", "gerekceli karar", "kısa karar", "kisa karar",
            "bilirkişi raporu", "bilirkisi raporu", "keşif zapt"
        )) and not any(k in tn for k in ("mazbata", "şerh", "serh", "parça", "parca", "uets", "e-tebligat", "elektronik"))
        if "bilirkişi" in tn or "bilirkisi" in tn:
            is_ex = True
        return is_teb and not is_ex

    if ft in ("muzekkere", "muzekkereler", "kurum_cevaplari"):
        is_muz = any(k in tn for k in (
            "müzekkere", "muzekkere", "kurum cevap", "banka", "ekstre",
            "tapu", "sgk", "egm", "polnet", "takbis",
            "nüfus", "nufus", "hts", "abone bilgisi", "kayıt cevap", "kayit cevap"
        )) and any(k in tn for k in ("cevab", "cevap", "yazı", "yazi", "müzekkere", "muzekkere", "ekstre", "rapor", "belge", "döküm", "dokum"))
        is_ex = any(k in tn for k in ("duruşma", "durusma", "karar", "dilekçe", "dilekce", "tensip"))
        return is_muz and not is_ex

    if ft == "iddianame":
        return any(k in tn for k in ("iddianame", "fezleke")) and not ("iade" in tn)

    if ft == "kesinlesme":
        return "kesinleşme" in tn or "kesinlesme" in tn

    try:
        from evrak_turleri import KATEGORI_ADI, kategori_of
        if ft in KATEGORI_ADI:
            return kategori_of(tur_name) == ft
    except ImportError:
        pass
    return ft in tn


def auto_convert_udf_to_pdf(target_path: Path):
    """Eğer indirilen dosya .udf ise Havelsan motoruyla aynı adda .pdf kopyasını oluşturur."""
    try:
        import donusturucu  # paketle gelen JRE/yazı tiplerini ve UYAP Editör kurulumunu da bulur
        p = Path(target_path)
        if p.suffix.lower() == ".udf" and not p.with_suffix(".pdf").exists():
            donusturucu.udf_to_pdf(p, timeout=60)
        return
    except ImportError:
        pass
    try:
        p = Path(target_path)
        if not p.exists() or p.suffix.lower() != ".udf":
            return
        pdf_path = p.with_suffix(".pdf")
        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            return
        script_dir = Path(__file__).resolve().parent
        if (script_dir / "jars").exists():
            jars_dir = script_dir / "jars"
        elif (script_dir.parent / "jars").exists():
            jars_dir = script_dir.parent / "jars"
        else:
            jars_dir = Path("/data/data/com.termux/files/home/jars")

        cp = f"{script_dir}{os.pathsep}{jars_dir / '*'}"
        cmd = [
            "java", "-Xmx256m", "-Djava.awt.headless=true",
            "--add-opens=java.base/java.util=ALL-UNNAMED",
            "--add-opens=java.base/java.lang=ALL-UNNAMED",
            "--add-opens=java.desktop/java.awt=ALL-UNNAMED",
            "--add-opens=java.desktop/javax.swing=ALL-UNNAMED",
            "-cp", cp,
            "uyap.UdfBatchPdfConverter",
            str(p)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
    except Exception:
        pass


def infer_dosya_turu(birim_adi: str, explicit_tur: str = "") -> str:
    """Birim adından veya açık dosya türünden anlamlı bir Dosya/Yargı Türü kategorisi çıkarır."""
    b = tr_upper(birim_adi or "")
    mapping = [
        ("AĞIR CEZA", "Agir_Ceza_Mahkemesi"),
        ("AGIR CEZA", "Agir_Ceza_Mahkemesi"),
        ("ASLİYE CEZA", "Asliye_Ceza_Mahkemesi"),
        ("ASLIYE CEZA", "Asliye_Ceza_Mahkemesi"),
        ("SULH CEZA", "Sulh_Ceza_Hakimligi"),
        ("ÇOCUK", "Cocuk_Mahkemesi"),
        ("İNFAZ", "Infaz_Hakimligi"),
        ("İCRA CEZA", "Icra_Ceza_Mahkemesi"),
        ("İCRA HUKUK", "Icra_Hukuk_Mahkemesi"),
        ("İCRA DAİRESİ", "Icra_Dairesi"),
        ("İCRA MÜDÜRLÜĞÜ", "Icra_Dairesi"),
        ("GENEL İCRA", "Icra_Dairesi"),
        ("İFLAS", "Icra_Dairesi"),
        ("SATIŞ MEMURLUĞU", "Satis_Memurlugu"),
        ("ASLİYE HUKUK", "Asliye_Hukuk_Mahkemesi"),
        ("SULH HUKUK", "Sulh_Hukuk_Mahkemesi"),
        ("ASLİYE TİCARET", "Asliye_Ticaret_Mahkemesi"),
        ("AİLE MAHKEMESİ", "Aile_Mahkemesi"),
        ("AİLE", "Aile_Mahkemesi"),
        ("İŞ MAHKEMESİ", "Is_Mahkemesi"),
        ("TÜKETİCİ", "Tuketici_Mahkemesi"),
        ("KADASTRO", "Kadastro_Mahkemesi"),
        ("FİKRİ VE SINAİ", "Fikri_Sinai_Haklar_Mahkemesi"),
        ("BÖLGE İDARE", "Bolge_Idare_Mahkemesi"),
        ("İDARİ DAVA DAİRESİ", "Bolge_Idare_Mahkemesi"),
        ("VERGİ DAVA DAİRESİ", "Bolge_Idare_Mahkemesi"),
        ("BİM ", "Bolge_Idare_Mahkemesi"),
        ("İDARE MAHKEMESİ", "Idare_Mahkemesi"),
        ("VERGİ MAHKEMESİ", "Vergi_Mahkemesi"),
        ("BÖLGE ADLİYE", "Bolge_Adliye_Mahkemesi_Istinaf"),
        ("BAM ", "Bolge_Adliye_Mahkemesi_Istinaf"),
        ("YARGITAY", "Yargitay"),
        ("DANIŞTAY", "Danistay"),
        ("ANAYASA MAHKEMESİ", "Anayasa_Mahkemesi"),
        ("BAŞSAVCILIĞI", "Cumhuriyet_Bassavciligi_Sorusturma"),
        ("SAVCILIĞI", "Cumhuriyet_Bassavciligi_Sorusturma"),
        ("SORUŞTURMA BÜROSU", "Cumhuriyet_Bassavciligi_Sorusturma"),
        ("HAZIRLIK BÜROSU", "Cumhuriyet_Bassavciligi_Sorusturma"),
        ("UZLAŞTIRMA", "Uzlastirma_Burosu"),
        ("ARABULUCULUK", "Arabuluculuk_Burosu"),
        ("TEVZİ BÜRO", "Tevzi_Burosu"),
        ("ÖN BÜRO", "On_Buro"),
        ("VEZNE", "On_Buro"),
    ]
    for kw, label in mapping:
        if kw in b:
            return label

    # Birim adından çıkarılamadıysa explicit_tur'e bak (genel 'Diğer Yargı Birimi' değilse)
    if explicit_tur and explicit_tur.strip():
        sanitized = sanitize_path_part(explicit_tur.strip(), "Diger_Dosya")
        if sanitized not in ("Diger_Yargi_Birimi", "Diğer_Yargı_Birimi", "Diger_Dosya", "Belirtilmemis_Birim"):
            return sanitized

    if birim_adi and birim_adi.strip():
        return "Diger_Yargi_Birimi"
    return "Belirtilmemis_Birim"


def is_case_relevant_for_filter(birim_adi: str, evrak_filter: str) -> bool:
    """
    Hedef evrak türünün bir birimde bulunma ihtimali olup olmadığını denetler.
    Örn: İcra Dairesinde, Arabuluculukta veya CBS Soruşturma dosyasında Duruşma Tutanağı olmaz!
    Böylece yüzlerce alakasız dosya boş yere taranmaz, tarama süresi %60-70 kısalır.
    """
    if not birim_adi:
        return True
    b = tr_lower(birim_adi)
    f = tr_lower(evrak_filter)

    if f in ("tumu", "all", "*", "layihalar", "dilekce", "dilekceler", "tebligat", "tebligatlar", "mazbata"):
        return True

    # İcra Dairesi / Müdürlüğü (Duruşma ve Tensip Mahkeme kararıdır, İcra Dairesinde OLMAZ)
    is_icra_dairesi = any(k in b for k in (
        "icra dairesi", "icra mudurlugu", "icra müdürlüğü", "genel icra",
        "gayrimenkul satis", "gayrimenkul satış", "abonelik", "iflas dairesi"
    )) and not any(k in b for k in ("mahkeme", "hakimliği", "hakimligi"))

    # Savcılık / Soruşturma (Duruşma olmaz, duruşma mahkemede başlar)
    is_savcilik = any(k in b for k in ("cumhuriyet başsavcılığı", "cumhuriyet bassavciligi", "cbs", "hazırlık", "soruşturma"))

    # İdari Bürolar
    is_idari_buro = any(k in b for k in ("arabuluculuk", "tevzi büro", "tevzi buro", "ön büro", "on buro"))

    if f == "durusma":
        if is_icra_dairesi or is_savcilik or is_idari_buro:
            return False
        return True

    if f == "iddianame":
        if is_icra_dairesi or is_idari_buro:
            return False
        if any(k in b for k in ("hukuk", "aile", "iş mah", "is mah", "ticaret", "tüketici", "tuketici", "idare", "vergi", "kadastro")):
            return False
        return True

    if f in ("tensip", "karar"):
        if is_icra_dairesi or is_idari_buro:
            return False
        return True

    if f == "bilirkisi":
        if is_idari_buro or is_icra_dairesi:
            return False
        return True

    return True


def infer_yargi_kategorisi(birim_adi: str) -> str:
    """Birim adından üst yargı kolunu çıkarır (AI ve LLM klasörlemesi için)."""
    b = tr_lower(birim_adi)
    if any(k in b for k in ("icra ceza", "icra hukuk")):
        return "Icra_Mahkemeleri"
    if any(k in b for k in ("icra dairesi", "icra müdürlüğü", "icra mudurlugu", "genel icra", "iflas", "satış memurluğu", "satis memurlugu")):
        return "Icra_Daireleri"
    if any(k in b for k in ("idare", "idari", "vergi", "danıştay", "danistay", "bim", "bölge idare", "bolge idare")):
        return "Idari_Yargi"
    if any(k in b for k in ("ceza", "savcı", "savci", "başsavcı", "bassavci", "çocuk", "cocuk", "infaz", "hazırlık", "hazirlik", "soruşturma", "sorusturma")):
        return "Ceza_Yargisi"
    if any(k in b for k in ("hukuk", "asliye", "sulh", "aile", "iş", "is mah", "ticaret", "tüketici", "tuketici", "kadastro", "fikri", "yargıtay", "yargitay", "bam", "bölge adliye", "bolge adliye", "arabuluculuk", "uzlaştırma", "uzlastirma", "tevzi", "ön büro", "on buro")):
        return "Hukuk_Yargisi"
    return "Diger_Yargi"


def infer_evrak_alt_kategori(evrak_turu: str) -> str:
    """Evrak adından yapay zeka analizine uygun standart alt klasör kategorisi belirler."""
    t = tr_lower(evrak_turu)
    if any(k in t for k in ("duruşma", "durusma", "celse", "segbis")):
        return "DURUSMA_TUTANAKLARI"
    if any(k in t for k in ("rapor", "bilirkişi", "bilirkisi", "uzman", "adli tıp", "adli tip", "kriminal")):
        return "BILIRKISI_RAPORLARI"
    if any(k in t for k in ("karar", "hüküm", "hukum", "ilam")):
        return "GEREKCELI_KARARLAR"
    if "tensip" in t:
        return "TENSIP_ZAPITLARI"
    if any(k in t for k in ("dilekçe", "dilekce", "beyan", "savunma", "layiha", "vekalet", "talep")):
        return "DILEKCELER_LAYIHALAR"
    if any(k in t for k in ("tebligat", "tebliğ", "teblig", "mazbata")):
        return "TEBLIGATLAR"
    if any(k in t for k in ("müzekkere", "muzekkere", "kurum cevab", "banka cevab")):
        return "MUZEKKERE_VE_KURUM_CEVAPLARI"
    if any(k in t for k in ("iddianame", "fezleke")):
        return "IDDIANAMELER"
    if "kesinleşme" in t or "kesinlesme" in t:
        return "KESINLESME_SERHLERI"
    return "DAVA_EVRAKLARI"
    return "DAVA_EVRAKLARI"


def save_ai_manifest(target_base: pathlib.Path, found_documents: list, download_queue: list):
    """
    Yapay zekanın (LLM / RAG / Otonom Ajan) dava analizinde doğrudan kullanabilmesi için
    tüm dosya, duruşma ve evrak kronolojisini içeren JSON manifest ve CSV tablosu üretir.
    """
    manifest_path = target_base / "ai_case_manifest.json"
    csv_path = target_base / "ai_durusma_kronolojisi.csv"

    cases_dict = {}
    csv_rows = []

    for item in found_documents:
        d_key = f"{item['birim_adi']}_{item['dosya_no']}"
        if d_key not in cases_dict:
            cases_dict[d_key] = {
                "birim_adi": item["birim_adi"],
                "dosya_no": item["dosya_no"],
                "dosya_id": item["dosya_id"],
                "yargi_turu": infer_yargi_kategorisi(item["birim_adi"]),
                "dosya_turu": item["dosya_turu"],
                "durusma_tarihleri": [],
                "evraklar": []
            }

        tarih = item["tarih"]
        is_durusma = any(k in tr_lower(item["evrak_turu"]) for k in ("duruşma", "durusma", "celse", "segbis"))
        if is_durusma and tarih not in cases_dict[d_key]["durusma_tarihleri"]:
            cases_dict[d_key]["durusma_tarihleri"].append(tarih)

        ev_entry = {
            "evrak_id": item["evrak_id"],
            "tarih": tarih,
            "evrak_adi": item["evrak_adi"],
            "evrak_turu": item["evrak_turu"],
            "is_attachment": item["is_attachment"],
            "unique_key": item["unique_key"]
        }
        cases_dict[d_key]["evraklar"].append(ev_entry)

        if is_durusma:
            csv_rows.append({
                "Tarih": tarih,
                "Yargi_Turu": cases_dict[d_key]["yargi_turu"],
                "Birim_Adi": item["birim_adi"],
                "Dosya_No": item["dosya_no"],
                "Evrak_Adi": item["evrak_adi"],
                "Evrak_ID": item["evrak_id"]
            })

    for c in cases_dict.values():
        c["durusma_tarihleri"].sort()

    manifest_data = {
        "manifest_surumu": "2.0-ai-ready",
        "olusturma_tarihi": dt.datetime.now().isoformat(),
        "toplam_hedef_dosya": len(cases_dict),
        "toplam_hedef_evrak": len(found_documents),
        "dosyalar": list(cases_dict.values())
    }

    try:
        manifest_path.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[✓] AI Dava Manifestosu hazırlandı: {manifest_path.name}")
    except Exception as e:
        print(f"[!] AI Manifestosu yazılamadı: {e}")

    try:
        csv_rows.sort(key=lambda r: (r["Tarih"], r["Birim_Adi"]))
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as cf:
            writer = csv.DictWriter(cf, fieldnames=["Tarih", "Yargi_Turu", "Birim_Adi", "Dosya_No", "Evrak_Adi", "Evrak_ID"])
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"[✓] AI Duruşma Kronoloji Tablosu hazırlandı: {csv_path.name}")
    except Exception as e:
        print(f"[!] Kronoloji CSV yazılamadı: {e}")


def parse_uyap_date(val) -> dt.date | None:
    """UYAP tarih formatlarını (timestamp, ISO, DD/MM/YYYY, DD.MM.YYYY) dt.date'e çevirir."""
    if not val:
        return None
    if isinstance(val, (int, float)):
        try:
            if val > 1e11:
                val = val / 1000.0
            return dt.datetime.fromtimestamp(val).date()
        except Exception:
            return None
    s = str(val).strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", s)
    if m:
        try:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return dt.date(y, mo, d)
        except ValueError:
            pass
    return None


def guess_extension(filename: str, content_type: str, raw_bytes: bytes) -> str:
    """Dosya uzantısını Content-Disposition, MIME tipi veya dosya imzasından (magic bytes) bulur."""
    if filename:
        m = re.search(r"(\.[a-zA-Z0-9]{2,6})$", filename.strip())
        if m:
            ext = m.group(1).lower()
            if ext not in (".html", ".htm", ".json"):
                return ext
    if raw_bytes:
        if raw_bytes.startswith(b"%PDF"):
            return ".pdf"
        if raw_bytes.startswith(b"PK\x03\x04"):
            return ".udf"
        if raw_bytes.startswith((b"II*\x00", b"MM\x00*")):
            return ".tif"
        if raw_bytes.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if raw_bytes.startswith(b"\x89PNG"):
            return ".png"
        if raw_bytes.startswith(b"{\\rtf"):
            return ".rtf"
        if raw_bytes.startswith(b"\xd0\xcf\x11\xe0"):
            return ".doc"
    ct = (content_type or "").lower()
    if "pdf" in ct:
        return ".pdf"
    if "tiff" in ct or "tif" in ct:
        return ".tif"
    if "word" in ct:
        return ".docx"
    if "zip" in ct:
        return ".zip"
    return ".udf"


def is_valid_document_bytes(raw_bytes: bytes, content_type: str = "") -> tuple[bool, str]:
    """
    İndirilen verinin gerçek ve bozulmamış bir evrak olup olmadığını denetler.
    UYAP oturum süresi bittiğinde dönen HTML sayfalarını, JSON hata mesajlarını veya
    0 baytlık boş/hatalı yanıtları tespit eder.
    """
    if not raw_bytes or len(raw_bytes) < 128:
        return False, "Dosya boyutu çok küçük veya boş (< 128 bayt)"

    sample = raw_bytes[:1024].lower()
    
    # HTML oturum düşmesi / hata sayfası kontrolü
    if (
        b"<!doctype html" in sample
        or b"<html" in sample
        or b"<body" in sample
        or b"<title>" in sample
        or b"loginstate" in sample
        or (b"adalet" in sample and b"giris" in sample and b"<" in sample)
    ):
        return False, "UYAP sunucusunda fiziksel dosya mevcut değil (HTML sayfası döndü)"

    # JSON hata mesajı kontrolü
    if "application/json" in (content_type or "").lower() or sample.strip().startswith(b"{"):
        try:
            j = json.loads(raw_bytes.decode("utf-8", errors="ignore"))
            if isinstance(j, dict) and (j.get("errorCode") or j.get("error") or j.get("status") == "ERROR"):
                msg = j.get("message") or j.get("error") or j.get("errorCode") or str(j)
                return False, f"UYAP JSON hata mesajı döndü: {msg}"
        except Exception:
            pass

    return True, "Geçerli evrak verisi"


# ---------------------------------------------------------------------------
# CDP (Chrome DevTools Protocol) ve ArkSigner e-İmza Bağlantı Yöneticisi
# ---------------------------------------------------------------------------

class UyapBrowserError(RuntimeError):
    """Tarayıcıya / CDP portuna ulaşılamadığında fırlatılan, kullanıcıya gösterilebilir hata."""


IS_TERMUX = bool(os.environ.get("TERMUX_VERSION")) or "com.termux" in (os.environ.get("PREFIX") or "")

_PIN_ERROR_WORDS = ("pin", "şifre", "parola", "hatalı", "yanlış", "incorrect", "wrong", "invalid", "ckr_pin")

# Yerel servislere (CDP 127.0.0.1, ArkSigner localhost) giden istekler sistem/ortam
# proxy'sine takılmasın (requests + websocket-client NO_PROXY'ye uyar).
_np = [x for x in (os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or "").split(",") if x.strip()]
for _h in ("127.0.0.1", "localhost", "::1"):
    if _h not in _np:
        _np.append(_h)
os.environ["NO_PROXY"] = os.environ["no_proxy"] = ",".join(_np)


def _host_of(url: str) -> str:
    m = re.match(r"^[a-z]+://([^/:?#]+)", url or "", re.I)
    return (m.group(1).lower() if m else "")


def ask_mobil_imza_onayi(gsm: str = "", confirm_cb=None, confirmed: bool = False) -> bool:
    """Kullanıcı 'Mobil imza isteği gönderilsin mi?' sorusunu açıkça onaylamadıkça True dönmez."""
    if confirmed:
        return True
    if confirm_cb is not None:
        return bool(confirm_cb())
    if sys.stdin is not None and sys.stdin.isatty():
        try:
            ans = input(f"📲 Mobil imza isteği gönderilsin mi? ({gsm or 'kayıtlı GSM'}) [e/H]: ").strip().lower()
            return ans in ("e", "evet", "y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False
    return False


class UyapBrowserBridge:
    """Chromium ile CDP üzerinden haberleşen, e-İmza / Mobil İmza ile oturum açan köprü.

    Tarayıcı başlatma, hata ayıklama portu ve sekme bulma işlemlerinin TAMAMI bu sınıfta,
    tek yerde yapılır (ensure_browser / get_tab / eval_js).
    """

    UYAP_HOST = "avukat.uyap.gov.tr"
    EDEVLET_HOST = "giris.turkiye.gov.tr"
    BLANK_PREFIXES = ("about:blank", "chrome://newtab", "chrome://new-tab-page", "edge://newtab", "chrome-search://")

    def __init__(self, port: int = CDP_PORT):
        self.port = port
        self.proc: subprocess.Popen | None = None
        self.is_headless = False
        self.last_error = ""
        self._fresh_launch = False
        self._http = requests.Session()
        self._http.trust_env = False  # yerel servisler için proxy kullanma
        self._rejected_pins: set[str] = set()  # sadece SHA-256 özeti, PIN'in kendisi saklanmaz

    # ------------------------------------------------------------------
    # Tarayıcı bulma / başlatma
    # ------------------------------------------------------------------
    @staticmethod
    def _find_chrome_bin() -> str | None:
        env_bin = os.environ.get("UYAP_CHROME_BIN")
        if env_bin and os.path.isfile(env_bin):
            return env_bin
        if sys.platform == "win32":
            win_candidates = []
            try:
                import winreg
                for exe in ("chrome.exe", "msedge.exe"):
                    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                        try:
                            with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as k:
                                win_candidates.append(winreg.QueryValue(k, None))
                        except OSError:
                            pass
            except ImportError:
                pass
            pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
            pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
            lad = os.environ.get("LOCALAPPDATA", "")
            win_candidates += [
                os.path.join(pf, r"Google\Chrome\Application\chrome.exe"),
                os.path.join(pf86, r"Google\Chrome\Application\chrome.exe"),
                os.path.join(lad, r"Google\Chrome\Application\chrome.exe") if lad else "",
                shutil.which("chrome.exe"),
                os.path.join(pf86, r"Microsoft\Edge\Application\msedge.exe"),
                os.path.join(pf, r"Microsoft\Edge\Application\msedge.exe"),
                os.path.join(lad, r"Microsoft\Edge\Application\msedge.exe") if lad else "",
                shutil.which("msedge.exe"),
            ]
            for c in win_candidates:
                c = (c or "").strip('"')
                if c and os.path.isfile(c):
                    return c
            return None

        prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
        candidates = [
            shutil.which("chromium-browser"),
            shutil.which("chromium"),
            shutil.which("google-chrome"),
            shutil.which("google-chrome-stable"),
            os.path.join(prefix, "bin/chromium-browser"),
            os.path.join(prefix, "bin/chromium"),
            "/data/data/com.termux/files/usr/bin/chromium-browser",
            "/data/data/com.termux/files/usr/bin/chromium",
            "/usr/lib64/chromium-browser/chromium-browser",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
        ]
        for c in candidates:
            if c and os.path.isfile(c) and os.access(c, os.X_OK):
                return c
        return None

    @staticmethod
    def _detect_display() -> bool:
        """Grafik ekran var mı? Termux'ta Termux:X11 soketi varsa DISPLAY=:0 ayarlanır."""
        if sys.platform == "win32":
            return True
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            return True
        if IS_TERMUX:
            prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
            if os.path.exists(os.path.join(prefix, "tmp/.X11-unix/X0")):
                os.environ["DISPLAY"] = ":0"
                return True
        return False

    def _manual_launch_hint(self) -> str:
        if sys.platform == "win32":
            return (f'  chrome.exe --remote-debugging-port={self.port} --user-data-dir="{CHROME_PROFILE_DIR}" {UYAP_BASE_URL}\n'
                    "  (veya baslat_windows.bat menüsünde 11. seçenek)")
        if IS_TERMUX:
            return ("  pkg install x11-repo && pkg install chromium\n"
                    f"  chromium-browser --no-sandbox --remote-debugging-port={self.port} {UYAP_BASE_URL}")
        return f"  chromium --remote-debugging-port={self.port} {UYAP_BASE_URL}"

    def launch_or_connect(self, headless: bool = False) -> tuple[bool, str]:
        """Geriye dönük uyumluluk: ensure_browser ile aynı."""
        return self.ensure_browser(headless=headless)

    def ensure_browser(self, headless: bool | None = None, wait_s: float | None = None) -> tuple[bool, str]:
        """CDP portu açıksa bağlanır; değilse platforma uygun tarayıcıyı başlatır ve port
        açılana kadar artan aralıklarla bekler. Hiçbir zaman istisna fırlatmaz."""
        if headless is not None:
            self.is_headless = headless
        # CanEditor gömülü tarayıcıyla çalışırken (CANASISTAN_GORUNMEZ=1) tarayıcı hiçbir zaman ön planda açılmaz
        if os.environ.get("CANASISTAN_GORUNMEZ"):
            self.is_headless = True
        if self._is_port_open():
            return True, f"Mevcut tarayıcı oturumuna bağlanıldı (Port {self.port})."

        if os.environ.get("CANASISTAN_ANDROID") == "1":
            # Android: tarayıcı CanEditor'un gizli WebView'ıdır (sunucu 127.0.0.1:9223'e köprüler); Chrome/Termux yok
            for _ in range(20):
                time.sleep(1.0)
                if self._is_port_open():
                    return True, "CanEditor gizli UYAP tarayıcısına bağlanıldı."
            self.last_error = "Gizli UYAP tarayıcısı yanıt vermiyor; CanEditor uygulamasını açıp yeniden deneyin."
            return False, self.last_error

        chrome_bin = self._find_chrome_bin()
        if not chrome_bin:
            if sys.platform == "win32":
                msg = "Google Chrome veya Microsoft Edge bulunamadı. Lütfen Chrome kurun."
            elif IS_TERMUX:
                msg = "Chromium bulunamadı. Termux'ta kurun: pkg install x11-repo && pkg install chromium"
            else:
                msg = "Chromium / Chrome bulunamadı. Lütfen kurun (örn. sudo dnf install chromium)."
            self.last_error = msg
            return False, msg

        try:
            CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.last_error = f"Tarayıcı profil klasörü oluşturulamadı ({CHROME_PROFILE_DIR}): {e}"
            return False, self.last_error

        cmd = [
            chrome_bin,
            f"--remote-debugging-port={self.port}",
            "--remote-debugging-address=127.0.0.1",
            "--remote-allow-origins=*",
            f"--user-data-dir={CHROME_PROFILE_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
        ]
        is_headless_shell = "headless-shell" in os.path.basename(chrome_bin).lower()
        has_display = self._detect_display()
        if self.is_headless or not has_display or is_headless_shell:
            self.is_headless = True
            # chrome-headless-shell zaten yalnızca başsızdır; --headless=new parametresi bazı sürümlerde reddedilir
            if not is_headless_shell:
                cmd.append("--headless=new")
            cmd += ["--disable-gpu", "--window-size=1366,900"]
        if IS_TERMUX or (sys.platform.startswith("linux") and hasattr(os, "geteuid") and os.geteuid() == 0):
            # Termux/Android'de Chromium sandbox'ı çalışmaz; /dev/shm yoktur.
            cmd += ["--no-sandbox", "--disable-dev-shm-usage"]
            if "--disable-gpu" not in cmd:
                cmd.append("--disable-gpu")
        cmd.append(UYAP_BASE_URL)

        try:
            if sys.platform == "win32":
                flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
                if self.is_headless:
                    flags |= 0x08000000  # CREATE_NO_WINDOW: arka planda hiç pencere/konsol göstermeden aç
                self.proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
            else:
                self.proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL, start_new_session=True)
        except Exception as e:
            self.last_error = f"Tarayıcı başlatılamadı ({os.path.basename(chrome_bin)}): {e}"
            return False, self.last_error

        if wait_s is None:
            wait_s = 60.0 if IS_TERMUX else 25.0
        deadline = time.time() + wait_s
        delay = 0.25
        while time.time() < deadline:
            time.sleep(delay)
            delay = min(delay * 1.5, 2.0)
            if self._is_port_open():
                self._fresh_launch = True
                mode_str = "Headless / Arka Plan" if self.is_headless else "Pencereli"
                name = "Edge" if "msedge" in chrome_bin.lower() else ("Chrome" if "chrome" in chrome_bin.lower() else "Chromium")
                return True, f"{name} başlatıldı ({mode_str}, Port {self.port})."
            rc = self.proc.poll()
            if rc is not None and time.time() > deadline - wait_s + 3:
                # Süreç hemen çıktı: aynı profille portsuz açık bir pencere var ya da tarayıcı çöktü.
                break

        rc = self.proc.poll() if self.proc else None
        if rc is not None:
            msg = (f"Tarayıcı açıldı ama hata ayıklama portu ({self.port}) açılmadı (çıkış kodu {rc}). "
                   f"Büyük olasılıkla aynı UYAP profiliyle ({CHROME_PROFILE_DIR.name}) portsuz açılmış bir "
                   "pencere zaten açık. O pencereyi tamamen kapatıp tekrar deneyin.")
        else:
            msg = (f"Tarayıcı başlatıldı ancak {int(wait_s)} sn içinde hata ayıklama portuna ({self.port}) "
                   "ulaşılamadı. Port başka bir program tarafından kullanılıyor olabilir.")
        self.last_error = msg
        return False, msg

    # ------------------------------------------------------------------
    # CDP yardımcıları
    # ------------------------------------------------------------------
    def _cdp_http(self, path: str, method: str = "GET", timeout: float = 2.5):
        """CDP HTTP uç noktası; bağlantı yoksa None döner (istisna fırlatmaz)."""
        url = f"http://127.0.0.1:{self.port}{path}"
        try:
            r = self._http.request(method, url, timeout=timeout)
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            return None

    def _is_port_open(self) -> bool:
        info = self._cdp_http("/json/version", timeout=1.5)
        return bool(info and (info.get("Browser") or info.get("webSocketDebuggerUrl")))

    def is_browser_alive(self) -> bool:
        return self._is_port_open()

    def _list_pages(self) -> list | None:
        tabs = self._cdp_http("/json/list")
        if tabs is None:
            return None
        return [t for t in tabs if t.get("type") == "page"]

    def _ws_url(self, tab: dict) -> str:
        ws = (tab.get("webSocketDebuggerUrl") or "").strip()
        if not ws:
            return ""
        # Android WebView DevTools soyut UNIX soketinden geldiği için host/port eksik olabilir
        # (örn. ws://localhost/devtools/page/1 veya ws:///devtools/page/1); her zaman 127.0.0.1:<port> yap.
        from urllib.parse import urlparse
        u = urlparse(ws)
        if u.scheme in ("ws", "wss") and (not u.hostname or u.hostname in ("localhost", "127.0.0.1", "::1") or u.port is None):
            path = u.path or "/"
            if u.query:
                path += "?" + u.query
            return f"{u.scheme}://127.0.0.1:{self.port}{path}"
        return ws.replace("ws://localhost:", "ws://127.0.0.1:")

    def _pick(self, pages: list, target: str) -> dict | None:
        def host_is(t, h):
            return _host_of(t.get("url") or "") == h
        uyap = [t for t in pages if host_is(t, self.UYAP_HOST)]
        edev = [t for t in pages if host_is(t, self.EDEVLET_HOST)]
        if target == "edevlet":
            return edev[0] if edev else None
        if target == "auto":
            # Mobil İmza akışı: e-Devlet sekmesi varsa o, yoksa UYAP sekmesi
            return (edev or uyap or [None])[0]
        # target == "uyap": API çağrıları için UYAP origin'li sekme şart
        # (giris sayfası değil, uygulama sayfası tercih edilir)
        uyap.sort(key=lambda t: "/giris" in (t.get("url") or ""))
        return uyap[0] if uyap else None

    def _open_uyap_tab(self, pages: list) -> dict | None:
        """UYAP sekmesi yoksa boş bir sekmeyi UYAP'a yönlendirir ya da yeni sekme açar."""
        # UETS'e ayrılmış gizli sayfa (about:blank#uets / uets.ptt.gov.tr) UYAP için kullanılmaz
        pages = [t for t in pages if "uets" not in (t.get("url") or "").lower()]
        blank = next((t for t in pages if (t.get("url") or "").startswith(self.BLANK_PREFIXES)
                      and t.get("webSocketDebuggerUrl")), None)
        # Android: /json/new yok; sunucu köprüsü yalnızca GİZLİ WebView'ları listeler, görünür ekran ele geçirilmez
        if not blank and os.environ.get("CANASISTAN_ANDROID") == "1":
            blank = next((t for t in pages if t.get("webSocketDebuggerUrl")), None)
        if blank:
            try:
                self._ws_call(self._ws_url(blank), "Page.navigate", {"url": UYAP_BASE_URL}, timeout=10)
            except Exception:
                blank = None
        if not blank and os.environ.get("CANASISTAN_ANDROID") != "1":
            from urllib.parse import quote
            # Yeni Chrome sürümleri /json/new için PUT ister; eskileri GET
            if self._cdp_http(f"/json/new?{quote(UYAP_BASE_URL, safe=':/')}", method="PUT") is None:
                self._cdp_http(f"/json/new?{quote(UYAP_BASE_URL, safe=':/')}", method="GET")
        deadline = time.time() + 20
        while time.time() < deadline:
            time.sleep(0.5)
            pages = self._list_pages() or []
            tab = self._pick(pages, "uyap")
            if tab and tab.get("webSocketDebuggerUrl"):
                return tab
        return None

    def get_tab(self, target: str = "uyap", create: bool = True, relaunch: bool = True) -> dict:
        """İstenen sekmeyi döndürür. Tarayıcı kapalıysa (relaunch) yeniden başlatır,
        UYAP sekmesi yoksa (create) açar. Bulunamazsa UyapBrowserError fırlatır."""
        pages = self._list_pages()
        if pages is None:
            if not relaunch:
                raise UyapBrowserError(f"Tarayıcıya bağlanılamadı (Port {self.port} kapalı).")
            print(f"[!] Tarayıcı (Port {self.port}) kapalı veya kapanmış; yeniden başlatılıyor...")
            ok, msg = self.ensure_browser()
            if not ok:
                raise UyapBrowserError(msg + "\n" + self._manual_launch_hint())
            print(f"[*] {msg} Not: Yeni açılan tarayıcıda UYAP oturumu yeniden açılmalıdır.")
            pages = self._list_pages() or []
            if not pages:
                time.sleep(1.5)
                pages = self._list_pages() or []

        tab = self._pick(pages, target)
        was_fresh = self._fresh_launch
        if tab is None and target in ("uyap", "auto") and self._fresh_launch:
            # Yeni başlatılan tarayıcının ilk sekmesi henüz UYAP adresine geçmemiş olabilir
            deadline = time.time() + 20
            while tab is None and time.time() < deadline:
                time.sleep(0.5)
                pages = self._list_pages() or []
                tab = self._pick(pages, target)
        self._fresh_launch = False
        if tab and not tab.get("webSocketDebuggerUrl"):
            raise UyapBrowserError("UYAP sekmesine başka bir araç (örn. açık DevTools penceresi) bağlı. "
                                   "Sekmedeki Geliştirici Araçları'nı kapatıp tekrar deneyin.")
        if tab:
            if was_fresh:
                self._wait_tab_host(tab)
            return tab
        if create and target in ("uyap", "auto"):
            tab = self._open_uyap_tab(pages)
            if tab:
                self._wait_tab_host(tab)
                return tab
            raise UyapBrowserError("UYAP sekmesi açılamadı. İnternet bağlantınızı kontrol edin.")
        raise UyapBrowserError("Açık bir UYAP sekmesi bulunamadı.")

    def _wait_tab_host(self, tab: dict, timeout: float = 25.0) -> bool:
        """Sekmedeki belge gerçekten UYAP/e-Devlet adresine yüklenene kadar bekler."""
        want = _host_of(tab.get("url") or "") or self.UYAP_HOST
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                res = self._ws_call(self._ws_url(tab), "Runtime.evaluate", {
                    "expression": "location.hostname + '|' + document.readyState",
                    "returnByValue": True,
                }, timeout=5)
                val = str(res.get("result", {}).get("value") or "")
                host, _, state = val.partition("|")
                if host == want and state in ("interactive", "complete"):
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def get_uyap_tab(self, target: str = "auto") -> dict | None:
        """Geriye dönük uyumluluk: istisna fırlatmadan sekme döndürür."""
        try:
            return self.get_tab(target=target, create=False, relaunch=False)
        except Exception:
            return None

    def ensure_ready(self, target: str = "uyap") -> tuple[bool, str]:
        """Tarayıcı + UYAP sekmesi hazır mı? (gerekirse başlatır / açar)"""
        try:
            self.get_tab(target=target, create=True, relaunch=True)
            return True, "Tarayıcı ve UYAP sekmesi hazır."
        except UyapBrowserError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Tarayıcı hazırlanamadı: {e}"

    @staticmethod
    def _ws_call(ws_url: str, method: str, params: dict, timeout: float = 30.0):
        ws = websocket.create_connection(ws_url, timeout=timeout, suppress_origin=True)
        try:
            msg_id = random.randint(1000, 999999)
            ws.send(json.dumps({"id": msg_id, "method": method, "params": params}))
            deadline = time.time() + timeout
            while time.time() < deadline:
                resp = json.loads(ws.recv())
                if resp.get("id") == msg_id:
                    if "error" in resp:
                        raise RuntimeError(f"CDP Hatası: {resp['error'].get('message', resp['error'])}")
                    return resp.get("result", {})
            raise TimeoutError(f"CDP yanıtı {timeout} sn içinde gelmedi ({method}).")
        finally:
            try:
                ws.close()
            except Exception:
                pass

    def navigate(self, url: str, target: str = "uyap") -> bool:
        try:
            tab = self.get_tab(target=target, create=True)
            self._ws_call(self._ws_url(tab), "Page.navigate", {"url": url}, timeout=15)
            return True
        except Exception:
            return False

    def eval_js(self, js_expression: str, timeout: float = 90.0, retries: int = 2, target: str = "uyap"):
        """Tarayıcı sekmesinde (varsayılan: UYAP origin'li sekme) asenkron JS çalıştırır.
        Tarayıcı kapanmışsa yeniden başlatır, UYAP sekmesi yoksa açar."""
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                tab = self.get_tab(target=target, create=True, relaunch=True)
            except UyapBrowserError as e:
                last_err = e
                if attempt < retries:
                    time.sleep(1.0 + attempt)
                    continue
                raise
            try:
                res = self._ws_call(self._ws_url(tab), "Runtime.evaluate", {
                    "expression": js_expression,
                    "awaitPromise": True,
                    "returnByValue": True,
                }, timeout=timeout)
                if "exceptionDetails" in res:
                    exc = res["exceptionDetails"]
                    raise RuntimeError(f"JS Hatası: {exc.get('text')} {exc.get('exception', {}).get('description', '')}")
                return res.get("result", {}).get("value")
            except (websocket.WebSocketTimeoutException, TimeoutError) as e:
                last_err = e
                if attempt < retries:
                    time.sleep(2.5)
                    continue
                raise
            except Exception as e:
                last_err = e
                if attempt < retries:
                    time.sleep(1.5)
                    continue
                raise
        if last_err:
            raise last_err

    # ------------------------------------------------------------------
    # e-İmza (Adalet e-İmza Client / ArkSigner, localhost:5975)
    # ------------------------------------------------------------------
    def check_arksigner(self) -> tuple[bool, str]:
        try:
            r = self._http.get(f"{ARKSIGNER_URL}/api/v1/signature/getCertificates", timeout=6)
        except requests.exceptions.RequestException:
            if IS_TERMUX:
                return False, "e-İmza (ArkSigner) Android/Termux'ta çalışmaz. Termux'ta Mobil İmza kullanın."
            return False, ("Adalet e-İmza Client (ArkSigner) çalışmıyor: localhost:5975'e bağlanılamadı. "
                           "Uygulamayı başlatıp e-İmza kartını takın.")
        if r.status_code != 200:
            return False, f"ArkSigner yanıt vermedi (HTTP {r.status_code})."
        return True, "ArkSigner hazır."

    def kart_takili_mi(self) -> bool:
        """e-İmza istemcisinde (5975) sertifikası okunabilen hazır bir kart var mı?"""
        try:
            r = self._http.get(f"{ARKSIGNER_URL}/api/v1/signature/getCertificates", timeout=6)
            kartlar = (r.json() or {}).get("data") or [] if r.status_code == 200 else []
        except (requests.exceptions.RequestException, ValueError):
            return False
        return any(k.get("ready") is not False and k.get("certificates") for k in kartlar)

    def akilli_oturum_ac(self, pin: str = "", tc: str = "", gsm: str = "", operator: str = "",
                         status_cb=None, sure_siniri_s: float | None = None, dur=None,
                         beklemeler=MOBIL_IMZA_BEKLEMELERI, uyku=time.sleep,
                         confirm_mobil=None) -> tuple[bool, str]:
        """UYAP oturumunu açar/yeniler. Kural:
          * e-İmza kartı takılıysa (ve PIN varsa) e-İmza ile girilir — sorun yok.
          * Otomatik Mobil İmza KAPALIDIR: kart takılı değilse veya e-İmza başarısız olursa kendiliğinden
            Mobil İmza isteği gönderilmez; yalnızca confirm_mobil açıkça onay verirse gönderilir.
          * Kartın reddettiği PIN asla yeniden denenmez (kart bloke olmasın).
        sure_siniri_s: toplam süre sınırı (None = sınırsız); dur: threading.Event — set edilince durur."""
        def bildir(m):
            (status_cb or file_logger.info)(m)

        pin, tc, gsm = str(pin or "").strip(), str(tc or "").strip(), str(gsm or "").strip()
        if not tc or not gsm:
            c_tc, c_gsm, c_op = mobil_imza_ayarlari()
            tc, gsm, operator = tc or c_tc, gsm or c_gsm, operator or c_op
        mobil_var = bool(tc and gsm)
        if not pin and not (mobil_var and confirm_mobil):
            return False, ("Otomatik mobil imza kapalı: oturumu açmak için e-İmza PIN'i girin veya "
                           "'Mobil imza isteği gönderilsin mi?' onayı verin.")
        bas = time.monotonic()
        deneme, son_hata = 0, ""

        def sure_doldu() -> bool:
            return (dur is not None and dur.is_set()) or (sure_siniri_s is not None and time.monotonic() - bas > sure_siniri_s)

        while not sure_doldu():
            try:
                if self.is_logged_in():
                    return True, "UYAP oturumu açık."
            except Exception:  # tarayıcı/bağlantı geçici olarak yoksa giriş denemesi zaten yeniden kurar
                pass
            pin_hash = hashlib.sha256(pin.encode("utf-8")).hexdigest() if pin else ""
            if pin and pin_hash not in self._rejected_pins and self.kart_takili_mi():
                bildir("🔑 e-İmza kartı takılı: e-İmza ile oturum açılıyor…")
                ok, msg = self.auto_relogin(pin=pin)
                if ok:
                    return True, msg
                son_hata = msg
                bildir(f"⚠️ e-İmza ile girilemedi: {msg}")
            istek_onay = False
            if mobil_var:
                if callable(confirm_mobil):
                    istek_onay = bool(confirm_mobil())
                    if not istek_onay:
                        confirm_mobil = False
                elif confirm_mobil is True:
                    istek_onay = True
                    confirm_mobil = False
            if mobil_var and istek_onay:
                deneme += 1
                bildir(f"📲 Kullanıcı onayıyla Mobil İmza gönderiliyor (deneme {deneme}) — telefonunuzdaki bildirimi onaylayın.")
                ok, msg = self.login_with_mobil_imza(
                    tc, gsm, operator or "turktelekom", status_cb=status_cb, confirmed=True
                )
                if ok:
                    return True, msg
                son_hata = msg
                if not callable(confirm_mobil) and (not pin or pin_hash in self._rejected_pins):
                    return False, f"Mobil İmza ile girilemedi (otomatik tekrar kapalı): {msg}"
                bekle = beklemeler[min(deneme - 1, len(beklemeler) - 1)]
                bildir(f"⚠️ Mobil İmza ile girilemedi: {msg} — {bekle} sn sonra yeniden denenecek.")
            else:
                if not pin or pin_hash in self._rejected_pins:
                    bildir("⏸️ Oturum kapalı — otomatik Mobil İmza gönderilmiyor. İstek göndermek için kullanıcı onayı gereklidir.")
                    return False, f"Oturum kapalı (otomatik mobil imza kapalı). {('Son hata: ' + son_hata) if son_hata else 'Onay bekleniyor.'}".strip()
                # Yalnız e-İmza etkin: kart takılana / bağlantı gelene kadar bekle
                deneme += 1
                bekle = beklemeler[min(deneme - 1, len(beklemeler) - 1)]
                bildir(f"⏳ e-İmza kartı bekleniyor (otomatik Mobil İmza kapalı); {bekle} sn sonra yeniden denenecek.")
            # Beklerken kart takılırsa ya da durdurulursa hemen dön
            hedef = time.monotonic() + bekle
            while time.monotonic() < hedef and not sure_doldu():
                uyku(min(5.0, max(0.0, hedef - time.monotonic())))
                if pin and pin_hash not in self._rejected_pins and self.kart_takili_mi():
                    break
        return False, f"Oturum açılamadı (süre doldu/durduruldu). Son hata: {son_hata or '-'}"

    # Kart okuyucu oturumu takılınca (ilk girişten sonra "Kart okuyucudan sertifika alınamadı")
    # e-İmza istemcisini yeniden başlatmak gerekir; bunu otomatik yapar.
    _ESIGN_EXE_CANDIDATES = (
        r"%LOCALAPPDATA%\Adalet E-imza\Adalet E-imza.exe",
        r"%LOCALAPPDATA%\Programs\Ark\ArkSigner\ArkSigner.exe",
        r"%ProgramFiles%\Adalet E-imza\Adalet E-imza.exe",
        r"%ProgramFiles(x86)%\Adalet E-imza\Adalet E-imza.exe",
    )

    def restart_esign_client(self, wait_s: float = 45.0) -> tuple[bool, str]:
        """Windows: 5975 portunu dinleyen e-İmza istemcisini (Adalet E-imza / ArkSigner) kapatıp yeniden
        açar ve kart hazır olana kadar bekler. Diğer sistemlerde yalnızca bilgi döner."""
        if os.name != "nt":
            return False, "e-İmza istemcisini yeniden başlatın (otomatik yeniden başlatma yalnızca Windows'ta)."
        exe = None
        try:
            ps = ("$c=Get-NetTCPConnection -LocalPort 5975 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1;"
                  "if($c){(Get-Process -Id $c.OwningProcess).Path}")
            out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                                 text=True, timeout=20, creationflags=0x08000000).stdout.strip()
            if out and os.path.exists(out):
                exe = out
        except Exception:
            pass
        if not exe:
            exe = next((os.path.expandvars(c) for c in self._ESIGN_EXE_CANDIDATES
                        if os.path.exists(os.path.expandvars(c))), None)
        if not exe:
            return False, "e-İmza istemcisi (Adalet E-imza / ArkSigner) bulunamadı; elle yeniden başlatın."
        name = os.path.basename(exe)
        file_logger.warning("e-İmza istemcisi yeniden başlatılıyor: %s", exe)
        subprocess.run(["taskkill", "/F", "/T", "/IM", name], capture_output=True, timeout=20, creationflags=0x08000000)
        time.sleep(2.0)
        try:
            subprocess.Popen([exe], cwd=os.path.dirname(exe), creationflags=0x00000008 | 0x00000200,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            return False, f"e-İmza istemcisi başlatılamadı: {e}"
        t0 = time.time()
        while time.time() - t0 < wait_s:
            time.sleep(2.0)
            try:
                r = self._http.get(f"{ARKSIGNER_URL}/api/v1/signature/getCertificates", timeout=6)
                cards = (r.json() or {}).get("data") or []
                if any(c.get("ready") is not False and c.get("certificates") for c in cards):
                    file_logger.info("e-İmza istemcisi hazır (%.0f sn)", time.time() - t0)
                    return True, f"e-İmza istemcisi yeniden başlatıldı ({name})."
            except Exception:
                continue
        return False, "e-İmza istemcisi yeniden başlatıldı ama kart hazır görünmüyor; kartı çıkarıp takın."

    def auto_relogin(self, pin: str = DEFAULT_E_IMZA_PIN, _restarted: bool = False) -> tuple[bool, str]:
        """
        ArkSigner (http://localhost:5975) üzerinden PIN ile challenge imzalatır ve tarayıcıdaki
        UYAP sekmesinde (UYAP'ın kendi akışıyla aynı: web1.uyap -> login.uyap ->
        kullanici_bilgileri.uyap) oturumu açar; sonunda oturumun gerçekten açıldığını doğrular.
        PIN hiçbir yere yazılmaz/loglanmaz.
        """
        pin = str(pin or "").strip()
        if not pin:
            return False, "e-İmza PIN kodu girilmedi."
        pin_hash = hashlib.sha256(pin.encode("utf-8")).hexdigest()
        if pin_hash in self._rejected_pins:
            return False, ("Bu PIN bu çalıştırmada kart tarafından zaten reddedildi. Kartın bloke olmaması için "
                           "aynı PIN tekrar denenmedi; doğru PIN ile yeniden deneyin.")
        try:
            # 1. Önce tarayıcı + UYAP sekmesi hazır olsun (PIN boşa harcanmasın)
            ok, msg = self.ensure_ready("uyap")
            if not ok:
                return False, msg

            # 2. Sertifika
            ok, msg = self.check_arksigner()
            if not ok:
                return False, msg
            r_cert = self._http.get(f"{ARKSIGNER_URL}/api/v1/signature/getCertificates", timeout=8)
            cards = (r_cert.json() or {}).get("data") or []
            if not cards:
                return False, "ArkSigner'a bağlı e-İmza kartı bulunamadı. Kartı takıp tekrar deneyin."
            certs = []
            for card in cards:
                if card.get("ready") is False:
                    continue
                certs.extend(card.get("certificates") or [])
            if not certs:
                return False, "e-İmza kartında sertifika bulunamadı (kart hazır değil veya okunamadı)."
            valid = [c for c in certs if c.get("valid", True)]
            if not valid:
                return False, "e-İmza sertifikanızın geçerlilik süresi uygun değil (süresi dolmuş olabilir)."
            valid.sort(key=lambda c: not c.get("default", False))
            cert = valid[0]

            # 3. Challenge imzalat (UYAP'ın kullandığı sabit içerik)
            try:
                r_sign = self._http.post(f"{ARKSIGNER_URL}/api/v1/signature/sign", json={
                    "certificateId": cert.get("certificateId"),
                    "password": pin,
                    "content": SIGN_CHALLENGE,
                }, timeout=45)
            except requests.exceptions.Timeout:
                return False, "ArkSigner imzalama isteği zaman aşımına uğradı. Kartı çıkarıp takıp tekrar deneyin."
            except requests.exceptions.RequestException:
                return False, "ArkSigner'a imza isteği gönderilemedi (servis kapandı mı?)."
            try:
                s_data = r_sign.json() or {}
            except ValueError:
                s_data = {}
            meta = s_data.get("metadata") or {}
            if r_sign.status_code != 200 or meta.get("STATUS") != "SUCCESS":
                emsg = meta.get("MESSAGE") or f"HTTP {r_sign.status_code}"
                if any(w in tr_lower(emsg) for w in _PIN_ERROR_WORDS):
                    self._rejected_pins.add(pin_hash)
                    return False, f"e-İmza PIN hatası: {emsg} (Dikkat: art arda hatalı PIN kartı bloke eder.)"
                # Kart okuyucu oturumu takıldı: istemciyi yeniden başlatıp BİR kez daha dene
                # (kart PIN'i hiç görmediği için PIN deneme sayacı artmaz)
                low = tr_lower(emsg)
                if not _restarted and any(k in low for k in ("sertifika alınamadı", "sertifika alinamadi", "okuyucu", "kart")):
                    file_logger.warning("ArkSigner kart hatası (%s); istemci yeniden başlatılıp tekrar denenecek", emsg)
                    ok_r, msg_r = self.restart_esign_client()
                    if ok_r:
                        return self.auto_relogin(pin, _restarted=True)
                    return False, f"e-İmza imzalama hatası: {emsg}. {msg_r}"
                return False, f"e-İmza imzalama hatası: {emsg}"
            sig_res = s_data.get("data") if isinstance(s_data.get("data"), dict) else s_data
            sig, tx_id = sig_res.get("signedData"), sig_res.get("txId")
            if not sig or not tx_id:
                return False, "ArkSigner imza veya işlem numarası (txId) üretemedi."

            # 4. UYAP sekmesinde giriş
            js_login = f"""
            (async () => {{
                try {{
                    const sig = {json.dumps(sig)};
                    const txId = {json.dumps(tx_id)};
                    const r1 = await fetch("/web1.uyap?signature=" + encodeURIComponent(sig) + "&txId=" + encodeURIComponent(txId), {{
                        method: "GET", headers: {{"Cache-Control": "no-cache"}}, credentials: "include"
                    }});
                    const d1 = await r1.json().catch(() => null);
                    if (!d1 || !d1.success) {{
                        return {{success: false, step: "web1.uyap", status: r1.status,
                                 message: d1 && (d1.message || d1.errorMessage || (d1.error && d1.error.message)) || null}};
                    }}
                    const r2 = await fetch("/login.uyap", {{
                        method: "POST", credentials: "include",
                        headers: {{"Content-Type": "application/json", "Cache-Control": "no-cache"}},
                        body: JSON.stringify({{}})
                    }});
                    if (!r2.ok) return {{success: false, step: "login.uyap", status: r2.status}};
                    const r3 = await fetch("/kullanici_bilgileri.uyap", {{
                        method: "POST", credentials: "include",
                        headers: {{"Content-Type": "application/json", "Cache-Control": "no-cache"}},
                        body: JSON.stringify({{}})
                    }});
                    const uinfo = await r3.json().catch(() => null);
                    if (!uinfo || !(uinfo.tcKimlikNo || uinfo.tckn)) {{
                        return {{success: false, step: "kullanici_bilgileri.uyap", status: r3.status}};
                    }}
                    localStorage.setItem("loginState", "true");
                    sessionStorage.setItem("showKvkPopup", "true");
                    sessionStorage.setItem("showPopupDuyuru2", "true");
                    sessionStorage.setItem("kullanici", JSON.stringify(uinfo));
                    return {{success: true, user: uinfo}};
                }} catch(e) {{
                    return {{success: false, error: e.toString()}};
                }}
            }})()
            """
            res = self.eval_js(js_login, timeout=30.0, retries=0, target="uyap")
            if not (res and res.get("success")):
                res = res or {}
                detail = res.get("message") or res.get("error") or f"adım: {res.get('step')}, HTTP {res.get('status')}"
                return False, f"UYAP e-İmza girişini kabul etmedi ({detail})."

            # 5. Kesin doğrulama + sayfayı oturum açık haliyle yenile
            if not self.is_logged_in():
                return False, "e-İmza imzası alındı ama UYAP oturumu doğrulanamadı. Tekrar deneyin."
            self.navigate(UYAP_BASE_URL + "/", target="uyap")
            time.sleep(2.0)
            u = res.get("user") or {}
            full_name = f"{u.get('adi', '')} {u.get('soyadi', '')}".strip() or "Avukat"
            return True, f"e-İmza ile oturum açıldı ({full_name})"
        except KeyboardInterrupt:
            return False, "e-İmza girişi iptal edildi."
        except Exception as e:
            return False, f"Otomatik e-İmza giriş hatası: {e}"

    def is_logged_in(self) -> bool:
        """/kullanici_bilgileri.uyap ile aktif UYAP oturumunu kesin olarak doğrular."""
        pages = self._list_pages() or []
        uyap_tab = [t for t in pages if self.UYAP_HOST in (t.get("url") or "")]
        if not uyap_tab:
            return False
        js = """
        (async () => {
            try {
                const r = await fetch("/kullanici_bilgileri.uyap", {
                    method: "POST", credentials: "include",
                    headers: {"Content-Type": "application/json", "Cache-Control": "no-cache"},
                    body: "{}"
                });
                const ct = r.headers.get("content-type") || "";
                if (!r.ok || ct.includes("text/html")) return false;
                const d = await r.json().catch(() => null);
                return Boolean(d && (d.tcKimlikNo || d.tckn));
            } catch(e) {
                try {
                    return localStorage.getItem("loginState") === "true";
                } catch(e2) {
                    return false;
                }
            }
        })()
        """
        try:
            return bool(self.eval_js(js, timeout=12.0, retries=1, target="uyap"))
        except Exception:
            return False

    def check_login_and_user(self) -> dict:
        """UYAP oturumu açık mı, TCKN/Ad/Soyad nedir? Hata olursa {} döner, 'error' anahtarına
        anlaşılır neden yazılır (tarayıcı yok vb.)."""
        pages = self._list_pages() or []
        uyap_tab = [t for t in pages if self.UYAP_HOST in (t.get("url") or "")]
        if not uyap_tab:
            return {"error": "Açık UYAP sekmesi bulunamadı", "loginState": "false"}
        js = """
        (async () => {
            const url = window.location.href;
            let user = null;
            try {
                const r = await fetch("/kullanici_bilgileri.uyap", {
                    method: "POST", credentials: "include",
                    headers: {"Content-Type": "application/json", "Cache-Control": "no-cache"},
                    body: "{}"
                });
                const ct = r.headers.get("content-type") || "";
                if (r.ok && !ct.includes("text/html")) {
                    const d = await r.json().catch(() => null);
                    if (d && (d.tcKimlikNo || d.tckn)) {
                        user = d;
                        sessionStorage.setItem("kullanici", JSON.stringify(user));
                        localStorage.setItem("loginState", "true");
                    }
                }
                if (!user) {
                    sessionStorage.removeItem("kullanici");
                    localStorage.removeItem("loginState");
                }
            } catch (e) {
                user = null;
            }
            return {url, loginState: user ? "true" : "false", user, title: document.title};
        })()
        """
        try:
            return self.eval_js(js, timeout=15.0, retries=1, target="uyap") or {}
        except UyapBrowserError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"Oturum kontrol edilemedi: {e}"}

    # ------------------------------------------------------------------
    # Mobil İmza (e-Devlet)
    # ------------------------------------------------------------------
    _JS_MOBIL_STATE = r"""
    (() => {
        const url = location.href;
        const host = location.hostname;
        const title = document.title || "";
        const text = (document.body && document.body.innerText) || "";
        const vis = e => !!(e && (e.offsetWidth || e.offsetHeight || (e.getClientRects && e.getClientRects().length)));
        const btnText = b => (b.innerText || b.value || b.getAttribute('title') || b.getAttribute('aria-label') || '').trim();
        const allBtns = Array.from(document.querySelectorAll('button, input[type=submit], input[type=button], a.btn, a[role=button], a.button, a')).filter(vis);
        const buttons = allBtns.map(b => ({
            tag: b.tagName.toLowerCase(),
            id: b.id || '',
            name: b.name || '',
            type: b.type || '',
            text: btnText(b)
        })).filter(b => b.text.length > 0 && b.text.length < 60);

        const btnTexts = buttons.map(b => b.text);

        const trid = document.getElementById('tridField');
        const gsm = document.getElementById('gsmField');
        const isFormVis = !!(trid && gsm && vis(trid) && vis(gsm));

        const errEl = Array.from(document.querySelectorAll('.fieldError, .formErrors, .errorMessage, .alert-danger, .error-message'))
            .find(e => vis(e) && (e.innerText || '').trim().length > 3);

        let fp = "";
        const m = text.match(/Parmak\s*[İI]zi\s*[:\-]?\s*([A-F0-9]{2,4}(?:[\s\-]+[A-F0-9]{2,4})+)/i) ||
                  text.match(/\b([A-F0-9]{4}(?:\s+[A-F0-9]{4}){3,})\b/);
        if (m) fp = m[1].trim();

        let page = "other";
        if (host === "avukat.uyap.gov.tr") {
            page = url.includes("/giris") ? "uyap_giris" : "uyap_app";
        } else if (host.includes("turkiye.gov.tr")) {
            const isOAuth = url.toLowerCase().includes("/oauth") || 
                            text.includes("erişim hakkı istemektedir") || 
                            text.includes("Uygulama İzin Onayı") ||
                            text.includes("Kimlik Doğrulama Seviyesi");
            if (isOAuth) {
                page = "oauth";
            } else if (isFormVis) {
                page = "mobil_form";
            } else if (btnTexts.some(t => /^İmzala$/i.test(t))) {
                page = "taahhut";
            } else if (fp || /bekleniyor|operat[öo]r|onaylanması/i.test(text)) {
                page = "waiting";
            } else if (!url.includes("Mobil-Imza")) {
                page = "edevlet_other";
            }
        }
        return {
            url, host, title, page, fp,
            buttons,
            btnTexts,
            textSnippet: text.slice(0, 300).replace(/\s+/g, ' '),
            ready: document.readyState,
            error: errEl ? errEl.innerText.trim().slice(0, 300) : ""
        };
    })()
    """

    _JS_MOBIL_SELECT = r"""
    (() => {
        const dd = document.querySelector(".edevlet-dropdown");
        if (!dd) return "no_dropdown";
        const reactKey = Object.keys(dd).find(k => k.startsWith("__reactFiber"));
        let curr = reactKey ? dd[reactKey] : null;
        while (curr) {
            const p = curr.memoizedProps;
            if (p && p.onItemClick && Array.isArray(p.items)) {
                const it = p.items.find(i => (i.name || "").includes("Mobil"));
                if (it) { p.onItemClick({itemData: it, itemIndex: p.items.indexOf(it)}); return "invoked"; }
            }
            curr = curr.return;
        }
        const item = Array.from(document.querySelectorAll('.dx-list-item, [role="option"]'))
            .find(e => (e.innerText || '').trim().startsWith('Mobil İmza') && e.getBoundingClientRect().width > 0);
        if (item) { item.click(); return "clicked"; }
        const btn = dd.querySelector('.dx-dropdownbutton-action') || dd;
        btn.click();
        return "opened_dropdown";
    })()
    """

    def _edevlet_page_message(self) -> str:
        """e-Devlet sayfasındaki uyarı/hata metnini bulur (seçicilerle yakalanamayan mesajlar için);
        sayfanın kısa bir özetini ayrıntılı günlüğe yazar. Kişisel veri (TC/GSM) maskelenir."""
        js = r"""(() => {
            const t = (document.body && document.body.innerText) || "";
            return {url: location.href, text: t.slice(0, 4000)};
        })()"""
        try:
            r = self.eval_js(js, timeout=8.0, retries=0, target="auto") or {}
        except Exception:
            return ""
        text = re.sub(r"\b\d{10,11}\b", "***", str(r.get("text") or ""))
        file_logger.info("e-Devlet sayfası (%s): %s", r.get("url"), text[:1500].replace("\n", " | "))
        keys = ("hata", "başarısız", "basarisiz", "geçersiz", "gecersiz", "uyuşm", "abone", "operatör",
                "iptal", "zaman aşımı", "zaman asimi", "bulunamadı", "sertifika", "reddedildi", "deneyiniz", "uyarı")
        for line in text.splitlines():
            ln = line.strip()
            if 8 < len(ln) < 300 and any(k in tr_lower(ln) for k in keys):
                return ln
        return ""

    def login_with_mobil_imza(
        self,
        tc: str,
        gsm: str,
        operator: str = "turktelekom",
        status_cb=None,
        timeout_s: float = 240.0,
        confirmed: bool = False,
        confirm_cb=None,
    ) -> tuple[bool, str]:
        """
        e-Devlet Mobil İmza ile UYAP Avukat Portal oturumu açar. Sayfa durumuna göre çalışan
        bir durum makinesidir (sabit beklemeler yerine): UYAP giriş -> e-Devlet Mobil İmza formu
        -> (Taahhütname / İmzala) -> telefonda onay bekleme -> (OAuth Onayla) -> UYAP.
        Sonunda /kullanici_bilgileri.uyap ile oturumun gerçekten açıldığı doğrulanır.
        Ctrl+C ile iptal edilebilir (istisna fırlatmaz).
        """
        def log_msg(m):
            if status_cb:
                status_cb(m)
            else:
                print(m)

        try:
            ok, msg = self.ensure_ready("auto")
            if not ok:
                return False, msg

            if self.is_logged_in():
                uinfo = self.check_login_and_user()
                usr = uinfo.get("user") or {}
                name = f"{usr.get('ad', '') or usr.get('adi', '')} {usr.get('soyad', '') or usr.get('soyadi', '')}".strip()
                return True, f"Zaten aktif UYAP oturumu mevcut: {name or 'Avukat'}"

            tc = re.sub(r"\D", "", str(tc))
            gsm_digits = re.sub(r"\D", "", str(gsm))
            if gsm_digits.startswith("90") and len(gsm_digits) == 12:
                gsm_digits = gsm_digits[2:]
            elif gsm_digits.startswith("0") and len(gsm_digits) == 11:
                gsm_digits = gsm_digits[1:]
            if len(tc) != 11:
                return False, "T.C. Kimlik No 11 haneli olmalıdır."
            if len(gsm_digits) != 10 or not gsm_digits.startswith("5"):
                return False, "GSM No 5 ile başlayan 10 hane olmalıdır (örn. 5321234567)."

            op_map = {"1": "turkcell", "turkcell": "turkcell",
                      "2": "turktelekom", "turktelekom": "turktelekom", "avea": "turktelekom", "tt": "turktelekom",
                      "3": "vodafone", "vodafone": "vodafone"}
            op_id = op_map.get(str(operator).lower().strip(), "")
            if not op_id:
                if gsm_digits.startswith(("50", "55")):
                    op_id = "turktelekom"
                elif gsm_digits.startswith("54"):
                    op_id = "vodafone"
                else:
                    op_id = "turkcell"

            js_fill = f"""
            (() => {{
                const tr = document.getElementById('tridField');
                const gsm = document.getElementById('gsmField');
                if (!tr || !gsm) return {{ok: false, error: "Form alanları bulunamadı"}};
                const setVal = (el, v) => {{
                    const proto = Object.getPrototypeOf(el);
                    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (desc && desc.set) desc.set.call(el, v); else el.value = v;
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    el.dispatchEvent(new Event('blur', {{bubbles: true}}));
                }};
                setVal(tr, {json.dumps(tc)});
                setVal(gsm, {json.dumps(gsm_digits)});
                const op = document.getElementById({json.dumps(op_id)});
                if (!op) return {{ok: false, error: "Operatör seçeneği bulunamadı: {op_id}"}};
                op.click(); op.checked = true;
                op.dispatchEvent(new Event('change', {{bubbles: true}}));
                const trOk = tr.value.replace(/\\D/g, '') === {json.dumps(tc)};
                const gsmOk = gsm.value.replace(/\\D/g, '').endsWith({json.dumps(gsm_digits)});
                if (!trOk || !gsmOk) return {{ok: false, error: "Form alanlarına değer yazılamadı"}};
                if ({json.dumps(bool(getattr(self, "_mobil_fill_only", False)))}) return {{ok: true, filled_only: true}};
                const btn = document.querySelector('button[name="submitButton"]') ||
                            document.querySelector('input[name="submitButton"]');
                if (!btn) return {{ok: false, error: "Devam Et butonu bulunamadı"}};
                btn.click();
                return {{ok: true}};
            }})()
            """
            js_smart_click = r"""
            (() => {
                const vis = e => !!(e && (e.offsetWidth || e.offsetHeight || (e.getClientRects && e.getClientRects().length)));
                const btnText = b => (b.innerText || b.value || b.getAttribute('title') || b.getAttribute('aria-label') || '').trim();
                const all = Array.from(document.querySelectorAll('button, input[type=submit], input[type=button], a.btn, a[role=button], a.button, a')).filter(vis);
                
                // KESİN KARA LİSTE: İptal, vazgeç, geri ve "Devamını Oku" gibi bilgi bağlantıları ASLA tıklanmaz!
                const blacklist = /(iptal|vazge[çc]|geri|hay[ıi]r|red|\boku\b|detay|yard[ıi]m|bilgi|kapat)/i;

                // 1. Birincil öncelik: Tam onay ve devam aksiyon kelimeleri (Onayla, Devam Et, Tamam, İzin Ver)
                const pat1 = /^(Onayla(y[ıi]n)?|Devam(\s+Et)?|Tamam|İzin\s*Ver|Uygulama(ya\s*Git)?|Sistem(e\s*Git)?|UYAP('a\s*Git)?|Kabul(\s*Et)?|Giriş(\s*Yap)?)$/i;
                let found = all.find(b => {
                    const txt = btnText(b);
                    return pat1.test(txt) && !blacklist.test(txt);
                });
                
                // 2. İkincil öncelik: submitButton ID/Name veya primary buton (Kara liste hariç)
                if (!found) {
                    found = all.find(b => {
                        const txt = btnText(b);
                        const isSub = (b.name === 'submitButton' || b.id === 'submitButton' || (b.className && /btn-primary|btn-success/.test(b.className.toString())));
                        return isSub && txt.length > 0 && !blacklist.test(txt);
                    });
                }

                // 3. Üçüncül öncelik: İçeren onay ifadeleri (Kara liste kesinlikle hariç)
                if (!found) {
                    const pat3 = /(Onayla|Devam\s+Et|İzin\s*Ver|Uygulamaya|Kabul\s*Et)/i;
                    found = all.find(b => {
                        const txt = btnText(b);
                        return pat3.test(txt) && !blacklist.test(txt);
                    });
                }

                if (found) {
                    const txt = btnText(found) || found.tagName;
                    const id = found.id || found.name || '';
                    found.click();
                    return {clicked: true, text: txt, id: id, tag: found.tagName.toLowerCase()};
                }
                return {clicked: false};
            })()
            """

            if not ask_mobil_imza_onayi(gsm=gsm_digits, confirm_cb=confirm_cb, confirmed=confirmed):
                msg_block = "Otomatik mobil imza kapalı: 'Mobil imza isteği gönderilsin mi?' onayı verilmedi."
                log_msg(f"[i] {msg_block}")
                return False, msg_block

            log_msg("[*] UYAP Mobil İmza girişi başlatılıyor...")
            st0 = self.eval_js(self._JS_MOBIL_STATE, timeout=10.0, target="auto") or {}
            if st0.get("page") not in ("uyap_giris", "mobil_form"):
                self.navigate(UYAP_BASE_URL + "/giris", target="auto")
                time.sleep(2.0)

            deadline = time.time() + timeout_s
            last_select = last_click = 0.0
            filled_at = signed_at = giris_since = 0.0
            fp_shown = waiting_shown = False
            last_page = ""
            btn_clicked_history = set()

            while time.time() < deadline:
                time.sleep(1.0)

                # 1. Oturum açıldı mı kontrol et
                if self.is_logged_in():
                    log_msg("✅ UYAP oturumu başarıyla doğrulandı!")
                    break

                try:
                    st = self.eval_js(self._JS_MOBIL_STATE, timeout=8.0, retries=0, target="auto") or {}
                except UyapBrowserError as e:
                    return False, str(e)
                except Exception:
                    continue  # sayfa geçişi / redirect sırasında context yok edilebilir

                page = st.get("page", "")
                btn_texts = st.get("btnTexts", []) or [b.get("text", "") for b in st.get("buttons", [])]
                curr_url = st.get("url", "")
                title = st.get("title", "")

                # Sayfa veya buton değiştiğinde canlı tarama ve kayıt tutma
                state_sig = f"{page}|{curr_url}|{tuple(btn_texts)}"
                if state_sig != last_page:
                    if page != (last_page.split("|", 1)[0] if last_page else None):
                        # Tanı: hangi adımda takıldığı Görevler/Tanı günlüğünde görünsün
                        log_msg(f"[i] Giriş adımı: {page or 'bilinmiyor'} ({(curr_url or '')[:80]})")
                    last_page = state_sig
                    file_logger.info(f"[e-Devlet Taraması] Sayfa: {page} | Başlık: '{title}' | URL: {curr_url} | Butonlar: {btn_texts}")

                # Hata denetimi
                if st.get("error") and page in ("mobil_form", "taahhut", "edevlet_other") and filled_at:
                    if time.time() - filled_at > 20:
                        return False, f"e-Devlet: {st['error']}"

                giris_since = (giris_since or time.time()) if page == "uyap_giris" else 0.0
                if page == "uyap_giris":
                    if filled_at:
                        if self.is_logged_in():
                            break
                        if time.time() - giris_since > 30:
                            return False, "Mobil İmza işlemi tamamlanmadan UYAP giriş sayfasına dönüldü (iptal / ret / süre aşımı)."
                    elif time.time() - last_select > 4:
                        last_select = time.time()
                        self.eval_js(self._JS_MOBIL_SELECT, timeout=8.0, retries=0, target="auto")

                elif page == "mobil_form":
                    if not filled_at:
                        log_msg("[*] e-Devlet Mobil İmza formu dolduruluyor...")
                        fr = self.eval_js(js_fill, timeout=10.0, retries=0, target="auto") or {}
                        if not fr.get("ok"):
                            return False, f"Mobil İmza formu doldurulamadı: {fr.get('error') or fr}"
                        if fr.get("filled_only"):
                            return False, "Test: form dolduruldu, gönderilmedi."
                        filled_at = time.time()
                        log_msg("[*] Mobil İmza formu gönderildi, telefon bildirimi bekleniyor...")
                    elif time.time() - filled_at > 45:
                        why = self._edevlet_page_message()
                        if why and ("zaman aşımı" in why.lower() or "hata" in why.lower()):
                            return False, f"e-Devlet: {why}"

                elif page == "taahhut":
                    if time.time() - signed_at > 4:
                        signed_at = time.time()
                        self.eval_js(js_smart_click, timeout=8.0, retries=0, target="auto")

                elif page == "waiting":
                    if st.get("fp") and not fp_shown:
                        fp_shown = True
                        waiting_shown = False
                    if not waiting_shown:
                        waiting_shown = True
                        log_msg("\n" + "=" * 70)
                        log_msg("  📲 MOBİL İMZA ONAY BİLDİRİMİ TELEFONUNUZA GÖNDERİLDİ!")
                        if st.get("fp"):
                            log_msg(f"  🔑 İşlemin Parmak İzi : {st['fp']}  (telefondakiyle aynı olmalı)")
                        log_msg("  ⏳ Telefonunuza gelen bildirimde Mobil İmza PIN'inizi girip onaylayın.")
                        log_msg(f"  (Kalan süre ~{int(deadline - time.time())} sn. İptal için Ctrl+C)")
                        log_msg("=" * 70 + "\n")
                    # DİKKAT: Telefon onayı beklenirken waiting ekranında hiçbir butona dokunulmaz!
                    # ('Devamını Oku' veya 'İptal' gibi bağlantılar tıklanmamalıdır)

                elif page in ("action_required", "oauth", "edevlet_other"):
                    # Kullanıcı telefondan PIN onaylayınca e-Devlet OAuth izin ekranına geçer
                    if time.time() - last_click > 1.5:
                        last_click = time.time()
                        click_res = self.eval_js(js_smart_click, timeout=8.0, retries=0, target="auto")
                        if click_res and isinstance(click_res, dict) and click_res.get("clicked"):
                            btxt = click_res.get("text", "")
                            bid = click_res.get("id", "")
                            key = f"{btxt}:{bid}"
                            if key not in btn_clicked_history:
                                btn_clicked_history.add(key)
                                log_msg(f"[*] 🚀 e-Devlet onay ekranı tamamlandı: '{btxt}' (ID: #{bid or 'yok'}). UYAP'a aktarılıyor...")
                                time.sleep(2.5)
                                if self.is_logged_in():
                                    break

                elif page == "uyap_app":
                    if self.is_logged_in():
                        break

            else:
                return False, "Mobil İmza onay süresi doldu (zaman aşımı). Lütfen tekrar deneyin."

            uinfo = self.check_login_and_user()
            usr = uinfo.get("user") or {}
            tckn_val = str(usr.get("tcKimlikNo") or usr.get("tckn") or "")
            if not tckn_val:
                return False, "e-Devlet onayı alındı ama UYAP oturumu doğrulanamadı. Tekrar deneyin."
            name_val = f"{usr.get('adi', '')} {usr.get('soyadi', '')}".strip() or "Avukat"
            return True, f"Mobil İmza ile giriş yapıldı: {name_val}"
        except KeyboardInterrupt:
            return False, "Mobil İmza girişi kullanıcı tarafından iptal edildi."
        except UyapBrowserError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Mobil İmza giriş hatası: {e}"

    def query_uyap_islemlerim(self, tckn: str, start_date_str: str, end_date_str: str, islem_turu=None) -> dict:
        """uyap_islem_sorgula.ajx uç noktasına tarayıcı oturumu içinden POST isteği atar."""
        payload = {
            "tcKimlikNo": tckn,
            "islemTuru": islem_turu,
            "isEmirNo": None,
            "baslangicTarihi": start_date_str,
            "bitisTarihi": end_date_str,
        }
        js = f"""
        (async () => {{
            const resp = await fetch("/uyap_islem_sorgula.ajx", {{
                method: "POST",
                headers: {{
                    "Content-Type": "application/json",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache"
                }},
                body: JSON.stringify({json.dumps(payload)})
            }});
            const errHeader = resp.headers.get("error-code");
            const ct = resp.headers.get("content-type") || "";
            let data = null;
            let text = "";
            if (ct.includes("application/json")) {{
                data = await resp.json();
            }} else {{
                text = await resp.text();
                try {{ data = JSON.parse(text); }} catch (e) {{}}
            }}
            return {{
                status: resp.status,
                ok: resp.ok,
                errorHeader: errHeader,
                data: data,
                rawText: text ? text.slice(0, 500) : ""
            }};
        }})()
        """
        try:
            return self.eval_js(js, timeout=90.0, retries=2) or {}
        except Exception as e:
            return {"status": 500, "ok": False, "error": str(e), "rawText": str(e)}

    def query_sik_kullanilan_dosyalar(self) -> list:
        """Sık kullanılan dosyaları (avukat_sik_kullanilan_dosyalar.ajx) çeker."""
        js = """
        (async () => {
            const resp = await fetch("/avukat_sik_kullanilan_dosyalar.ajx", {
                method: "POST",
                headers: {"Content-Type": "application/json", "Cache-Control": "no-cache"},
                body: JSON.stringify({})
            });
            if (!resp.ok) return [];
            const data = await resp.json();
            return Array.isArray(data) ? data : (data && Array.isArray(data.data) ? data.data : []);
        })()
        """
        return self.eval_js(js, timeout=30.0) or []

    def query_dosya_evraklar(self, dosya_id: str) -> list:
        """Bir dosyanın tüm evrak sayfalarını çeker."""
        js = f"""
        (async () => {{
            const dosyaId = {json.dumps(dosya_id)};
            const totalResp = await fetch("/listDosyaEvraklarPageTotal.ajx", {{
                method: "POST",
                headers: {{"Content-Type": "application/json", "Cache-Control": "no-cache"}},
                body: JSON.stringify({{dosyaId: dosyaId, pageNumber: 1}})
            }});
            let totalPages = 1;
            if (totalResp.ok) {{
                try {{
                    const td = await totalResp.json();
                    if (typeof td === "number") totalPages = td;
                    else if (td && td.total) totalPages = Number(td.total) || 1;
                }} catch (e) {{}}
            }}
            let allPages = [];
            for (let p = 1; p <= Math.max(totalPages, 1); p++) {{
                const r = await fetch("/list_dosya_evraklar.ajx", {{
                    method: "POST",
                    headers: {{"Content-Type": "application/json", "Cache-Control": "no-cache"}},
                    body: JSON.stringify({{dosyaId: dosyaId, pageNumber: p}})
                }});
                if (r.ok) {{
                    const d = await r.json();
                    allPages.push(d);
                }}
                if (p < totalPages) {{
                    await new Promise(res => setTimeout(res, 1200));
                }}
            }}
            return allPages;
        }})()
        """
        return self.eval_js(js, timeout=90.0) or []

    def query_dosyalar_evraklar_batch(self, dosya_ids: list, chunk_size: int = 5) -> dict:
        """
        Birden fazla dosyanın evrak sayfalarını Chromium içinde paralel olarak çeker.
        Tek tek sorgulamaya göre 5-8 kat daha hızlıdır.
        """
        if not dosya_ids:
            return {}

        clean_ids = [str(x).strip() for x in dosya_ids if str(x).strip()]
        if not clean_ids:
            return {}
        ids_json = json.dumps(clean_ids)

        js = f"""
        (async () => {{
            const ids = {ids_json};
            const results = {{}};
            const chunkSize = {chunk_size};
            for (let i = 0; i < ids.length; i += chunkSize) {{
                const chunk = ids.slice(i, i + chunkSize);
                await Promise.all(chunk.map(async (dosyaId) => {{
                    try {{
                        const totalResp = await fetch("/listDosyaEvraklarPageTotal.ajx", {{
                            method: "POST",
                            headers: {{"Content-Type": "application/json", "Cache-Control": "no-cache"}},
                            body: JSON.stringify({{dosyaId: dosyaId, pageNumber: 1}})
                        }});
                        let totalPages = 1;
                        if (totalResp.ok) {{
                            try {{
                                const td = await totalResp.json();
                                if (typeof td === "number") totalPages = td;
                                else if (td && td.total) totalPages = Number(td.total) || 1;
                            }} catch (e) {{}}
                        }}
                        let allPages = [];
                        for (let p = 1; p <= Math.min(totalPages, 5); p++) {{
                            const r = await fetch("/list_dosya_evraklar.ajx", {{
                                method: "POST",
                                headers: {{"Content-Type": "application/json", "Cache-Control": "no-cache"}},
                                body: JSON.stringify({{dosyaId: dosyaId, pageNumber: p}})
                            }});
                            if (r.ok) {{
                                const d = await r.json();
                                allPages.push(d);
                            }}
                        }}
                        results[dosyaId] = allPages;
                    }} catch(e) {{
                        results[dosyaId] = [];
                    }}
                }}));
                if (i + chunkSize < ids.length) {{
                    await new Promise(res => setTimeout(res, 200));
                }}
            }}
            return results;
        }})()
        """
        res = self.eval_js(js, timeout=120.0)
        return res if isinstance(res, dict) else {}

    def query_tum_dosyalar(self, include_closed: bool = True, use_cache: bool = True) -> list:
        """
        Tüm yargı türlerindeki AÇIK ve KAPALI (Karara Çıkmış / Arşiv) dava dosyalarını
        paralel ve optimize şekilde UYAP search_phrase_detayli servisinden çeker.
        """
        cache_file = BASE_DIR / "tum_dosyalar_cache.json"
        if use_cache and cache_file.exists():
            try:
                cdata = json.loads(cache_file.read_text(encoding="utf-8"))
                if (time.time() - cdata.get("timestamp", 0)) < 1800 and isinstance(cdata.get("cases"), list):
                    cached_cases = cdata["cases"]
                    if not include_closed:
                        cached_cases = [c for c in cached_cases if c.get("dosyaDurumGenel") == "Açık" or "açık" in str(c.get("dosyaDurum", "")).lower()]
                    return cached_cases
            except Exception:
                pass

        # Her iki durum kodu da sorgulanır; açık/kapalı ayrımı UYAP'ın döndürdüğü dosyaDurum alanından yapılır
        # (kod anlamı yargı türüne göre değişebiliyor, eskiden yalnız açıklar istendiğinde kapalılar gelebiliyordu).
        durum_vals = [0, 1]
        js = f"""
        (async () => {{
            const birimler = [
                ["0", "0901"], ["0", "0921"], ["0", "7702"], ["0", "0929"], ["0", "0911"],
                ["0", "0914"], ["0", "0924"], ["0", "0915"], ["0", "0931"],
                ["1", "0926"], ["1", "0920"], ["1", "0902"], ["1", "7710"], ["1", "7703"],
                ["1", "0913"], ["1", "0925"], ["1", "0908"], ["1", "0907"], ["1", "0906"],
                ["1", "0904"], ["1", "0912"],
                ["2", "1101"],
                ["6", "0917"], ["6", "0918"], ["6", "0919"],
                ["11", "9791"],
                ["25", "6701"]
            ];
            const durumlar = {json.dumps(durum_vals)};
            // Avukatın yetkili olduğu TÜM birim türleri UYAP'tan dinamik alınır (icra daireleri dahil); sabit listede
            // olmayan birimlerin dosyaları eskiden hiç gelmiyordu (icra dosyaları "Dosya Hesapları"nda görünmüyordu).
            for (const yt of ["0", "1", "2", "6", "11", "25"]) {{
                try {{
                    const r = await fetch("/yargiBirimleriSorgula_brd.ajx", {{method: "POST",
                        headers: {{"Content-Type": "application/json"}}, body: JSON.stringify({{yargiTuru: yt}})}});
                    const d = r.ok ? await r.json() : null;
                    if (Array.isArray(d)) for (const b of d) {{
                        const kod = String((b && b.tablo) || "");
                        if (kod && !birimler.some(x => x[0] === yt && x[1] === kod)) birimler.push([yt, kod]);
                    }}
                }} catch (e) {{}}
            }}

            // UYAP aynı anda çok sayıda isteği zaman zaman reddeder: her istek 3 kez denenir,
            // aynı anda en fazla 6 istek çalışır (önceden reddedilen kategoriler sessizce boş dönüyordu).
            let active = 0;
            const waiting = [];
            const acquire = () => new Promise(res => {{ if (active < 6) {{ active++; res(); }} else waiting.push(res); }});
            const release = () => {{ const n = waiting.shift(); if (n) n(); else active--; }};
            const postJson = async (url, body) => {{
                await acquire();
                try {{ return await postJsonRaw(url, body); }} finally {{ release(); }}
            }};
            const postJsonRaw = async (url, body) => {{
                for (let t = 0; t < 3; t++) {{
                    try {{
                        const r = await fetch(url, {{method: "POST", headers: {{"Content-Type": "application/json"}},
                                                    body: JSON.stringify(body)}});
                        if (r.ok) {{
                            const d = await r.json();
                            if (Array.isArray(d)) return d;
                        }}
                    }} catch (e) {{}}
                    await new Promise(res => setTimeout(res, 600 * (t + 1)));
                }}
                return null;
            }};
            let failed = 0;
            let tasks = [];
            for (let [y_tur, b_tur] of birimler) {{
                for (let durum of durumlar) {{
                    tasks.push((async () => {{
                        // UYAP sayfa başına en fazla 200 dosya döner: TÜM sayfalar çekilmeli
                        const out = [];
                        for (let page = 1; page <= 50; page++) {{
                            try {{
                                const d = await postJson("/search_phrase_detayli.ajx", {{
                                    dosyaDurumKod: durum, birimTuru3: y_tur, birimTuru2: b_tur,
                                    pageSize: 200, pageNumber: page
                                }});
                                if (d === null) {{ failed++; break; }}
                                const list = Array.isArray(d[0]) ? d[0] : [];
                                for (const x of list) {{
                                    const dd = String(x.dosyaDurum || "").toLocaleLowerCase("tr");
                                    const genel = dd ? (dd.startsWith("açık") || dd.startsWith("acik") ? "Açık" : "Kapalı") : (durum === 0 ? "Açık" : "Kapalı");
                                    out.push({{...x, dosyaDurumGenel: genel}});
                                }}
                                if (list.length < 200) break;
                            }} catch (e) {{
                                break;
                            }}
                        }}
                        return out;
                    }})());
                }}
            }}

            tasks.push((async () => {{
                const out = [];
                for (let page = 1; page <= 50; page++) {{
                    try {{
                        const d = await postJson("/avukat_dosya_sorgula_cbs_brd.ajx", {{dosyaDurumKod: 1, pageSize: 200, pageNumber: page}});
                        if (d === null) {{ failed++; break; }}
                        const list = Array.isArray(d[0]) ? d[0] : [];
                        out.push(...list);
                        if (list.length < 200) break;
                    }} catch (e) {{ break; }}
                }}
                return out;
            }})());

            let results = await Promise.all(tasks);
            let allCases = [];
            let seen = new Set();
            for (let list of results) {{
                for (let c of list) {{
                    let id = c.dosyaId || c.dosyaID;
                    if (id && !seen.has(id)) {{
                        seen.add(id);
                        allCases.push(c);
                    }}
                }}
            }}
            return allCases;
        }})()
        """
        cases = self.eval_js(js, timeout=240.0) or []
        if not include_closed:
            cases = [c for c in cases if c.get("dosyaDurumGenel") == "Açık"]
        if cases and include_closed:
            try:
                cache_file.write_text(
                    json.dumps({"timestamp": time.time(), "cases": cases}, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
            except Exception:
                pass
        return cases

    def query_durusmalar(self, start_date_str: str, end_date_str: str) -> list:
        """avukat_durusma_sorgula_brd.ajx ile belirli tarih aralığındaki duruşmaları çeker."""
        start_date_str = start_date_str.replace("/", ".")
        end_date_str = end_date_str.replace("/", ".")
        js = f"""
        (async () => {{
            const resp = await fetch("/avukat_durusma_sorgula_brd.ajx", {{
                method: "POST",
                headers: {{"Content-Type": "application/json", "Cache-Control": "no-cache"}},
                body: JSON.stringify({{
                    baslangicTarihi: {json.dumps(start_date_str)},
                    bitisTarihi: {json.dumps(end_date_str)}
                }})
            }});
            if (!resp.ok) return [];
            const d = await resp.json();
            return Array.isArray(d) ? d : (d && Array.isArray(d.data) ? d.data : []);
        }})()
        """
        return self.eval_js(js, timeout=30.0) or []

    def download_document(self, params: dict, timeout_s: float = 40.0) -> dict:
        """download_document_brd.uyap üzerinden tek bir evrakı indirir ve base64 olarak döndürür.
        İstek timeout_s saniyede yanıt vermezse tarayıcı içinde iptal edilir ({"ok": False, "timeout": True});
        böylece takılan bir indirme programı dakikalarca bekletmez, üst katman yeniden dener."""
        qs = urlencode({k: v for k, v in params.items() if v is not None and v != ""})
        url = f"/download_document_brd.uyap?{qs}"
        js = f"""
        (async () => {{
            const ctl = new AbortController();
            const timer = setTimeout(() => ctl.abort(), {int(timeout_s * 1000)});
            let resp;
            try {{
                resp = await fetch({json.dumps(url)}, {{
                    method: "GET", signal: ctl.signal,
                    headers: {{"Cache-Control": "no-cache", "Pragma": "no-cache"}}
                }});
            }} catch (e) {{
                clearTimeout(timer);
                return {{status: 0, ok: false, timeout: e && e.name === "AbortError", error: String(e)}};
            }}
            const errHeader = resp.headers.get("error-code");
            const ct = resp.headers.get("content-type") || "";
            const cd = resp.headers.get("content-disposition") || "";
            let buf;
            try {{ buf = await resp.arrayBuffer(); }}
            catch (e) {{ clearTimeout(timer); return {{status: resp.status, ok: false, timeout: e && e.name === "AbortError", error: String(e)}}; }}
            clearTimeout(timer);
            const bytes = new Uint8Array(buf);
            let binary = "";
            const chunkSize = 0x8000;
            for (let i = 0; i < bytes.length; i += chunkSize) {{
                binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
            }}
            const b64 = btoa(binary);
            return {{
                status: resp.status,
                ok: resp.ok,
                errorHeader: errHeader,
                contentType: ct,
                contentDisposition: cd,
                size: bytes.length,
                base64: b64
            }};
        }})()
        """
        try:
            return self.eval_js(js, timeout=timeout_s + 20, retries=0) or {}
        except Exception as e:  # CDP / tarayıcı sorunu: üst katman yeniden dener
            file_logger.warning("download_document CDP hatası: %s", e)
            return {"status": 0, "ok": False, "error": f"CDP: {e}"}


# ---------------------------------------------------------------------------
# Masaüstü Arayüzü (Tkinter GUI)
# ---------------------------------------------------------------------------

FOLDER_PRESETS = [
    (
        "İşlemlerim / Dosya Türü / Evrak Türü / İşlem Türü / Yıl-Ay (Önerilen)",
        "ISLEMLERIM/{dosya_turu}/{evrak_turu}/{islem_turu}/{yil_ay}/{tarih}_{birim_adi}_{dosya_no}_{evrak_adi}",
    ),
    (
        "İşlemlerim / Yıl-Ay / Dosya Türü / Birim & Dosya No / Evrak Türü",
        "ISLEMLERIM/{yil_ay}/{dosya_turu}/{birim_adi}_{dosya_no}/{evrak_turu}/{tarih}_{evrak_adi}",
    ),
    (
        "İşlemlerim / Dosya Türü / Birim & Dosya No / İşlem Türü / Evrak Türü",
        "ISLEMLERIM/{dosya_turu}/{birim_adi}_{dosya_no}/{islem_turu}/{evrak_turu}/{tarih}_{evrak_adi}",
    ),
    (
        "İşlemlerim / İşlem Türü / Dosya Türü / Evrak Türü / Tarih",
        "ISLEMLERIM/{islem_turu}/{dosya_turu}/{evrak_turu}/{yil_ay}/{tarih}_{birim_adi}_{dosya_no}_{evrak_adi}",
    ),
]


class UyapDownloaderApp:
    def __init__(self, root: "tk.Tk"):
        self.root = root
        self.root.title("UYAP Avukat Portal - Güvenli Evrak İndirici (e-İmza Otomatik Yenilemeli)")
        self.root.geometry("1280x880")
        self.root.minsize(1050, 720)

        self.bridge = UyapBrowserBridge(port=CDP_PORT)
        self.all_items: list[dict] = []
        self.filtered_items: list[dict] = []
        self.tckn: str = ""

        self.is_busy = False
        self.stop_requested = False
        self.pause_requested = False

        # İndirme geçmişini diskteki fiziksel dosyalarla eşleştirip temizleyerek yükle
        self.history: dict = self._verify_and_clean_history()

        self._build_ui()
        self.log(f"Uygulama hazır. Kayıtlı ve doğrulanmış evrak sayısı: {len(self.history)}")

    # -----------------------------------------------------------------------
    # Geçmiş Yönetimi ve Tam Doğruluk (Idempotency)
    # -----------------------------------------------------------------------
    def _verify_and_clean_history(self) -> dict:
        """
        Geçmişteki kayıtları diskteki fiziksel dosyalarla karşılaştırır:
        - Eski dinamik anahtarları kalıcı islem_{is_emir_no} formatına standardize eder.
        - Dosya diskte yoksa veya boyutu < 128 / HTML ise geçmişten siler (tekrar indirilebilsin diye).
        - Böylece eksik evrak kalmaz ve mükerrerlik %100 önlenir.
        """
        raw = {}
        if HISTORY_FILE.exists():
            try:
                raw = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            except Exception:
                raw = {}

        cleaned = {}
        for k, v in raw.items():
            path_str = v.get("path")
            if not path_str:
                continue
            fp = Path(path_str)
            if not fp.exists():
                if "/ISLEMLERIM/" not in path_str and "/UYAP_Indirilenler/" in path_str:
                    alt_fp = Path(path_str.replace("/UYAP_Indirilenler/", "/UYAP_Indirilenler/ISLEMLERIM/"))
                    if alt_fp.exists():
                        fp = alt_fp
                        v["path"] = str(alt_fp)
            if not fp.exists():
                # Dosya taşınmış / yeniden adlandırılmış olabilir: kalıcı numarayla diskte ara
                ident = str(v.get("is_emir_no") or "").strip() or (k.split("_")[-1] if "_" in k else "")
                moved = self._find_on_disk(ident)
                if moved:
                    fp = moved
                    v["path"] = str(moved)
            if not fp.exists():
                continue
            try:
                sz = fp.stat().st_size
                if sz < 128:
                    fp.unlink(missing_ok=True)
                    continue
                head = fp.read_bytes()[:512].lower()
                if b"<html" in head or b"<!doctype html" in head:
                    fp.unlink(missing_ok=True)
                    continue

                # Anahtarı kalıcı işlem numarasıyla (is_emir_no) standardize et
                emir = str(v.get("is_emir_no") or "").strip()
                if not emir and "_" in k:
                    parts = k.split("_")
                    if len(parts) >= 2 and parts[-1].isdigit():
                        emir = parts[-1]
                v["is_emir_no"] = emir
                stable_k = f"islem_{emir}" if emir else k
                cleaned[stable_k] = v
            except Exception:
                continue

        try:
            HISTORY_FILE.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return cleaned

    def is_item_already_downloaded(self, item_or_key) -> bool:
        """
        Bir evrakın hem geçmişte hem de diskte sağlam bir şekilde bulunup bulunmadığını denetler.
        UYAP evrakId'yi dinamik şifrelese bile:
        1. is_emir_no eşleşmesi (kalıcı işlem no)
        2. unique_key eşleşmesi
        3. (birim_adi, dosya_no, tarih, evrak_adi) içerik eşleşmesi
        4. Diskteki fiziksel dosya varlığı ve boyutu (> 128 bayt)
        ile tam mükerrerlik denetimi yapar.
        """
        if isinstance(item_or_key, dict):
            item = item_or_key
            ukey = item.get("unique_key", "")
            is_emir = str(item.get("is_emir_no") or "").strip()
        else:
            ukey = str(item_or_key)
            is_emir = ukey.split("_")[-1] if ukey.startswith("islem_") else ""
            item = {}

        entry = None
        # 1. Doğrudan ukey eşleşmesi
        if ukey and ukey in self.history:
            entry = self.history[ukey]
        # 2. is_emir_no eşleşmesi (örn: islem_18313320805)
        elif is_emir and f"islem_{is_emir}" in self.history:
            entry = self.history[f"islem_{is_emir}"]
        # 3. Geçmişteki is_emir_no alanları arasında ara (kısa birim evrak no'ları mahkemeler
        #    arasında çakışabilir; yalnızca uzun, global işlem numaralarında güvenli).
        #    Eskiden her evrak için tüm geçmiş baştan sona taranıyordu (binlerce evrakta dakikalar);
        #    artık bir kez kurulan dizinle O(1).
        elif is_emir and len(is_emir) >= 8:
            entry = self._gecmis_dizini()[0].get(is_emir)

        # 4. Alternatif eşleşme: Birim adı, dosya no, tarih ve evrak adı birebir aynı mı?
        b_adi = item.get("birim_adi") if item else None
        d_no = item.get("dosya_no") if item else None
        e_adi = item.get("evrak_adi") if item else None
        tarih = item.get("tarih") if item else None
        # Boş alanlar (None == None) yanlış eşleşme üretmesin
        if not entry and item and b_adi and e_adi and tarih:
            entry = self._gecmis_dizini()[1].get((b_adi, d_no, e_adi, tarih))

        if entry:
            path_str = entry.get("path")
            fp = Path(path_str) if path_str else None
            if fp and not fp.exists():
                if "/ISLEMLERIM/" not in path_str and "/UYAP_Indirilenler/" in path_str:
                    alt_p = Path(path_str.replace("/UYAP_Indirilenler/", "/UYAP_Indirilenler/ISLEMLERIM/"))
                    if alt_p.exists():
                        entry["path"] = str(alt_p)
                        fp = alt_p
            if fp and fp.exists() and fp.stat().st_size >= 128:
                return True

        # 5. Geçmişte yok / yolu değişmiş: diskte dosya adındaki kalıcı numarayla ara
        #    (taşınan, yeniden adlandırılan, başka cihazda indirilen dosyalar mükerrer inmesin)
        ident = str(item.get("is_emir_no") or item.get("evrak_id") or is_emir or "").strip()
        disk_path = self._find_on_disk(ident)
        if disk_path:
            hk = f"islem_{ident}" if (item.get("is_emir_no") or is_emir) else (ukey or f"disk_{ident}")
            self.history[hk] = {
                "path": str(disk_path),
                "is_emir_no": str(item.get("is_emir_no") or is_emir or ""),
                "birim_adi": item.get("birim_adi"),
                "dosya_no": item.get("dosya_no"),
                "evrak_turu": item.get("evrak_adi"),
                "tarih": item.get("tarih"),
                "kaynak": "disk_eslesme",
            }
            self._history_dirty = True
            return True
        return False

    def _gecmis_dizini(self):
        """Geçmiş (indirme_gecmisi.json) için arama dizinleri: (is_emir_no → kayıt, (birim, dosya, evrak, tarih) → kayıt,
        sha256 → kayıt). Geçmiş büyüdükçe kendiliğinden yenilenir."""
        anahtar = (id(self.history), len(self.history))
        if getattr(self, "_gd_anahtar", None) != anahtar:
            emir, icerik, sha = {}, {}, {}
            for h in self.history.values():
                if not isinstance(h, dict):
                    continue
                e = str(h.get("is_emir_no") or "").strip()
                if e and e not in emir:
                    emir[e] = h
                k = (h.get("birim_adi"), h.get("dosya_no"), h.get("evrak_turu"), h.get("tarih"))
                if k[0] and k[2] and k[3] and k not in icerik:
                    icerik[k] = h
                if h.get("sha256") and h.get("path") and h["sha256"] not in sha:
                    sha[h["sha256"]] = h
            self._gd = (emir, icerik, sha)
            self._gd_anahtar = anahtar
        return self._gd

    def ayni_icerik_var(self, raw_bytes: bytes):
        """İndirilen içerik (SHA-256) diskte zaten varsa o dosyanın yolunu döner: ikinci kopya yazılmaz."""
        h = self._gecmis_dizini()[2].get(hashlib.sha256(raw_bytes).hexdigest())
        if h and h.get("path") and Path(h["path"]).exists():
            return Path(h["path"])
        return None

    _DISK_ID_RX = re.compile(
        r"_(\d{6,})(?:_\d{1,3})?\.(?:udf|pdf|tif|tiff|jpe?g|png|gif|docx?|xlsx?|zip|rar|xml|html?|txt|eyp|p7s)$",
        re.IGNORECASE,
    )

    def _disk_roots(self) -> list:
        roots = list(getattr(self, "disk_roots", None) or [])
        if hasattr(self, "var_download_dir"):
            try:
                roots.append(Path(self.var_download_dir.get().strip() or str(DEFAULT_DOWNLOAD_DIR)))
            except Exception:
                pass
        roots.append(DEFAULT_DOWNLOAD_DIR)
        seen, out = set(), []
        for r in roots:
            try:
                rp = Path(r).resolve()
            except Exception:
                continue
            if rp not in seen and rp.exists():
                seen.add(rp)
                out.append(rp)
        return out

    def _disk_index(self) -> dict:
        """İndirme klasör(ler)indeki dosyaları adlarının sonundaki numaraya göre indeksler
        (örn. ..._evrak_10119302152.udf -> '10119302152'). Bir kez taranır, önbelleğe alınır."""
        idx = getattr(self, "_disk_idx", None)
        if idx is not None:
            return idx
        idx = {}
        for root in self._disk_roots():
            for dirpath, _dirs, files in os.walk(root):
                for fn in files:
                    m = self._DISK_ID_RX.search(fn)
                    if not m:
                        continue
                    p = Path(dirpath) / fn
                    try:
                        if p.stat().st_size < 128:
                            continue
                    except OSError:
                        continue
                    # .udf asıl evrak; varsa onu tercih et
                    if m.group(1) not in idx or fn.lower().endswith(".udf"):
                        idx[m.group(1)] = p
        self._disk_idx = idx
        return idx

    def _find_on_disk(self, ident: str):
        ident = str(ident or "").strip()
        if len(ident) < 6 or not ident.isdigit():
            return None
        p = self._disk_index().get(ident)
        if p is not None and p.exists():
            return p
        return None

    def flush_history_if_dirty(self):
        if getattr(self, "_history_dirty", False):
            try:
                HISTORY_FILE.write_text(json.dumps(self.history, ensure_ascii=False, indent=2), encoding="utf-8")
                self._history_dirty = False
            except Exception:
                pass

    def _save_history(self):
        try:
            HISTORY_FILE.write_text(json.dumps(self.history, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            self.log(f"UYARI: İndirme geçmişi kaydedilemedi: {e}", level="WARNING")

    # -----------------------------------------------------------------------
    # Arayüz Kurulumu
    # -----------------------------------------------------------------------
    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # 1. Üst Panel: Tarayıcı Bağlantısı, e-İmza Ayarları ve Tarih Seçimi
        top_frame = ttk.LabelFrame(self.root, text=" 1. UYAP Tarayıcı & e-İmza Oturum Yönetimi ", padding=8)
        top_frame.pack(fill=tk.X, padx=10, pady=4)

        row1 = ttk.Frame(top_frame)
        row1.pack(fill=tk.X, pady=2)

        self.btn_launch = ttk.Button(
            row1,
            text="1. Chromium ile UYAP'ı Aç",
            command=self.on_launch_browser,
        )
        self.btn_launch.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_check_login = ttk.Button(
            row1,
            text="2. Giriş Durumunu Kontrol Et",
            command=self.on_check_login,
        )
        self.btn_check_login.pack(side=tk.LEFT, padx=(0, 10))

        # e-İmza Otomatik Giriş Bölümü
        ttk.Label(row1, text="e-İmza PIN:", font=("Sans", 9, "bold")).pack(side=tk.LEFT, padx=(4, 2))
        self.var_pin = tk.StringVar(value=DEFAULT_E_IMZA_PIN)
        self.ent_pin = ttk.Entry(row1, textvariable=self.var_pin, width=8, show="*")
        self.ent_pin.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_toggle_pin = ttk.Button(row1, text="Göster", width=6, command=self.on_toggle_pin_visibility)
        self.btn_toggle_pin.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_manual_relogin = ttk.Button(
            row1,
            text="e-İmza ile Giriş Yap / Yenile",
            command=self.on_manual_relogin,
        )
        self.btn_manual_relogin.pack(side=tk.LEFT, padx=(0, 10))

        self.var_auto_relogin = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            row1,
            text="Oturum koparsa e-İmza ile otomatik tekrar bağlan",
            variable=self.var_auto_relogin,
        ).pack(side=tk.LEFT, padx=4)

        row1_sub = ttk.Frame(top_frame)
        row1_sub.pack(fill=tk.X, pady=(4, 2))

        self.lbl_status = ttk.Label(
            row1_sub,
            text="Durum: Chromium ve ArkSigner bağlantısı bekleniyor...",
            foreground="#b45309",
            font=("Sans", 9, "bold"),
        )
        self.lbl_status.pack(side=tk.LEFT, padx=4)

        row2 = ttk.Frame(top_frame)
        row2.pack(fill=tk.X, pady=4)

        ttk.Label(row2, text="Başlangıç:").pack(side=tk.LEFT)
        one_year_ago = dt.date.today() - dt.timedelta(days=365)
        self.var_start_date = tk.StringVar(value=one_year_ago.strftime("%d.%m.%Y"))
        ttk.Entry(row2, textvariable=self.var_start_date, width=12).pack(side=tk.LEFT, padx=(4, 10))

        ttk.Label(row2, text="Bitiş:").pack(side=tk.LEFT)
        self.var_end_date = tk.StringVar(value=dt.date.today().strftime("%d.%m.%Y"))
        ttk.Entry(row2, textvariable=self.var_end_date, width=12).pack(side=tk.LEFT, padx=(4, 10))

        ttk.Label(row2, text="Dilim (Gün):").pack(side=tk.LEFT)
        self.var_chunk_days = tk.IntVar(value=30)
        ttk.Spinbox(row2, from_=7, to=90, textvariable=self.var_chunk_days, width=5).pack(side=tk.LEFT, padx=(4, 12))

        self.btn_scan_islemlerim = ttk.Button(
            row2,
            text="3. İşlemlerim'i Tara (Son 1 Yıl / Seçili Aralık)",
            command=self.on_scan_islemlerim,
        )
        self.btn_scan_islemlerim.pack(side=tk.LEFT, padx=4)

        self.btn_scan_fav_cases = ttk.Button(
            row2,
            text="Sık Kullanılan Dosyalarımın Evraklarını Tara",
            command=self.on_scan_fav_cases,
        )
        self.btn_scan_fav_cases.pack(side=tk.LEFT, padx=4)

        # 2. Orta Panel: Filtreleme ve Kategorileme Ayarları
        filter_frame = ttk.LabelFrame(
            self.root,
            text=" 2. Dosya Türü / Evrak Türü / İşlem Türü / Tarih Filtreleri ve Klasör Şablonu ",
            padding=8,
        )
        filter_frame.pack(fill=tk.X, padx=10, pady=3)

        frow1 = ttk.Frame(filter_frame)
        frow1.pack(fill=tk.X, pady=2)

        ttk.Label(frow1, text="Dosya/Birim Türü:").pack(side=tk.LEFT)
        self.var_filter_dosya_turu = tk.StringVar(value="TÜMÜ")
        self.cb_dosya_turu = ttk.Combobox(
            frow1, textvariable=self.var_filter_dosya_turu, state="readonly", width=22, values=["TÜMÜ"]
        )
        self.cb_dosya_turu.pack(side=tk.LEFT, padx=(4, 10))
        self.cb_dosya_turu.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        ttk.Label(frow1, text="Evrak Türü:").pack(side=tk.LEFT)
        self.var_filter_evrak_turu = tk.StringVar(value="TÜMÜ")
        self.cb_evrak_turu = ttk.Combobox(
            frow1, textvariable=self.var_filter_evrak_turu, state="readonly", width=26, values=["TÜMÜ"]
        )
        self.cb_evrak_turu.pack(side=tk.LEFT, padx=(4, 10))
        self.cb_evrak_turu.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        ttk.Label(frow1, text="İşlem Türü / Durum:").pack(side=tk.LEFT)
        self.var_filter_islem_turu = tk.StringVar(value="TÜMÜ")
        self.cb_islem_turu = ttk.Combobox(
            frow1, textvariable=self.var_filter_islem_turu, state="readonly", width=18, values=["TÜMÜ"]
        )
        self.cb_islem_turu.pack(side=tk.LEFT, padx=(4, 10))
        self.cb_islem_turu.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        ttk.Label(frow1, text="Arama:").pack(side=tk.LEFT)
        self.var_filter_search = tk.StringVar(value="")
        ent_search = ttk.Entry(frow1, textvariable=self.var_filter_search, width=16)
        ent_search.pack(side=tk.LEFT, padx=(4, 6))
        ent_search.bind("<KeyRelease>", lambda e: self.apply_filters())

        ttk.Button(frow1, text="Filtreyi Sıfırla", command=self.reset_filters).pack(side=tk.LEFT, padx=2)

        frow2 = ttk.Frame(filter_frame)
        frow2.pack(fill=tk.X, pady=4)

        ttk.Label(frow2, text="Klasör Şablonu:").pack(side=tk.LEFT)
        self.var_preset = tk.StringVar(value=FOLDER_PRESETS[0][0])
        cb_preset = ttk.Combobox(
            frow2,
            textvariable=self.var_preset,
            state="readonly",
            width=40,
            values=[p[0] for p in FOLDER_PRESETS],
        )
        cb_preset.pack(side=tk.LEFT, padx=(4, 8))

        self.var_template = tk.StringVar(value=FOLDER_PRESETS[0][1])
        ttk.Entry(frow2, textvariable=self.var_template, width=64).pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)

        def on_preset_change(event):
            sel = self.var_preset.get()
            for title, tpl in FOLDER_PRESETS:
                if title == sel:
                    self.var_template.set(tpl)
                    break

        cb_preset.bind("<<ComboboxSelected>>", on_preset_change)

        frow3 = ttk.Frame(filter_frame)
        frow3.pack(fill=tk.X, pady=2)

        ttk.Label(frow3, text="İndirme Klasörü:").pack(side=tk.LEFT)
        self.var_download_dir = tk.StringVar(value=str(DEFAULT_DOWNLOAD_DIR))
        ttk.Entry(frow3, textvariable=self.var_download_dir, width=42).pack(side=tk.LEFT, padx=(4, 6))
        ttk.Button(frow3, text="Klasör Seç...", command=self.on_choose_dir).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(frow3, text="Bekleme (sn):").pack(side=tk.LEFT)
        self.var_min_delay = tk.DoubleVar(value=1.0)
        self.var_max_delay = tk.DoubleVar(value=2.0)
        ttk.Spinbox(frow3, from_=1.0, to=30.0, increment=0.5, textvariable=self.var_min_delay, width=4).pack(side=tk.LEFT, padx=1)
        ttk.Label(frow3, text="-").pack(side=tk.LEFT)
        ttk.Spinbox(frow3, from_=1.5, to=60.0, increment=0.5, textvariable=self.var_max_delay, width=4).pack(side=tk.LEFT, padx=(1, 8))

        ttk.Label(frow3, text="Her").pack(side=tk.LEFT)
        self.var_batch_size = tk.IntVar(value=20)
        ttk.Spinbox(frow3, from_=5, to=100, textvariable=self.var_batch_size, width=3).pack(side=tk.LEFT, padx=1)
        ttk.Label(frow3, text="dosyada").pack(side=tk.LEFT)
        self.var_batch_pause = tk.DoubleVar(value=10.0)
        ttk.Spinbox(frow3, from_=5.0, to=120.0, increment=5.0, textvariable=self.var_batch_pause, width=4).pack(side=tk.LEFT, padx=1)
        ttk.Label(frow3, text="sn dinlen").pack(side=tk.LEFT, padx=(0, 8))

        self.var_skip_downloaded = tk.BooleanVar(value=True)
        ttk.Checkbutton(frow3, text="İndirilenleri Atla (Mükerrer Önle)", variable=self.var_skip_downloaded).pack(side=tk.LEFT, padx=4)

        # 3. Tablo (Treeview): Evrak Listesi
        table_frame = ttk.LabelFrame(self.root, text=" 3. Bulunan Evraklar / İşlemler Listesi ", padding=6)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=3)

        cols = ("durum", "tarih", "dosya_turu", "birim_adi", "dosya_no", "islem_turu", "evrak_turu", "evrak_id")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="extended")
        headers = {
            "durum": ("İndirme Durumu", 120),
            "tarih": ("Tarih", 95),
            "dosya_turu": ("Dosya / Yargı Türü", 170),
            "birim_adi": ("Birim / Mahkeme Adı", 230),
            "dosya_no": ("Dosya No", 100),
            "islem_turu": ("İşlem Türü / Kaynak", 140),
            "evrak_turu": ("Evrak / İşin Adı", 260),
            "evrak_id": ("Evrak ID", 100),
        }
        for c, (text, w) in headers.items():
            self.tree.heading(c, text=text)
            self.tree.column(c, width=w, anchor=tk.W)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # 4. Alt Panel: İndirme Butonları, İlerleme Çubuğu ve Rotasyonlu Log Konsolu
        bottom_frame = ttk.Frame(self.root, padding=6)
        bottom_frame.pack(fill=tk.X, padx=10, pady=2)

        btn_row = ttk.Frame(bottom_frame)
        btn_row.pack(fill=tk.X, pady=3)

        self.btn_download_filtered = ttk.Button(
            btn_row,
            text="Filtrelenen Tüm Evrakları Güvenli İndir",
            command=lambda: self.on_start_download(selected_only=False),
        )
        self.btn_download_filtered.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_download_selected = ttk.Button(
            btn_row,
            text="Sadece Tabloda Seçili Olanları İndir",
            command=lambda: self.on_start_download(selected_only=True),
        )
        self.btn_download_selected.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_pause = ttk.Button(
            btn_row,
            text="Duraklat / Devam Et",
            command=self.on_toggle_pause,
            state=tk.DISABLED,
        )
        self.btn_pause.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_stop = ttk.Button(
            btn_row,
            text="İndirmeyi Durdur",
            command=self.on_stop,
            state=tk.DISABLED,
        )
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_export_csv = ttk.Button(
            btn_row,
            text="Listeyi CSV Olarak Dışa Aktar",
            command=self.on_export_csv,
        )
        self.btn_export_csv.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_open_log = ttk.Button(
            btn_row,
            text="📄 Log Dosyasını Aç",
            command=self.on_open_log_file,
        )
        self.btn_open_log.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_open_dir = ttk.Button(
            btn_row,
            text="📁 İndirilenler Klasörünü Aç",
            command=self.on_open_download_dir,
        )
        self.btn_open_dir.pack(side=tk.LEFT, padx=(0, 8))

        self.lbl_count = ttk.Label(btn_row, text="Toplam: 0 | Filtrelenen: 0", font=("Sans", 9, "bold"))
        self.lbl_count.pack(side=tk.RIGHT, padx=4)

        self.progress = ttk.Progressbar(bottom_frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill=tk.X, pady=3)

        self.txt_log = tk.Text(bottom_frame, height=5, wrap=tk.WORD, font=("Monospace", 9))
        self.txt_log.pack(fill=tk.X, pady=2)

    # -----------------------------------------------------------------------
    # Loglama Metotları
    # -----------------------------------------------------------------------
    def log(self, msg: str, level: str = "INFO"):
        """Mesajı hem UI konsoluna hem de rotasyonlu 8 MB uyap_indirici_log.txt dosyasına anlık yazar."""
        lvl = getattr(logging, level.upper(), logging.INFO)
        file_logger.log(lvl, msg)
        try:
            rf_handler.flush()
        except Exception:
            pass

        ts = dt.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self.root.after(0, self._append_log, line)

    def _append_log(self, line: str):
        self.txt_log.insert(tk.END, line)
        self.txt_log.see(tk.END)

    def on_open_log_file(self):
        """Kullanıcının sistemindeki varsayılan metin editörüyle log dosyasını açar."""
        if not LOG_FILE.exists():
            LOG_FILE.touch()
        try:
            subprocess.Popen(["xdg-open", str(LOG_FILE)])
        except Exception as e:
            messagebox.showinfo("Log Dosyası", f"Log dosya konumu:\n{LOG_FILE}\n\nDoğrudan açma hatası: {e}")

    def on_open_download_dir(self):
        """İndirilenler klasörünü dosya yöneticisinde açar."""
        d = Path(self.var_download_dir.get().strip() or str(DEFAULT_DOWNLOAD_DIR))
        d.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.Popen(["xdg-open", str(d)])
        except Exception as e:
            messagebox.showinfo("İndirme Klasörü", f"Klasör konumu:\n{d}\n\nDoğrudan açma hatası: {e}")

    def on_toggle_pin_visibility(self):
        if self.ent_pin.cget("show") == "*":
            self.ent_pin.config(show="")
            self.btn_toggle_pin.config(text="Gizle")
        else:
            self.ent_pin.config(show="*")
            self.btn_toggle_pin.config(text="Göster")

    # -----------------------------------------------------------------------
    # Bağlantı ve e-İmza İşlemleri
    # -----------------------------------------------------------------------
    def on_launch_browser(self):
        def task():
            self.log("Chromium başlatılıyor veya mevcut oturuma bağlanılıyor...")
            ok, msg = self.bridge.launch_or_connect()
            self.log(msg)
            if ok:
                time.sleep(1.2)
                self.on_check_login()

        threading.Thread(target=task, daemon=True).start()

    def on_manual_relogin(self):
        """Kullanıcı butona bastığında veya oturum koptuğunda e-İmza ile giriş yapar."""
        pin = self.var_pin.get().strip()
        if not pin:
            messagebox.showwarning("PIN Gerekli", "Lütfen e-İmza PIN kodunuzu girin.")
            return

        def task():
            self.log("ArkSigner üzerinden e-İmza doğrulaması başlatılıyor...")
            ok, msg = self.bridge.auto_relogin(pin=pin)
            if ok:
                self.log(f"Başarılı: {msg}")
                self.root.after(0, lambda: self.lbl_status.config(text=f"Durum: {msg}", foreground="#15803d"))
                self.on_check_login()
            else:
                self.log(f"HATA: {msg}", level="ERROR")
                self.root.after(0, lambda: self.lbl_status.config(text=f"Durum: {msg}", foreground="#b91c1c"))

        threading.Thread(target=task, daemon=True).start()

    def on_check_login(self):
        def task():
            try:
                info = self.bridge.check_login_and_user()
                user = info.get("user")
                if user and (user.get("tcKimlikNo") or user.get("tckn")):
                    self.tckn = str(user.get("tcKimlikNo") or user.get("tckn"))
                    ad = user.get("adi") or user.get("ad") or ""
                    soyad = user.get("soyadi") or user.get("soyad") or ""
                    baro = user.get("baroAdi") or ""
                    status_text = f"Bağlı: {ad} {soyad} (TCKN: {self.tckn} - {baro})"
                    self.log(f"Giriş Başarılı: {status_text}")
                    self.root.after(0, lambda: self.lbl_status.config(text=status_text, foreground="#15803d"))
                else:
                    msg = "UYAP oturumu açık görünmüyor. 'e-İmza ile Giriş Yap' butonuna basabilir veya tarayıcıdan girebilirsiniz."
                    self.log(msg, level="WARNING")
                    self.root.after(0, lambda: self.lbl_status.config(text=msg, foreground="#b45309"))
            except Exception as e:
                self.log(f"Giriş kontrol hatası: {e}", level="ERROR")

        threading.Thread(target=task, daemon=True).start()

    # -----------------------------------------------------------------------
    # Tarama İşlemleri (İşlemlerim ve Sık Kullanılan Dosyalar)
    # -----------------------------------------------------------------------
    def on_scan_islemlerim(self):
        if self.is_busy:
            messagebox.showwarning("Meşgul", "Şu anda devam eden bir işlem var.")
            return
        try:
            start_d = dt.datetime.strptime(self.var_start_date.get().strip(), "%d.%m.%Y").date()
            end_d = dt.datetime.strptime(self.var_end_date.get().strip(), "%d.%m.%Y").date()
        except ValueError:
            messagebox.showerror("Tarih Hatası", "Lütfen tarihleri GG.AA.YYYY (örn. 13.11.2025) formatında girin.")
            return

        if start_d > end_d:
            messagebox.showerror("Tarih Hatası", "Başlangıç tarihi bitiş tarihinden büyük olamaz.")
            return

        chunk_days = max(7, int(self.var_chunk_days.get() or 30))
        self.is_busy = True
        self.stop_requested = False

        def worker():
            try:
                if not self.tckn:
                    info = self.bridge.check_login_and_user()
                    user = info.get("user") or {}
                    self.tckn = str(user.get("tcKimlikNo") or user.get("tckn") or "")
                
                # Oturum yoksa ve otomatik relogin açıksa hemen dene
                if not self.tckn and self.var_auto_relogin.get():
                    self.log("UYAP oturumu bulunamadı, e-İmza ile otomatik giriş deneniyor...")
                    ok, msg = self.bridge.auto_relogin(pin=self.var_pin.get().strip())
                    if ok:
                        info = self.bridge.check_login_and_user()
                        user = info.get("user") or {}
                        self.tckn = str(user.get("tcKimlikNo") or user.get("tckn") or "")

                if not self.tckn:
                    self.log("HATA: UYAP oturumu açılamadı. Lütfen e-İmza ile giriş yapın.", level="ERROR")
                    return

                # Tarih aralığını dilimlere böl
                ranges = []
                cur = start_d
                while cur <= end_d:
                    nxt = min(cur + dt.timedelta(days=chunk_days - 1), end_d)
                    ranges.append((cur, nxt))
                    cur = nxt + dt.timedelta(days=1)

                self.log(
                    f"İşlemlerim taranıyor: {start_d.strftime('%d.%m.%Y')} - {end_d.strftime('%d.%m.%Y')} "
                    f"({len(ranges)} dilim halinde)..."
                )
                seen_keys = {item["unique_key"] for item in self.all_items}
                added_count = 0

                for idx, (s_d, e_d) in enumerate(ranges, start=1):
                    if self.stop_requested:
                        self.log("Tarama kullanıcı tarafından durduruldu.")
                        break

                    s_str = s_d.strftime("%d.%m.%Y")
                    e_str = e_d.strftime("%d.%m.%Y")
                    self.log(f"[{idx}/{len(ranges)}] Sorgulanıyor: {s_str} - {e_str} ...")

                    resp = self.bridge.query_uyap_islemlerim(self.tckn, s_str, e_str, islem_turu=None)
                    
                    # Oturum düştüyse otomatik yenile ve dilimi tekrar dene
                    if not resp.get("ok") or resp.get("status") in (401, 403):
                        if self.var_auto_relogin.get():
                            self.log("Tarama sırasında UYAP oturumu düştü, e-İmza ile otomatik yenileniyor...")
                            self.bridge.auto_relogin(pin=self.var_pin.get().strip())
                            time.sleep(2.0)
                            resp = self.bridge.query_uyap_islemlerim(self.tckn, s_str, e_str, islem_turu=None)

                    rows = resp.get("data")
                    if isinstance(rows, dict):
                        rows = rows.get("data") or rows.get("list") or []
                    if not isinstance(rows, list):
                        rows = []

                    chunk_added = 0
                    for r in rows:
                        if not isinstance(r, dict):
                            continue
                        evrak_id = str(r.get("evrakId") or "").strip()
                        gg_evrak_id = str(r.get("ggEvrakId") or "").strip()
                        is_emir_no = str(r.get("isEmirNo") or "").strip()
                        # UYAP evrakId'yi her sorguda dinamik şifreler; sabit ve kalıcı kimlik is_emir_no'dur
                        if is_emir_no:
                            ukey = f"islem_{is_emir_no}"
                        else:
                            ukey = f"islem_{evrak_id}_{gg_evrak_id}"
                        if ukey in seen_keys:
                            continue
                        seen_keys.add(ukey)

                        parsed_date = (
                            parse_uyap_date(r.get("isEmirTarihi"))
                            or parse_uyap_date(r.get("birimEvrakTarihi"))
                            or s_d
                        )
                        birim_adi = str(r.get("birimAdi") or "Belirtilmemis_Birim").strip()
                        dosya_no = str(r.get("dosyaNo") or "DosyaNo_Yok").strip()
                        evrak_adi = str(r.get("name") or r.get("evrakTuru") or "Evrak").strip()
                        evrak_turu_kod = str(r.get("evrakTuru") or evrak_adi).strip()
                        isin_durumu = str(r.get("isinDurumu") or "Tamamlandı").strip()
                        dosya_turu = infer_dosya_turu(birim_adi)

                        item = {
                            "unique_key": ukey,
                            "kaynak": "Islemlerim",
                            "tarih_obj": parsed_date,
                            "tarih": parsed_date.strftime("%Y-%m-%d"),
                            "yil": parsed_date.strftime("%Y"),
                            "yil_ay": parsed_date.strftime("%Y-%m"),
                            "dosya_turu": dosya_turu,
                            "birim_adi": birim_adi,
                            "dosya_no": dosya_no,
                            "dosya_id": str(r.get("dosyaId") or ""),
                            "islem_turu": f"Gonderilen_Islem ({isin_durumu})",
                            "evrak_turu": evrak_adi,
                            "evrak_turu_kod": evrak_turu_kod,
                            "evrak_adi": evrak_adi,
                            "evrak_id": evrak_id,
                            "gg_evrak_id": gg_evrak_id,
                            "is_emir_no": is_emir_no,
                            "download_params": {
                                "evrakId": evrak_id,
                                "gelenGidenEvrakId": gg_evrak_id,
                            },
                            "can_download": bool(evrak_id),
                        }
                        self.all_items.append(item)
                        chunk_added += 1
                        added_count += 1

                    self.log(f"  -> {len(rows)} kayıt döndü ({chunk_added} yeni kayıt eklendi).")
                    self.root.after(0, self.refresh_filter_options_and_table)

                    if idx < len(ranges):
                        time.sleep(random.uniform(2.2, 4.0))

                self.log(f"İşlemlerim taraması tamamlandı. Toplam {added_count} yeni işlem/evrak listeye eklendi.")
            except Exception as e:
                self.log(f"Tarama sırasında hata: {e}", level="ERROR")
            finally:
                self.is_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def on_scan_fav_cases(self):
        if self.is_busy:
            messagebox.showwarning("Meşgul", "Şu anda devam eden bir işlem var.")
            return
        self.is_busy = True
        self.stop_requested = False

        def worker():
            try:
                self.log("Sık Kullanılan Dosyalarım listesi çekiliyor...")
                cases = self.bridge.query_sik_kullanilan_dosyalar()
                if not cases:
                    self.log("Sık kullanılan dosya bulunamadı veya oturum açık değil.", level="WARNING")
                    return

                self.log(f"{len(cases)} adet sık kullanılan dosya bulundu. Evrakları taranıyor...")
                seen_keys = {item["unique_key"] for item in self.all_items}
                added_count = 0

                for idx, c in enumerate(cases, start=1):
                    if self.stop_requested:
                        break
                    dosya_id = str(c.get("dosyaID") or c.get("dosyaId") or "").strip()
                    dosya_no = str(c.get("dosyaNO") or c.get("dosyaNo") or "").strip()
                    birim_adi = str(c.get("birimAdi") or c.get("mahkemeAdi") or "").strip()
                    explicit_tur = str(c.get("dosyaTurAciklama") or c.get("dosyaTuru") or "").strip()
                    if not dosya_id:
                        continue

                    self.log(f"[{idx}/{len(cases)}] {birim_adi} {dosya_no} evrakları sorgulanıyor...")
                    pages = self.bridge.query_dosya_evraklar(dosya_id)

                    def collect_evrak(ev):
                        nonlocal added_count
                        if not isinstance(ev, dict):
                            return
                        ev_id = str(ev.get("evrakId") or "").strip()
                        if ev_id:
                            ukey = f"dosya_{dosya_id}_{ev_id}"
                            if ukey not in seen_keys:
                                seen_keys.add(ukey)
                                p_date = (
                                    parse_uyap_date(ev.get("onaylandigiTarih"))
                                    or parse_uyap_date(ev.get("sistemeGonderildigiTarih"))
                                    or dt.date.today()
                                )
                                tip = str(ev.get("tip") or "DOSYA").strip()
                                tur = str(ev.get("tur") or "Evrak").strip()
                                item = {
                                    "unique_key": ukey,
                                    "kaynak": "Dosya_Evraklari",
                                    "tarih_obj": p_date,
                                    "tarih": p_date.strftime("%Y-%m-%d"),
                                    "yil": p_date.strftime("%Y"),
                                    "yil_ay": p_date.strftime("%Y-%m"),
                                    "dosya_turu": infer_dosya_turu(birim_adi, explicit_tur),
                                    "birim_adi": birim_adi or str(ev.get("gonderenYerKisi") or "Birim"),
                                    "dosya_no": dosya_no or str(ev.get("gonderenDosyaNo") or "DosyaNo"),
                                    "dosya_id": dosya_id,
                                    "islem_turu": f"Dosya_Evraki_{tip}",
                                    "evrak_turu": tur,
                                    "evrak_turu_kod": tur,
                                    "evrak_adi": tur,
                                    "evrak_id": ev_id,
                                    "gg_evrak_id": "",
                                    "is_emir_no": str(ev.get("birimEvrakNo") or ""),
                                    "download_params": {
                                        "dosyaId": dosya_id,
                                        "evrakId": ev_id,
                                    },
                                    "can_download": True,
                                }
                                self.all_items.append(item)
                                added_count += 1
                        for ek in ev.get("ekEvrakListesi") or []:
                            collect_evrak(ek)

                    for p in pages:
                        if isinstance(p, dict):
                            tum = p.get("tumEvraklar") or p
                            if isinstance(tum, dict):
                                for sub_k, sub_v in tum.items():
                                    if isinstance(sub_v, list):
                                        for ev in sub_v:
                                            collect_evrak(ev)
                            elif isinstance(tum, list):
                                for ev in tum:
                                    collect_evrak(ev)
                        elif isinstance(p, list):
                            for ev in p:
                                collect_evrak(ev)

                    self.root.after(0, self.refresh_filter_options_and_table)
                    if idx < len(cases):
                        time.sleep(random.uniform(2.5, 4.5))

                self.log(f"Dosya evrakları taraması tamamlandı. {added_count} yeni evrak eklendi.")
            except Exception as e:
                self.log(f"Dosya evrakları taranırken hata: {e}", level="ERROR")
            finally:
                self.is_busy = False

        threading.Thread(target=worker, daemon=True).start()

    # -----------------------------------------------------------------------
    # Filtreleme ve Tablo Yönetimi
    # -----------------------------------------------------------------------
    def refresh_filter_options_and_table(self):
        dosya_turleri = sorted({it["dosya_turu"] for it in self.all_items if it.get("dosya_turu")})
        evrak_turleri = sorted({it["evrak_turu"] for it in self.all_items if it.get("evrak_turu")})
        islem_turleri = sorted({it["islem_turu"] for it in self.all_items if it.get("islem_turu")})

        self.cb_dosya_turu["values"] = ["TÜMÜ"] + dosya_turleri
        self.cb_evrak_turu["values"] = ["TÜMÜ"] + evrak_turleri
        self.cb_islem_turu["values"] = ["TÜMÜ"] + islem_turleri

        self.apply_filters()

    def reset_filters(self):
        self.var_filter_dosya_turu.set("TÜMÜ")
        self.var_filter_evrak_turu.set("TÜMÜ")
        self.var_filter_islem_turu.set("TÜMÜ")
        self.var_filter_search.set("")
        self.apply_filters()

    def apply_filters(self):
        f_dt = self.var_filter_dosya_turu.get()
        f_et = self.var_filter_evrak_turu.get()
        f_it = self.var_filter_islem_turu.get()
        f_q = self.var_filter_search.get().strip().lower()

        res = []
        for it in self.all_items:
            if f_dt != "TÜMÜ" and it["dosya_turu"] != f_dt:
                continue
            if f_et != "TÜMÜ" and it["evrak_turu"] != f_et:
                continue
            if f_it != "TÜMÜ" and it["islem_turu"] != f_it:
                continue
            if f_q:
                haystack = f"{it['birim_adi']} {it['dosya_no']} {it['evrak_turu']} {it['evrak_id']}".lower()
                if f_q not in haystack:
                    continue
            res.append(it)

        # Tarihe göre yeniden eskiye sırala
        res.sort(key=lambda x: x["tarih"], reverse=True)
        self.filtered_items = res

        # Tabloyu güncelle
        self.tree.delete(*self.tree.get_children())
        for it in self.filtered_items:
            ukey = it["unique_key"]
            if not it["can_download"]:
                status = "İndirilemez (ID Yok)"
            elif self.is_item_already_downloaded(it):
                status = "İndirildi"
            else:
                status = "Bekliyor"
            self.tree.insert(
                "",
                tk.END,
                iid=ukey,
                values=(
                    status,
                    it["tarih"],
                    it["dosya_turu"],
                    it["birim_adi"],
                    it["dosya_no"],
                    it["islem_turu"],
                    it["evrak_turu"],
                    it["evrak_id"],
                ),
            )

        self.lbl_count.config(text=f"Toplam: {len(self.all_items)} | Filtrelenen: {len(self.filtered_items)}")

    def build_target_filepath(self, item: dict, ext: str, override_dir: Path | None = None) -> Path:
        if override_dir:
            base_dir = Path(override_dir)
        elif hasattr(self, "var_download_dir"):
            base_dir = Path(self.var_download_dir.get().strip() or str(DEFAULT_DOWNLOAD_DIR))
        else:
            base_dir = DEFAULT_DOWNLOAD_DIR

        if hasattr(self, "var_template"):
            tpl = self.var_template.get().strip() or FOLDER_PRESETS[0][1]
        else:
            tpl = FOLDER_PRESETS[0][1]

        tokens = {
            "kaynak": sanitize_path_part(item.get("kaynak"), "UYAP"),
            "yil": sanitize_path_part(item.get("yil"), "Yil"),
            "yil_ay": sanitize_path_part(item.get("yil_ay"), "Yil_Ay"),
            "tarih": sanitize_path_part(item.get("tarih"), "Tarih"),
            "dosya_turu": sanitize_path_part(item.get("dosya_turu"), "Dosya_Turu"),
            "birim_adi": sanitize_path_part(item.get("birim_adi"), "Birim"),
            "dosya_no": sanitize_path_part(item.get("dosya_no"), "DosyaNo"),
            "islem_turu": sanitize_path_part(item.get("islem_turu"), "Islem_Turu"),
            "evrak_turu": sanitize_path_part(item.get("evrak_turu"), "Evrak_Turu"),
            "evrak_adi": sanitize_path_part(item.get("evrak_adi"), "Evrak"),
            "evrak_id": sanitize_path_part(item.get("evrak_id"), "0"),
            "is_emir_no": sanitize_path_part(item.get("is_emir_no"), ""),
        }

        rel_str = tpl.format(**tokens)
        parts = [sanitize_path_part(p, "Klasor", max_len=90) for p in rel_str.replace("\\", "/").split("/") if p.strip()]
        if not parts:
            parts = [f"evrak_{tokens['is_emir_no'] or tokens['evrak_id']}"]

        ident = tokens["is_emir_no"] or tokens["evrak_id"]
        # v4.9.3: Windows MAX_PATH (260) — AppData altındaki kökle birlikte "Avukat Evrak Kaydi (İstinaf Ba..."
        # gibi uzun klasör adları sınırı aşıyor, "[Errno 2] No such file or directory" ile İşlemlerim çöküyordu.
        # EN: shrink folder parts and file stem until the absolute path fits in 230 chars (.part suffix included).
        sinir = 230
        def _tam(pp):
            return len(str(base_dir.joinpath(*pp[:-1]))) + 1 + len(f"{pp[-1]}_{ident}{ext}.part")
        uzunluk = 50
        while _tam(parts) > sinir and uzunluk >= 12:
            parts = [x[:uzunluk].rstrip(". _") or "Klasor" for x in parts]
            uzunluk -= 6
        if _tam(parts) > sinir:
            parts = parts[:1] + [parts[-1][:35]]
        filename_stem = f"{parts[-1]}_{ident}"
        folder_path = base_dir.joinpath(*parts[:-1])
        try:
            os.makedirs(win_extended_path(folder_path), exist_ok=True)
        except Exception:
            folder_path.mkdir(parents=True, exist_ok=True)
        return folder_path / f"{filename_stem}{ext}"

    def on_choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.var_download_dir.get(), title="İndirme Klasörünü Seçin")
        if d:
            self.var_download_dir.set(d)

    def on_toggle_pause(self):
        self.pause_requested = not self.pause_requested
        if self.pause_requested:
            self.log("İndirme duraklatıldı. Devam etmek için tekrar 'Duraklat / Devam Et' butonuna basın.")
            self.btn_pause.config(text="Devam Et")
        else:
            self.log("İndirmeye devam ediliyor...")
            self.btn_pause.config(text="Duraklat")

    def on_stop(self):
        self.stop_requested = True
        self.pause_requested = False
        self.log("Durdurma isteği gönderildi, mevcut dosya tamamlanınca duracak...")

    # -----------------------------------------------------------------------
    # Güvenli İndirme Motoru (Otomatik e-İmza Yenilemeli & Atomik Yazmalı)
    # -----------------------------------------------------------------------
    def on_start_download(self, selected_only: bool = False):
        if self.is_busy:
            messagebox.showwarning("Meşgul", "Şu anda devam eden bir işlem var.")
            return

        if selected_only:
            sel_iids = set(self.tree.selection())
            if not sel_iids:
                messagebox.showinfo("Seçim Yok", "Lütfen önce tablodan indirmek istediğiniz satırları seçin.")
                return
            queue = [it for it in self.filtered_items if it["unique_key"] in sel_iids]
        else:
            queue = list(self.filtered_items)

        skip_done = self.var_skip_downloaded.get()
        # Mükerrerlik ve eksiklik kontrolü: Sadece fiziksel dosyası tam olanları atla
        download_queue = [
            it for it in queue if it["can_download"] and (not skip_done or not self.is_item_already_downloaded(it))
        ]

        skipped_count = len(queue) - len(download_queue)
        if skip_done and skipped_count > 0:
            self.log(
                f"MÜKERRERLİK KORUMASI: Daha önce başarıyla indirilmiş {skipped_count} evrak atlandı. "
                f"Sadece kalan {len(download_queue)} eksik evrak için indirme başlatılıyor."
            )

        if not download_queue:
            messagebox.showinfo(
                "Tümü İndirilmiş",
                f"Seçili kriterlere uygun {len(queue)} evrakın tamamı daha önce indirilmiş ve diskte sağlam olarak mevcuttur.\n\nHiçbir evrak tekrar indirilmeyecektir."
            )
            return

        min_d = max(1.0, float(self.var_min_delay.get() or 3.5))
        max_d = max(min_d + 0.5, float(self.var_max_delay.get() or 7.0))
        batch_n = max(3, int(self.var_batch_size.get() or 15))
        batch_pause = max(5.0, float(self.var_batch_pause.get() or 20.0))

        self.is_busy = True
        self.stop_requested = False
        self.pause_requested = False
        self.btn_pause.config(state=tk.NORMAL, text="Duraklat")
        self.btn_stop.config(state=tk.NORMAL)
        self.progress["maximum"] = len(download_queue)
        self.progress["value"] = 0

        def worker():
            downloaded_now = 0
            max_retries = 3
            try:
                self.log(
                    f"Toplam {len(download_queue)} evrak için güvenli indirme başlatıldı "
                    f"(Gecikme: {min_d:.1f}-{max_d:.1f} sn, Her {batch_n} dosyada {batch_pause:.0f} sn mola, "
                    f"Oturum Koruması: {'Açık' if self.var_auto_relogin.get() else 'Kapalı'})."
                )
                for idx, item in enumerate(download_queue, start=1):
                    while self.pause_requested and not self.stop_requested:
                        time.sleep(0.5)
                    if self.stop_requested:
                        self.log("İndirme kullanıcı tarafından durduruldu.")
                        break

                    ukey = item["unique_key"]
                    self.root.after(0, lambda k=ukey: self._update_row_status(k, "İndiriliyor..."))

                    success = False
                    for attempt in range(1, max_retries + 1):
                        while self.pause_requested and not self.stop_requested:
                            time.sleep(0.5)
                        if self.stop_requested:
                            break

                        resp = self.bridge.download_document(item["download_params"])
                        err_hdr = resp.get("errorHeader")
                        status_code = resp.get("status", 0)
                        ct = resp.get("contentType") or ""
                        raw_bytes = base64.b64decode(resp.get("base64") or "") if resp.get("base64") else b""

                        # İçerik doğrulama: HTML, JSON hata veya 0 bayt kontrolü
                        is_valid, reason = is_valid_document_bytes(raw_bytes, ct)
                        need_relogin = (
                            not resp.get("ok")
                            or status_code in (401, 403, 302, 500)
                            or bool(err_hdr)
                            or not is_valid
                        )

                        if need_relogin:
                            is_session_dead = (
                                not self.bridge.is_logged_in()
                                or "oturum" in reason.lower()
                                or "html" in reason.lower()
                                or "nosessionobject" in reason.lower()
                                or "prtl_gnl" in reason.lower()
                                or status_code in (401, 403, 302)
                                or "text/html" in ct.lower()
                            )

                            if not is_session_dead and self.bridge.is_logged_in() and "text/html" not in ct.lower():
                                self.log(
                                    f"BİLGİ: {item['evrak_adi']} UYAP sunucusunda fiziksel dosya olarak mevcut değil (Ekli dosya yok / Sunucu boş yanıt verdi). Atlandı."
                                )
                                break

                            self.log(
                                f"UYARI: {item['evrak_adi']} indirilemedi ({reason}) [Deneme {attempt}/{max_retries}]",
                                level="WARNING"
                            )
                            if self.var_auto_relogin.get() and attempt < max_retries:
                                pin_val = self.var_pin.get().strip() or DEFAULT_E_IMZA_PIN
                                self.log(f"UYAP oturumu tazelemek için e-İmza ile otomatik giriş yapılıyor (PIN: {pin_val})...")
                                relogin_ok, relogin_msg = self.bridge.auto_relogin(pin=pin_val)
                                if relogin_ok:
                                    self.log(f"Başarılı: {relogin_msg}. Evrak tekrar indiriliyor...")
                                    self._sleep_interruptible(2.5)
                                    continue
                                else:
                                    self.log(f"HATA: {relogin_msg}", level="ERROR")
                                    self._sleep_interruptible(3.0)
                            else:
                                if attempt < max_retries:
                                    self._sleep_interruptible(3.0)
                                    continue

                        if is_valid:
                            cd = resp.get("contentDisposition") or ""
                            cd_filename = ""
                            m = re.search(r'filename\*?=["\']?(?:UTF-8\'\')?([^;"\']+)', cd, re.IGNORECASE)
                            if m:
                                cd_filename = m.group(1).strip()

                            ext = guess_extension(cd_filename, ct, raw_bytes)
                            target_path = self.build_target_filepath(item, ext)

                            # Atomik dosya kaydı: Önce .part dosyasına yaz, sonra doğrula ve taşı
                            tmp_path = target_path.with_suffix(target_path.suffix + ".part")
                            safe_write_bytes(tmp_path, raw_bytes)

                            ext_tmp = win_extended_path(tmp_path)
                            if os.path.exists(ext_tmp) and os.path.getsize(ext_tmp) == len(raw_bytes):
                                safe_replace_file(tmp_path, target_path)
                            else:
                                safe_write_bytes(target_path, raw_bytes)
                                try:
                                    os.unlink(ext_tmp)
                                except OSError:
                                    pass

                            auto_convert_udf_to_pdf(target_path)

                            sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

                            self.history[ukey] = {
                                "path": str(target_path),
                                "sha256": sha256_hash,
                                "downloaded_at": dt.datetime.now().isoformat(timespec="seconds"),
                                "size": len(raw_bytes),
                                "tarih": item["tarih"],
                                "dosya_turu": item["dosya_turu"],
                                "birim_adi": item["birim_adi"],
                                "dosya_no": item["dosya_no"],
                                "islem_turu": item["islem_turu"],
                                "evrak_turu": item["evrak_turu"],
                                "evrak_id": item["evrak_id"],
                                "is_emir_no": item.get("is_emir_no", ""),
                            }
                            self._save_history()
                            downloaded_now += 1
                            success = True

                            rel_display = target_path.relative_to(Path(self.var_download_dir.get())) if target_path.is_relative_to(Path(self.var_download_dir.get())) else target_path
                            self.log(f"[{idx}/{len(download_queue)}] Kaydedildi ({len(raw_bytes)//1024} KB): {rel_display}")
                            self.root.after(0, lambda k=ukey, v=idx: self._on_item_downloaded(k, v))
                            break

                    if not success and not self.stop_requested:
                        self.log(
                            f"HATA: Evrak {max_retries} denemede de indirilemedi: {item['evrak_adi']} ({ukey}). "
                            "UYAP güvenliği için indirme duraklatıldı.",
                            level="ERROR"
                        )
                        self.pause_requested = True
                        self.root.after(0, lambda: self.btn_pause.config(text="Devam Et"))
                        self.root.after(0, lambda k=ukey: self._update_row_status(k, "Hata (İndirilemedi)"))
                        continue

                    # Güvenli bekleme ve mola yönetimi
                    if idx < len(download_queue) and not self.stop_requested:
                        if downloaded_now > 0 and downloaded_now % batch_n == 0:
                            jitter_pause = batch_pause + random.uniform(0.0, 5.0)
                            self.log(f"UYAP koruma molası: {downloaded_now} dosya indirildi, {jitter_pause:.1f} sn dinleniliyor...")
                            self._sleep_interruptible(jitter_pause)
                        else:
                            wait_s = random.uniform(min_d, max_d)
                            self._sleep_interruptible(wait_s)

                self._write_summary_csv()
                self.log(f"İndirme oturumu tamamlandı. Bu oturumda {downloaded_now} dosya eksiksiz indirildi.")
            except Exception as e:
                self.log(f"İndirme sırasında beklenmeyen hata: {e}", level="ERROR")
            finally:
                self.is_busy = False
                self.root.after(0, self._reset_buttons)

        threading.Thread(target=worker, daemon=True).start()

    def _sleep_interruptible(self, seconds: float):
        end_t = time.time() + seconds
        while time.time() < end_t:
            if self.stop_requested:
                break
            time.sleep(0.25)

    def _update_row_status(self, ukey: str, status_text: str):
        if self.tree.exists(ukey):
            vals = list(self.tree.item(ukey, "values"))
            vals[0] = status_text
            self.tree.item(ukey, values=vals)

    def _on_item_downloaded(self, ukey: str, progress_val: int):
        self._update_row_status(ukey, "İndirildi")
        self.progress["value"] = progress_val

    def _reset_buttons(self):
        self.btn_pause.config(state=tk.DISABLED, text="Duraklat / Devam Et")
        self.btn_stop.config(state=tk.DISABLED)

    def _write_summary_csv(self):
        try:
            base_dir = Path(self.var_download_dir.get().strip() or str(DEFAULT_DOWNLOAD_DIR))
            base_dir.mkdir(parents=True, exist_ok=True)
            csv_path = base_dir / "indirme_indeksi.csv"
            with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow([
                    "Durum", "Tarih", "Dosya Türü", "Birim Adı", "Dosya No",
                    "İşlem Türü", "Evrak Türü", "Evrak ID", "Kaydedilen Dosya Yolu"
                ])
                for it in self.all_items:
                    ukey = it["unique_key"]
                    h = self.history.get(ukey, {})
                    writer.writerow([
                        "İndirildi" if h else "Bekliyor",
                        it["tarih"],
                        it["dosya_turu"],
                        it["birim_adi"],
                        it["dosya_no"],
                        it["islem_turu"],
                        it["evrak_turu"],
                        it["evrak_id"],
                        h.get("path", ""),
                    ])
        except Exception as e:
            self.log(f"CSV indeksi yazılamadı: {e}", level="WARNING")

    def on_export_csv(self):
        if not self.filtered_items:
            messagebox.showinfo("Veri Yok", "Dışa aktarılacak kayıt bulunmuyor.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile="uyap_evrak_listesi.csv",
            filetypes=[("CSV Dosyası (Excel Uyumlu)", "*.csv")],
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([
                "Durum", "Tarih", "Dosya Türü", "Birim Adı", "Dosya No",
                "İşlem Türü", "Evrak Türü", "Evrak ID", "Dosya Yolu"
            ])
            for it in self.filtered_items:
                h = self.history.get(it["unique_key"], {})
                writer.writerow([
                    "İndirildi" if h else "Bekliyor",
                    it["tarih"],
                    it["dosya_turu"],
                    it["birim_adi"],
                    it["dosya_no"],
                    it["islem_turu"],
                    it["evrak_turu"],
                    it["evrak_id"],
                    h.get("path", ""),
                ])
        self.log(f"Liste dışa aktarıldı: {path}")


def refresh_dosya_ids_in_queue(bridge, queue: list, start_idx: int):
    """
    Oturum yenilendiğinde (Mobil İmza sonrası), UYAP sunucusunun dinamik olarak
    yeniden şifrelediği taze dosyaId token'larını çeker ve indirme kuyruğunu günceller.
    """
    print("[*] Yeni oturum için dosya token'ları (dosyaId) güncelleniyor...")
    try:
        fresh_cases = bridge.query_tum_dosyalar(include_closed=True, use_cache=False)
        case_map = {}
        for fc in fresh_cases:
            b_name = str(fc.get("birimAdi") or fc.get("mahkemeAdi") or "").strip()
            d_no = str(fc.get("dosyaNO") or fc.get("dosyaNo") or "").strip()
            n_id = str(fc.get("dosyaID") or fc.get("dosyaId") or "").strip()
            if b_name and d_no and n_id:
                case_map[(b_name, d_no)] = n_id

        updated = 0
        for i in range(max(0, start_idx), len(queue)):
            it = queue[i]
            k = (it["birim_adi"], it["dosya_no"])
            if k in case_map:
                new_id = case_map[k]
                if it.get("download_params"):
                    it["download_params"]["dosyaId"] = new_id
                it["dosya_id"] = new_id
                ev_id = str(it.get("evrak_id") or "")
                it["unique_key"] = f"dosya_{new_id}_{ev_id}"
                updated += 1
        print(f"[✓] Kuyruktaki {updated} adet evrakın dosyaId token'ı yeni oturuma başarıyla uyarlandı.")
    except Exception as e:
        print(f"[!] Oturum token'ı güncelleme uyarısı: {e}")


_DOSYA_NUM_RX = re.compile(r"_(?:evrak_)?([0-9A-Za-z\-]+)$")


def _norm_dno(dno: str) -> str:
    """'2026/234 Esas' -> '2026-234' (dosya adlarında '/' yerine '-' kullanılır)."""
    m = re.search(r"(\d{4})\s*[/\-_]\s*(\d+)", str(dno or ""))
    return f"{m.group(1)}-{int(m.group(2))}" if m else ""


def build_dosya_disk_keys(base: Path) -> dict:
    """Dava dosyası evraklarının klasöründeki dosyalardan kalıcı eşleşme anahtarları çıkarır.
    Dosya adı biçimleri: 'YYYY-MM-DD_..._evrak_NNNN.udf' ve eski 'YYYY-MM-DD_..._NNNN.udf'.
    Windows / Termux yolu fark etmez; yalnızca dosya adı ve klasör adları kullanılır."""
    keys = {"date_num": set(), "date_dno": set()}
    if not base.exists():
        return keys
    for dirpath, _dirs, files in os.walk(base):
        rel_dirs = os.path.relpath(dirpath, base)
        for fn in files:
            low = fn.lower()
            if low.endswith((".part", ".csv", ".json", ".md", ".ics")) or ".yedek" in low:
                continue
            stem = fn.rsplit(".", 1)[0]
            if not re.match(r"^\d{4}-\d{2}-\d{2}_", stem):
                continue
            try:
                if (Path(dirpath) / fn).stat().st_size < 128:
                    continue
            except OSError:
                continue
            date = stem[:10]
            m = _DOSYA_NUM_RX.search(stem)
            if m:
                keys["date_num"].add((date, m.group(1).lower()))
            # Tarih önekini ve 'K2025-12' gibi karar no'larını dosya no sanma
            for src in (stem[11:], rel_dirs):
                for mm in re.finditer(r"(?<![0-9A-Za-z.])(\d{4})[\-_](\d+)(?![0-9.])", src):
                    if 1990 <= int(mm.group(1)) <= 2100:
                        keys["date_dno"].add((date, f"{mm.group(1)}-{int(mm.group(2))}"))
    return keys


def dosya_item_on_disk(item: dict, keys: dict, same_day_ok: bool) -> str:
    """Diskte varsa eşleşme türünü ('no' / 'gun'), yoksa '' döner."""
    date = str(item.get("tarih") or "")
    clean_ev_id = str(item.get("evrak_id") or "").replace('"', "").replace("'", "").strip()
    doc_num = sanitize_path_part(item.get("is_emir_no") or clean_ev_id[:8], max_len=20).lower()
    if item.get("is_emir_no") and (date, doc_num) in keys["date_num"]:
        return "no"
    # Aynı gün + aynı dosya no: duruşma/karar/tensip gibi günde tek evrak olan türlerde güvenli
    if same_day_ok:
        dno = _norm_dno(item.get("dosya_no"))
        if dno and (date, dno) in keys["date_dno"]:
            return "gun"
    return ""


def _kategori_adi(kod: str) -> str:
    try:
        from evrak_turleri import KATEGORI_ADI
        return KATEGORI_ADI.get(kod, "")
    except ImportError:
        return ""


def run_cli_dosyalar_mode(args, bridge, app_helper, download_dir, tckn):
    """
    Dava Dosyalarından Belirli Evrak Türlerini (Duruşma Tutanağı, Bilirkişi Raporu, Karar vb.)
    ve eklerini toplu olarak indiren CLI fonksiyonu.
    """
    print("\n" + "=" * 70)
    print("  UYAP Avukat Portal - Dava Dosyalarından Evrak İndirici (CLI)")
    print("=" * 70 + "\n")

    evrak_filter = getattr(args, "evrak_turu", "").strip().lower()
    include_attachments = getattr(args, "include_attachments", False)

    if not evrak_filter:
        print("[*] İndirmek istediğiniz evrak türünü seçiniz:")
        print("  1) Duruşma Tutanakları / Zabıtları (Asıl + Talimat, Celse Zabıtları, SEGBİS) [Önerilen]")
        print("  2) Bilirkişi Raporları (Kök + Ek Rapor, Uzman Görüşü, Adli Tıp / Kriminal)")
        print("  3) Gerekçeli Karar, Hüküm ve İlamlar (BAM, Yargıtay, Kısa Karar, Ek Karar)")
        print("  4) Tensip Zabıtları (İlk Tensip, Talimat Tensip Zaptı)")
        print("  5) Dava & Cevap Layihaları (Tüm Taraflar: Dava, Cevap, Replik, Düplik, Delil, İtiraz, Savunma)")
        print("  6) Tebligat & Mazbatalar (Fiziki PTT + UETS Elektronik Tebligat & Takip CSV'si)")
        print("  7) Müzekkere ve Kurum Cevapları (Banka, Tapu, SGK, EGM, HTS, Nüfus vb.)")
        print("  8) İddianame ve Ceza Başvuru Evrakları (İddianame, Fezleke, İddianame Kabul)")
        print("  9) Kesinleşme Şerhleri")
        print(" 10) TÜM Evraklar ve Ekleri (Toplu Eksiksiz Arşiv)")
        print(" 11) Özel Kelime Arama (Serbest Metin)")
        print(" 12) Tutuklama / Adli Kontrol / Yakalama Evrakları")
        print(" 13) İfade / Sorgu / Tutanak / Keşif")
        print(" 14) Vekaletname / Yetki Belgesi")
        print(" 15) İcra / Haciz / Satış")
        print(" 16) Makbuz / Harç / Masraf / Reddiyat")
        print(" 17) Talimat Yazışmaları")
        print("-" * 65)
        print("[i] Daha ayrıntılı seçim (taraf, müvekkil, tarih, evrak türü...) için: python uyap_indirici.py --katalog")
        try:
            sec = input("Seçiminiz (1-17) [Varsayılan: 1]: ").strip() or "1"
        except (EOFError, KeyboardInterrupt):
            sec = "1"

        if sec == "1":
            evrak_filter = "durusma"
        elif sec == "2":
            evrak_filter = "bilirkisi"
        elif sec == "3":
            evrak_filter = "karar"
        elif sec == "4":
            evrak_filter = "tensip"
        elif sec == "5":
            evrak_filter = "layihalar"
        elif sec == "6":
            evrak_filter = "tebligat"
        elif sec == "7":
            evrak_filter = "muzekkere"
        elif sec == "8":
            evrak_filter = "iddianame"
        elif sec == "9":
            evrak_filter = "kesinlesme"
        elif sec == "10":
            evrak_filter = "tumu"
            include_attachments = True
        elif sec in ("12", "13", "14", "15", "16", "17"):
            evrak_filter = {"12": "tutuklama", "13": "ifade", "14": "vekalet", "15": "icra",
                            "16": "mali", "17": "talimat"}[sec]
        elif sec == "11":
            try:
                evrak_filter = input("Aramak istediğiniz evrak türü / kelime: ").strip().lower()
            except Exception:
                evrak_filter = "tumu"
        else:
            evrak_filter = "durusma"

    filter_desc = {
        "durusma": "Duruşma Tutanakları (Zabıtlar, Celse Zabıtları, SEGBİS)",
        "bilirkisi": "Bilirkişi Raporları (Kök + Ek + Adli Tıp / Kriminal)",
        "karar": "Gerekçeli Karar, Hüküm ve İlamlar (BAM / Yargıtay)",
        "tensip": "Tensip Zabıtları (İlk + Talimat Tensip)",
        "layihalar": "Dava & Cevap Layihaları ve Beyanlar (Tüm Taraflar)",
        "dilekce": "Dilekçeler ve Beyanlar (Dava, Cevap, İstinaf, Temyiz)",
        "tebligat": "Tebligat Evrakları ve Mazbatalar (Fiziki PTT + UETS Elektronik + Takip CSV'si)",
        "muzekkere": "Müzekkere ve Kurum Cevapları (Banka, Tapu, SGK, EGM vb.)",
        "iddianame": "İddianame ve Fezleke",
        "kesinlesme": "Kesinleşme Şerhleri",
        "tumu": "Tüm Evraklar ve Ek Belgeler (Toplu Tam Arşiv)",
    }.get(evrak_filter) or _kategori_adi(evrak_filter) or f"'{evrak_filter}' içeren evraklar"

    print(f"\n[*] Hedef Evrak Türü: {filter_desc}")

    scope = getattr(args, "scope", "all").strip().lower()
    include_closed = getattr(args, "include_closed", True)
    if scope == "acik":
        include_closed = False

    if scope == "fav":
        print("[*] Sık kullanılan aktif dosyalarınız sorgulanıyor...")
        cases = bridge.query_sik_kullanilan_dosyalar()
    else:
        durum_str = "Tüm Dava Dosyaları (Açık + Kapalı / Karara Çıkmış)" if include_closed else "Yalnızca Açık Dava Dosyaları"
        print(f"[*] {durum_str} sorgulanıyor...")
        cases = bridge.query_tum_dosyalar(include_closed=include_closed)

    if not cases:
        print("[!] UYAP'ta dosya listesi alınamadı veya oturum kapalı.")
        return

    acik_c = sum(1 for c in cases if c.get("dosyaDurumGenel") == "Açık" or "açık" in str(c.get("dosyaDurum", "")).lower())
    kapali_c = len(cases) - acik_c
    print(f"[✓] Toplam {len(cases)} adet dosya tespit edildi ({acik_c} Açık, {kapali_c} Kapalı).")

    # Akıllı Yargı Ön Filtreleme & Hedef Mahkeme Arama
    filter_birim_kw = getattr(args, "filter_birim", "").strip().lower()
    yargi_filter = getattr(args, "yargi_turu", "").strip().lower()
    relevant_cases = []
    skipped_icra_count = 0
    skipped_yargi_count = 0

    for c in cases:
        birim = str(c.get("birimAdi") or c.get("mahkemeAdi") or "").strip()
        dosya = str(c.get("dosyaNO") or c.get("dosyaNo") or "").strip()

        # Spesifik birim / dosya filtresi (Örn: "erzurum" veya "2025/506")
        if filter_birim_kw:
            if filter_birim_kw not in tr_lower(birim) and filter_birim_kw not in tr_lower(dosya):
                continue

        # Yargı türü filtresi (hukuk, ceza, idari, icra)
        if yargi_filter and yargi_filter not in ("all", "tumu"):
            kat = infer_yargi_kategorisi(birim)
            if yargi_filter == "hukuk" and kat != "Hukuk_Yargisi":
                skipped_yargi_count += 1
                continue
            elif yargi_filter == "ceza" and kat != "Ceza_Yargisi":
                skipped_yargi_count += 1
                continue
            elif yargi_filter == "idari" and kat != "Idari_Yargi":
                skipped_yargi_count += 1
                continue
            elif yargi_filter == "icra" and kat not in ("Icra_Daireleri", "Icra_Mahkemeleri"):
                skipped_yargi_count += 1
                continue

        # Evrak türüne göre alakasız birimleri ele (Örn: İcra Dairesinde duruşma olmaz!)
        if not is_case_relevant_for_filter(birim, evrak_filter):
            skipped_icra_count += 1
            continue

        relevant_cases.append(c)

    if yargi_filter and yargi_filter not in ("all", "tumu"):
        print(f"[*] Yargı Türü Filtresi ('{yargi_filter.upper()}'): {len(relevant_cases)} dosya seçildi ({skipped_yargi_count} dosya elendi).")

    if skipped_icra_count > 0:
        print(f"[*] Akıllı Yargı Filtresi: {skipped_icra_count} adet ilgisiz dosya (İcra Dairesi / Bürolar) tarama dışı bırakıldı.")

    if getattr(args, "start_date", None):
        print(f"[*] Tarih Süzgeci: {args.start_date} tarihinden günümüze olan evraklar filtrelenecek.")

    if filter_birim_kw:
        print(f"[*] Arama Filtresi ('{filter_birim_kw}'): {len(relevant_cases)} adet dosya eşleşti.")

    if not relevant_cases:
        print("[!] Belirtilen kriterlere uygun incelenecek dava dosyası bulunamadı.")
        return

    print(f"[✓] Taranacak hedef dosya sayısı: {len(relevant_cases)} adet.")

    batch_size = 5
    total_batches = (len(relevant_cases) + batch_size - 1) // batch_size
    print(f"[*] Evrak listeleri hızlı paralel modda taranıyor ({total_batches} paket, paket başı {batch_size} dosya)...\n")

    found_documents = []
    seen_keys = set()
    seen_hearings = set()
    seen_evrak_ids = set()
    total_skipped_duplicates = 0

    for b_idx in range(0, len(relevant_cases), batch_size):
        chunk = relevant_cases[b_idx : b_idx + batch_size]
        chunk_ids = [str(c.get("dosyaID") or c.get("dosyaId") or "").strip() for c in chunk]
        chunk_ids = [cid for cid in chunk_ids if cid]

        batch_results = bridge.query_dosyalar_evraklar_batch(chunk_ids, chunk_size=len(chunk_ids))

        for c in chunk:
            dosya_id = str(c.get("dosyaID") or c.get("dosyaId") or "").strip()
            dosya_no = str(c.get("dosyaNO") or c.get("dosyaNo") or "DosyaNo_Yok").strip()
            birim_adi = str(c.get("birimAdi") or c.get("mahkemeAdi") or "Mahkeme").strip()
            if not dosya_id:
                continue

            pages = batch_results.get(dosya_id)
            if not pages:
                try:
                    pages = bridge.query_dosya_evraklar(dosya_id)
                except Exception:
                    pages = []

            case_found = 0

            def collect_doc(ev, is_attachment=False, parent_tur="", p_yer="", p_dosya="", p_tarih_obj=None):
                nonlocal case_found, total_skipped_duplicates
                if not isinstance(ev, dict):
                    return
                ev_id = str(ev.get("evrakId") or "").strip()
                if not ev_id or ev_id in seen_evrak_ids:
                    return

                tur = str(ev.get("ekTuru") if is_attachment else (ev.get("tur") or ev.get("aciklama") or "Evrak")).strip()
                yer = str(ev.get("gonderenYerKisi") or p_yer or birim_adi).strip()
                dno = str(ev.get("gonderenDosyaNo") or p_dosya or dosya_no).strip()

                p_date = (
                    parse_uyap_date(ev.get("onaylandigiTarih"))
                    or parse_uyap_date(ev.get("sistemeGonderildigiTarih"))
                    or p_tarih_obj
                    or dt.date.today()
                )
                tarih_str = p_date.strftime("%d.%m.%Y")

                is_match = matches_evrak_filter(tur, evrak_filter) or (
                    is_attachment and include_attachments and matches_evrak_filter(parent_tur, evrak_filter)
                )

                if is_match:
                    if getattr(args, "start_date", None):
                        try:
                            s_limit = dt.datetime.strptime(args.start_date, "%d.%m.%Y").date()
                            if p_date < s_limit:
                                return
                        except Exception:
                            pass
                    if getattr(args, "end_date", None):
                        try:
                            e_limit = dt.datetime.strptime(args.end_date, "%d.%m.%Y").date()
                            if p_date > e_limit:
                                return
                        except Exception:
                            pass

                    # Mükerrer / Kopya Evrak Kontrolü:
                    # Özellikle mahkemeler arası talimat, müzekkere ekinde gelen suretler veya
                    # birleşen dosyalarda aynı celse / kararın mükerrer indirilmesini önler.
                    if evrak_filter == "durusma":
                        dedup_key = f"{sanitize_path_part(yer).lower()}::{sanitize_path_part(dno).lower()}::{tarih_str}"
                        if dedup_key in seen_hearings:
                            total_skipped_duplicates += 1
                            return
                        seen_hearings.add(dedup_key)
                    elif evrak_filter in ("karar", "tensip", "iddianame"):
                        dedup_key = f"{evrak_filter}::{sanitize_path_part(yer).lower()}::{sanitize_path_part(dno).lower()}::{tarih_str}"
                        if dedup_key in seen_hearings:
                            total_skipped_duplicates += 1
                            return
                        seen_hearings.add(dedup_key)

                    seen_evrak_ids.add(ev_id)
                    ukey = f"dosya_{dosya_id}_{ev_id}"
                    if ukey in seen_keys:
                        return
                    seen_keys.add(ukey)

                    # Evrak adını zenginleştir: Eğer celse bilgisi (örn: "6. Celse") varsa ekle
                    aciklama = str(ev.get("aciklama") or "").strip()
                    display_tur = tur
                    if aciklama and aciklama.lower() not in tur.lower():
                        display_tur = f"{tur}_{aciklama}"

                    item = {
                        "unique_key": ukey,
                        "kaynak": "Dava_Dosyasi",
                        "tarih_obj": p_date,
                        "tarih": p_date.strftime("%Y-%m-%d"),
                        "yil": p_date.strftime("%Y"),
                        "yil_ay": p_date.strftime("%Y-%m"),
                        "dosya_turu": infer_dosya_turu(birim_adi),
                        "birim_adi": birim_adi,
                        "dosya_no": dosya_no,
                        "dosya_id": dosya_id,
                        "islem_turu": "Dava_Evraki_Ek" if is_attachment else "Dava_Evraki",
                        "evrak_turu": tur,
                        "evrak_turu_kod": tur,
                        "evrak_adi": f"EK_{display_tur}" if is_attachment else display_tur,
                        "evrak_id": ev_id,
                        "gg_evrak_id": str(ev.get("ggEvrakId") or ""),
                        "is_emir_no": str(ev.get("birimEvrakNo") or ev.get("anaEvrakId") or ""),
                        "is_attachment": is_attachment,
                        "download_params": {
                            "dosyaId": dosya_id,
                            "evrakId": ev_id,
                        },
                        "can_download": True,
                    }
                    found_documents.append(item)
                    case_found += 1

                # Evrak eklerini YALNIZCA kullanıcı özellikle talep etmişse (include_attachments=True) tara
                if include_attachments:
                    for ek in ev.get("ekEvrakListesi") or []:
                        collect_doc(
                            ek,
                            is_attachment=True,
                            parent_tur=tur,
                            p_yer=yer,
                            p_dosya=dno,
                            p_tarih_obj=p_date
                        )

            for p in pages:
                if isinstance(p, dict):
                    tum = p.get("tumEvraklar") or p
                    if isinstance(tum, dict):
                        for sub_k, sub_v in tum.items():
                            if isinstance(sub_v, list):
                                for ev in sub_v:
                                    collect_doc(ev)
                    elif isinstance(tum, list):
                        for ev in tum:
                            collect_doc(ev)
                elif isinstance(p, list):
                    for ev in p:
                        collect_doc(ev)

            if case_found > 0:
                print(f"  [+] {birim_adi} ({dosya_no}) -> {case_found} hedef evrak tespit edildi.")

        curr_batch = (b_idx // batch_size) + 1
        pct = min(100.0, ((b_idx + len(chunk)) / len(relevant_cases)) * 100)
        print(f"  --> [Paket {curr_batch}/{total_batches}] %{pct:.1f} tarandı (Şu ana kadar {len(found_documents)} hedef evrak bulundu)")

    print("\n" + "=" * 70)
    print(f"  TOPLAM BULUNAN HEDEF EVRAK     : {len(found_documents)} adet")
    if total_skipped_duplicates > 0:
        print(f"  MÜKERRER / KOPYA EVRAK (ELENDİ): {total_skipped_duplicates} adet")

    sub_folder_name ="DURUSMA_TUTANAKLARI" if evrak_filter == "durusma" else (
        "BILIRKISI_RAPORLARI" if evrak_filter == "bilirkisi" else (
            "GEREKCELI_KARARLAR" if evrak_filter == "karar" else (
                "TENSIP_ZAPITLARI" if evrak_filter == "tensip" else (
                    "DILEKCELER_LAYIHALAR" if evrak_filter in ("layihalar", "dilekce", "dilekceler") else (
                        "TEBLIGATLAR" if evrak_filter in ("tebligat", "tebligatlar", "mazbata") else (
                            "MUZEKKERE_VE_KURUM_CEVAPLARI" if evrak_filter in ("muzekkere", "muzekkereler", "kurum_cevaplari") else (
                                "IDDIANAMELER" if evrak_filter == "iddianame" else (
                                    "KESINLESME_SERHLERI" if evrak_filter == "kesinlesme" else "DAVA_EVRAKLARI"
                                )
                            )
                        )
                    )
                )
            )
        )
    )
    target_base = download_dir / sub_folder_name
    target_base.mkdir(parents=True, exist_ok=True)

    # Diskte var mı? UYAP'ın evrakId'si oturuma göre değiştiği için geçmiş anahtarı tutmaz;
    # dosya adındaki kalıcı bilgilerle (tarih + birim evrak no / tarih + dosya no) eşleştirilir.
    disk_keys = build_dosya_disk_keys(target_base)
    same_day_ok = evrak_filter in ("durusma", "karar", "tensip", "iddianame", "kesinlesme")
    download_queue = []
    match_stats = {"no": 0, "gun": 0, "gecmis": 0}
    for it in found_documents:
        how = dosya_item_on_disk(it, disk_keys, same_day_ok)
        if how:
            match_stats[how] += 1
            continue
        if app_helper.is_item_already_downloaded(it):
            match_stats["gecmis"] += 1
            continue
        download_queue.append(it)
    print(f"  (eşleşme: evrak no+tarih {match_stats['no']}, dosya no+gün {match_stats['gun']}, geçmiş {match_stats['gecmis']})")
    skipped_count = len(found_documents) - len(download_queue)
    app_helper.flush_history_if_dirty()
    print(f"  DİSKTE MEVCUT (ATLANDI)        : {skipped_count} adet")
    print(f"  İNDİRİLECEK YENİ EVRAK         : {len(download_queue)} adet")
    print("=" * 70 + "\n")

    if getattr(args, "dry_run", False):
        print("[i] --dry-run: hiçbir evrak indirilmedi. İndirilecek ilk 15 evrak:")
        for it in download_queue[:15]:
            print(f"    - {it['tarih']} | {it['birim_adi']} ({it['dosya_no']}) | {it['evrak_adi']} | no: {it.get('is_emir_no') or '-'}")
        return

    if not download_queue:
        print("[✓] Tebrikler! Hedef evrakların tamamı zaten diskte sağlam olarak mevcut.")
        save_ai_manifest(target_base, found_documents, download_queue)
        return

    min_d = 0.6
    max_d = 1.2
    batch_n = 30
    batch_pause = 6.0
    downloaded_now = 0
    max_retries = 5

    print(f"[*] Güvenli hızlı indirme başlatılıyor ({min_d}-{max_d} sn bekleme, her {batch_n} dosyada {batch_pause:.0f} sn mola)...")

    for idx, item in enumerate(download_queue, start=1):
        ukey = item["unique_key"]
        success = False

        for attempt in range(1, max_retries + 1):
            resp = bridge.download_document(item["download_params"])
            err_hdr = resp.get("errorHeader")
            status_code = resp.get("status", 0)
            ct = resp.get("contentType") or ""
            raw_bytes = base64.b64decode(resp.get("base64") or "") if resp.get("base64") else b""

            is_valid, reason = is_valid_document_bytes(raw_bytes, ct)
            need_relogin = (
                not resp.get("ok")
                or status_code in (401, 403, 302, 500)
                or bool(err_hdr)
                or not is_valid
            )

            if need_relogin:
                is_session_dead = (
                    not bridge.is_logged_in()
                    or "oturum" in reason.lower()
                    or "html" in reason.lower()
                    or "nosessionobject" in reason.lower()
                    or "prtl_gnl" in reason.lower()
                    or status_code in (401, 403, 302)
                    or "text/html" in ct.lower()
                )

                if is_session_dead:
                    print(f"[!] UYARI: Evrak alınamadı ({item['evrak_adi']}) - {reason} [Deneme {attempt}/{max_retries}]")
                    if attempt < max_retries:
                        # Kart takılıysa e-İmza, değilse oturum açılana kadar Mobil İmza
                        m_ok, m_msg = bridge.akilli_oturum_ac(
                            pin=DEFAULT_E_IMZA_PIN,
                            status_cb=print,
                            confirm_mobil=(lambda: ask_mobil_imza_onayi(mobil_imza_ayarlari()[1])) if (sys.stdin and sys.stdin.isatty()) else False,
                        )
                        if m_ok:
                            print(f"[✓] {m_msg}.")
                            refresh_dosya_ids_in_queue(bridge, download_queue, idx - 1)
                            continue
                        print(f"[x] Oturum yenilenemedi: {m_msg}")
                    time.sleep(3.0)
                    continue

                if bridge.is_logged_in() and "text/html" not in ct.lower():
                    print(f"[-] BİLGİ: {item['evrak_adi']} ({item['birim_adi']}) UYAP sunucusunda fiziksel dosya olarak mevcut değil (Ekli dosya yok). Atlandı.")
                    break

            if is_valid:
                cd = resp.get("contentDisposition") or ""
                cd_filename = ""
                m = re.search(r'filename\*?=["\']?(?:UTF-8\'\')?([^;"\']+)', cd, re.IGNORECASE)
                if m:
                    cd_filename = m.group(1).strip()
                ext = guess_extension(cd_filename, ct, raw_bytes)

                clean_ext = ext if ext.startswith(".") else f".{ext}"
                yargi_slug = infer_yargi_kategorisi(item["birim_adi"])
                b_slug = sanitize_path_part(item["birim_adi"], max_len=60)
                d_slug = sanitize_path_part(item["dosya_no"], max_len=40)
                alt_kat = infer_evrak_alt_kategori(item["evrak_adi"])
                clean_ev_id = str(item.get("evrak_id") or "").replace('"', '').replace("'", "").strip()
                doc_num = sanitize_path_part(item.get("is_emir_no") or clean_ev_id[:8], max_len=20)
                
                target_folder = target_base / yargi_slug / b_slug / d_slug / alt_kat
                ayni = app_helper.ayni_icerik_var(raw_bytes)
                if ayni:
                    # Aynı içerik başka bir evrak olarak zaten inmiş (ör. her dilekçeye eklenen vekaletname)
                    app_helper.history[ukey] = {"path": str(ayni), "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                                                "downloaded_at": dt.datetime.now().isoformat(timespec="seconds"),
                                                "size": len(raw_bytes), "tarih": item["tarih"], "birim_adi": item["birim_adi"],
                                                "dosya_no": item["dosya_no"], "evrak_turu": item["evrak_adi"],
                                                "is_emir_no": item.get("is_emir_no", ""), "mukerrer": True}
                    app_helper._history_dirty = True
                    print(f"[=] Mükerrer (aynı içerik zaten var, yazılmadı): {item['evrak_adi']} → {ayni.name}")
                    success = True
                    break
                tmp_path = target_folder / f"temp_{doc_num}{clean_ext}.part"
                safe_write_bytes(tmp_path, raw_bytes)

                meta = {}
                if clean_ext == ".udf":
                    try:
                        meta = extract_meta_from_udf(tmp_path)
                        meta["mahkeme"] = item.get("birim_adi") or meta.get("mahkeme", "")
                        meta["dosya_no"] = item.get("dosya_no") or meta.get("dosya_no", "")
                        meta["evrak_tarihi"] = item.get("tarih") or ""
                        meta["evrak_turu"] = item.get("evrak_adi") or item.get("evrak_turu", "")
                        meta["evrak_id"] = doc_num
                        update_udf_properties(tmp_path, meta)
                    except Exception:
                        pass

                file_name = build_enriched_filename(
                    tarih=item["tarih"],
                    birim=item["birim_adi"],
                    dosya_no=item["dosya_no"],
                    muvekkil=meta.get("muvekkil", ""),
                    evrak_turu=item["evrak_adi"],
                    karar_no=meta.get("karar_no", ""),
                    durusma_tarihi=meta.get("durusma_tarihi", ""),
                    celse_no=meta.get("celse_no", ""),
                    baglantili_dosya=meta.get("baglantili_dosya", ""),
                    muhatap=meta.get("muhatap", ""),
                    ptt_barkod=meta.get("ptt_barkod", ""),
                    teblig_sonuc=meta.get("teblig_sonuc", ""),
                    hukuki_teblig_tarihi=meta.get("hukuki_teblig_tarihi", ""),
                    is_uets=meta.get("is_uets", False),
                    evrak_id=doc_num,
                    ext=clean_ext
                )

                target_path = target_folder / file_name
                ext_tmp = win_extended_path(tmp_path)
                if os.path.exists(ext_tmp) and os.path.getsize(ext_tmp) == len(raw_bytes):
                    safe_replace_file(tmp_path, target_path)
                else:
                    safe_write_bytes(target_path, raw_bytes)
                    try:
                        os.unlink(ext_tmp)
                    except OSError:
                        pass

                auto_convert_udf_to_pdf(target_path)

                sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

                app_helper.history[ukey] = {
                    "path": str(target_path),
                    "sha256": sha256_hash,
                    "downloaded_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "size": len(raw_bytes),
                    "tarih": item["tarih"],
                    "dosya_turu": item["dosya_turu"],
                    "birim_adi": item["birim_adi"],
                    "dosya_no": item["dosya_no"],
                    "islem_turu": item["islem_turu"],
                    "evrak_turu": item["evrak_turu"],
                    "evrak_id": item["evrak_id"],
                    "is_emir_no": item.get("is_emir_no", ""),
                }
                app_helper._save_history()

                # Eğer evrak Tebligat veya UETS ise detaylı takip kütüğüne (CSV) işle
                is_teb_doc = any(k in tr_lower(item["evrak_adi"]) for k in ("tebligat", "tebliğ", "teblig", "mazbata", "uets"))
                if is_teb_doc or evrak_filter in ("tebligat", "tebligatlar", "mazbata"):
                    try:
                        from tebligat_yoneticisi import record_tebligat_to_csv, parse_tebligat_meta, extract_text_from_file
                        t_text = extract_text_from_file(target_path)
                        t_meta = parse_tebligat_meta(t_text, evrak_adi=item["evrak_adi"], evrak_tarihi=item["tarih"])
                        record_tebligat_to_csv({
                            "Gonderim_Tarihi": item["tarih"] or t_meta.get("gonderim_tarihi", ""),
                            "Tebligat_Turu": t_meta.get("tebligat_turu", "Fiziki PTT"),
                            "Birim_Adi": item["birim_adi"],
                            "Dosya_No": item["dosya_no"],
                            "Dosyadaki_Muvekkil": meta.get("muvekkil", ""),
                            "Muvekkil_Rolu": meta.get("muvekkil_rol", ""),
                            "Tebligat_Muhatabi": meta.get("muhatap") or t_meta.get("muhatap", ""),
                            "Muhatap_Rolu": t_meta.get("muhatap_rolu", ""),
                            "Barkod_Veya_Delil_No": meta.get("ptt_barkod") or t_meta.get("barkod_veya_delil_no", ""),
                            "Hukuki_Teblig_Tarihi": meta.get("hukuki_teblig_tarihi") or t_meta.get("hukuki_teblig_tarihi", ""),
                            "Teblig_Durumu_Sonuc": meta.get("teblig_sonuc") or t_meta.get("teblig_sonuc", ""),
                            "Yasal_Sure_Hesabi_Notu": t_meta.get("yasal_sure_notu", ""),
                            "Evrak_Adi": item["evrak_adi"],
                            "Evrak_Id": item.get("evrak_id", doc_num),
                            "Dosya_Yolu": str(target_path),
                            "Detayli_Icerik_Ozeti": t_meta.get("ozet_icerik", ""),
                        })
                    except Exception:
                        pass
                downloaded_now += 1
                success = True

                pct = (idx / len(download_queue)) * 100
                bar = ("█" * int(pct // 5)).ljust(20, "░")
                print(f"[{idx}/{len(download_queue)}] [{bar}] %{pct:.1f} Kaydedildi ({len(raw_bytes)//1024} KB): {item['birim_adi']} ({item['dosya_no']}) - {item['evrak_adi']}")
                break

        if not success:
            print(f"[x] HATA: {item['evrak_adi']} ({ukey}) indirilemedi, atlandı.")

        if idx < len(download_queue):
            if downloaded_now > 0 and downloaded_now % batch_n == 0:
                print(f"[*] UYAP koruma molası: {downloaded_now} dosya indirildi, {batch_pause:.0f} sn dinleniliyor...")
                time.sleep(batch_pause)
            else:
                time.sleep(random.uniform(min_d, max_d))

    # CSV İndeksi yaz
    try:
        csv_path = target_base / "indeks.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([
                "Durum", "Tarih", "Dosya Türü", "Birim Adı", "Dosya No",
                "İşlem Türü", "Evrak Türü", "Evrak ID", "Kaydedilen Dosya Yolu"
            ])
            for it in found_documents:
                uk = it["unique_key"]
                h = app_helper.history.get(uk, {})
                writer.writerow([
                    "İndirildi" if h else "Bekliyor",
                    it["tarih"],
                    it["dosya_turu"],
                    it["birim_adi"],
                    it["dosya_no"],
                    it["islem_turu"],
                    it["evrak_turu"],
                    it["evrak_id"],
                    h.get("path", ""),
                ])
        print(f"[✓] CSV İndeksi kaydedildi: {csv_path}")
    except Exception as e:
        print(f"[!] CSV kaydedilemedi: {e}")

    # Yapay Zeka (AI / LLM) Dava Analiz Manifestosu & Duruşma Kronolojisi üret
    save_ai_manifest(target_base, found_documents, download_queue)

    print("\n" + "=" * 70)
    print(f"  İNDİRME TAMAMLANDI! Bu oturumda {downloaded_now} dosya eksiksiz indirildi.")
    print(f"  Kayıt Konumu: {target_base}")
    print("=" * 70 + "\n")

    if evrak_filter == "tebligat":
        try:
            print("[*] Yeni indirilen tebligat ve mazbatalar analiz ediliyor (PTT Barkod, UETS Delil ID, TK m.7/a süre hesabı)...")
            from tebligat_yoneticisi import scan_and_sync_all_tebligats
            scan_and_sync_all_tebligats()
        except Exception as teb_err:
            print(f"[!] Tebligat takip tablosu senkronize edilirken hata: {teb_err}")


def run_cli_durusmalar_mode(args, bridge, app_helper, download_dir, tckn):
    """
    Duruşmaları sorgulayıp Google / Android Takvim için .ics dosyası üreten
    ve duruşma listesini CSV olarak kaydeden CLI fonksiyonu.
    """
    print("\n" + "=" * 70)
    print("  UYAP Avukat Portal - Duruşma Takvimi & Tutanak Yöneticisi")
    print("=" * 70 + "\n")

    today = dt.date.today()
    s_date = today - dt.timedelta(days=90)
    e_date = today + dt.timedelta(days=180)

    if getattr(args, "start_date", None):
        try:
            s_date = dt.datetime.strptime(args.start_date, "%d.%m.%Y").date()
        except Exception:
            pass
    if getattr(args, "end_date", None):
        try:
            e_date = dt.datetime.strptime(args.end_date, "%d.%m.%Y").date()
        except Exception:
            pass

    print(f"[*] Duruşma Tarama Aralığı: {s_date.strftime('%d.%m.%Y')} - {e_date.strftime('%d.%m.%Y')}")

    ranges = []
    cur = s_date
    while cur <= e_date:
        nxt = min(cur + dt.timedelta(days=29), e_date)
        ranges.append((cur, nxt))
        cur = nxt + dt.timedelta(days=1)

    print(f"[*] {len(ranges)} dilim halinde duruşmalar taranıyor...")
    all_durusmalar = []
    seen_ids = set()

    for idx, (s_d, e_d) in enumerate(ranges, start=1):
        s_str = s_d.strftime("%d.%m.%Y")
        e_str = e_d.strftime("%d.%m.%Y")
        try:
            res = bridge.query_durusmalar(s_str, e_str)
        except Exception:
            res = []
        c_count = 0
        for d in res:
            k_id = d.get("kayitId")
            if k_id and k_id not in seen_ids:
                seen_ids.add(k_id)
                all_durusmalar.append(d)
                c_count += 1
        print(f"  [{idx}/{len(ranges)}] {s_str} - {e_str} -> {c_count} duruşma bulundu.")
        if idx < len(ranges):
            time.sleep(random.uniform(0.3, 0.6))

    print(f"\n[✓] Toplam {len(all_durusmalar)} adet duruşma kaydı tespit edildi.")

    if not all_durusmalar:
        print("[i] Belirtilen tarih aralığında duruşma kaydı bulunamadı.")
        return

    # 1. iCalendar (.ics) Dosyası Üret
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//UYAP Avukat Portal//Duruşma Takvimi//TR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:UYAP Duruşmaları",
        "X-WR-TIMEZONE:Europe/Istanbul",
    ]

    for d in all_durusmalar:
        k_id = d.get("kayitId", random.randint(100000, 999999))
        ts_str = str(d.get("tarihSaat") or "").strip()
        yerel_birim = str(d.get("yerelBirimAd") or "Mahkeme").strip()
        dosya_no = str(d.get("dosyaNo") or "").strip()
        islem_tur = str(d.get("islemTuruAciklama") or "Duruşma").strip()
        islem_sonuc = str(d.get("islemSonucuAciklama") or "").strip()
        token = str(d.get("token") or "").strip()
        taraflar = d.get("dosyaTaraflari") or []
        taraf_str = ", ".join([f"{t.get('isim','')} {t.get('soyad','')} ({t.get('sifat','')})" for t in taraflar if isinstance(t, dict)])

        dt_start = None
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                dt_start = dt.datetime.strptime(ts_str, fmt)
                break
            except Exception:
                pass

        if not dt_start:
            continue

        dt_end = dt_start + dt.timedelta(minutes=30)
        dt_stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%SZ")
        dt_start_s = dt_start.strftime("%Y%m%dT%H%M%S")
        dt_end_s = dt_end.strftime("%Y%m%dT%H%M%S")

        desc = f"Dosya: {dosya_no}\\nMahkeme: {yerel_birim}\\nİşlem: {islem_tur} ({islem_sonuc})"
        if token:
            desc += f"\\ne-Duruşma Linki: {token}"
        if taraf_str:
            desc += f"\\nTaraflar: {taraf_str}"

        ics_lines.extend([
            "BEGIN:VEVENT",
            f"UID:durusma_{k_id}@uyap.gov.tr",
            f"DTSTAMP:{dt_stamp}",
            f"DTSTART;TZID=Europe/Istanbul:{dt_start_s}",
            f"DTEND;TZID=Europe/Istanbul:{dt_end_s}",
            f"SUMMARY:{islem_tur}: {yerel_birim} ({dosya_no})",
            f"DESCRIPTION:{desc}",
            f"LOCATION:{yerel_birim}",
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ])

    ics_lines.append("END:VCALENDAR")
    ics_path = download_dir / "durusma_takvimi.ics"
    ics_path.write_text("\r\n".join(ics_lines), encoding="utf-8")
    print(f"\n[✓] Duruşma Takvimi Oluşturuldu: {ics_path}")
    print("    (Bu dosyayı telefonunuzda açarak tüm duruşmaları Google Takvim / Telefon Takviminize tek tıkla ekleyebilirsiniz)\n")

    # 2. CSV Çıktısı ve Veritabanı Kaydı
    try:
        import evrak_katalog as ek
        kat = ek.Katalog()
        for d in all_durusmalar:
            dt_raw = str(d.get("tarihSaat") or "")
            tarih_part = dt_raw.split()[0] if " " in dt_raw else dt_raw
            saat_part = dt_raw.split()[1] if " " in dt_raw else ""
            kat.upsert_durusma({
                "birim": d.get("yerelBirimAd"),
                "dosya_no": d.get("dosyaNo"),
                "tarih": tarih_part,
                "saat": saat_part,
                "yer": d.get("yerelBirimAd"),
                "aciklama": f"{d.get('islemTuruAciklama', '')} - Sonuç: {d.get('islemSonucuAciklama', '')}",
            })
    except Exception:
        pass

    csv_path = download_dir / "durusma_listesi.csv"
    try:
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Tarih Saat", "Mahkeme / Birim", "Dosya No", "İşlem Türü", "Sonuç", "e-Duruşma Linki", "Taraflar"])
            for d in all_durusmalar:
                taraflar = d.get("dosyaTaraflari") or []
                taraf_str = ", ".join([f"{t.get('isim','')} {t.get('soyad','')} ({t.get('sifat','')})" for t in taraflar if isinstance(t, dict)])
                w.writerow([
                    d.get("tarihSaat"),
                    d.get("yerelBirimAd"),
                    d.get("dosyaNo"),
                    d.get("islemTuruAciklama"),
                    d.get("islemSonucuAciklama"),
                    d.get("token"),
                    taraf_str,
                ])
        print(f"[✓] Duruşma Tablosu CSV olarak kaydedildi: {csv_path}\n")
    except Exception:
        pass


def _ask(prompt: str) -> str | None:
    """input() sarmalayıcı: Ctrl+C / EOF durumunda None döner (traceback yok)."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def _ask_secret(prompt: str) -> str | None:
    """PIN gibi gizli girdileri ekrana yansıtmadan okur; hiçbir yere yazmaz."""
    import getpass
    try:
        return getpass.getpass(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def _tckn_of(user: dict | None) -> str:
    user = user or {}
    return str(user.get("tcKimlikNo") or user.get("tckn") or "")


def cli_ensure_session(args) -> tuple["UyapBrowserBridge", dict | None]:
    """CLI giriş akışı: tarayıcıyı hazırlar, oturum yoksa Mobil İmza / e-İmza / elle giriş
    seçeneklerini sunar. Kullanıcı vazgeçerse (bridge, None) döner. İstisna fırlatmaz."""
    bridge = UyapBrowserBridge(port=args.port)
    headless = bool(args.headless) or not bridge._detect_display()

    # 1. Tarayıcı + UYAP sekmesi
    while True:
        print(f"[*] Tarayıcı hazırlanıyor (Port {bridge.port})...")
        ok, msg = bridge.ensure_browser(headless=headless)
        if not ok and not headless and IS_TERMUX:
            # Termux:X11 açık değilse pencereli Chromium açılamaz: arka planda dene
            print(f"[!] {msg}\n[*] Termux:X11 kullanılamıyor; tarayıcı arka planda (headless) deneniyor...")
            headless = True
            ok, msg = bridge.ensure_browser(headless=True)
        if ok:
            print(f"[*] {msg}")
            ok, msg = bridge.ensure_ready("uyap")
            if ok:
                break
        print("\n" + "=" * 70)
        print(f"  [x] {msg}")
        print("=" * 70)
        print("  Tarayıcıyı elle başlatmak isterseniz:")
        print(bridge._manual_launch_hint())
        ans = _ask("\nTekrar denemek için Enter, menüye dönmek için 'q': ")
        if ans is None or ans.lower() in ("q", "0", "h", "cik", "çık"):
            return bridge, None

    # 2. Mevcut oturum
    print("[*] UYAP oturum durumu kontrol ediliyor...")
    info = bridge.check_login_and_user()
    if info.get("error"):
        print(f"[!] {info['error']}")
    user = info.get("user") or {}
    if _tckn_of(user):
        return bridge, user

    pin = args.pin or DEFAULT_E_IMZA_PIN

    # 3. Kayıtlı PIN (pin.txt / UYAP_E_IMZA_PIN / --pin) ile tek seferlik otomatik deneme
    if pin and not args.no_auto_relogin:
        ok_ark, _ = bridge.check_arksigner()
        if ok_ark:
            print("[*] Kayıtlı PIN ile e-İmza girişi deneniyor...")
            ok, msg = bridge.auto_relogin(pin=pin)
            print(f"[{'✓' if ok else 'x'}] {msg}")
            if ok:
                user = bridge.check_login_and_user().get("user") or {}
                if _tckn_of(user):
                    return bridge, user

    cfg = load_user_config()
    def_tc = getattr(args, "tc", "") or cfg.get("tc", "")
    def_gsm = getattr(args, "gsm", "") or cfg.get("gsm", "")
    def_op = getattr(args, "operator", "") or cfg.get("operator", "2")

    def do_mobil(tc_val, gsm_val, op_val) -> dict:
        ok, msg = bridge.login_with_mobil_imza(tc_val, gsm_val, op_val)
        print(f"[{'✓' if ok else 'x'}] {msg}")
        if ok:
            save_user_config({"tc": tc_val, "gsm": gsm_val, "operator": op_val})
            return bridge.check_login_and_user().get("user") or {}
        return {}

    # 4. Komut satırından Mobil İmza istendiyse doğrudan başlat
    if getattr(args, "mobil_imza", False) or (getattr(args, "tc", "") and getattr(args, "gsm", "")):
        if def_tc and def_gsm:
            user = do_mobil(def_tc, def_gsm, def_op)
            if _tckn_of(user):
                return bridge, user

    # 5. Giriş menüsü
    while True:
        print("\n" + "=" * 70)
        print("  [!] UYAP OTURUMU AÇIK DEĞİL - LÜTFEN BİR GİRİŞ YÖNTEMİ SEÇİN:")
        print("  1) Mobil İmza ile Giriş (telefonunuza onay gönderilir - Önerilen)")
        print("  2) e-İmza ile Giriş (ArkSigner / Adalet e-İmza Client)")
        print("  3) Tarayıcıda Kendim Giriş Yapacağım (girişi bekle)")
        print("  0) Vazgeç / Menüye Dön")
        print("=" * 70)
        choice = _ask("Seçiminiz (0-3) [Varsayılan: 1]: ")
        if choice is None or choice in ("0", "q"):
            print("[*] Giriş iptal edildi.")
            return bridge, None
        choice = choice or "1"

        if choice == "1":
            tc_val, gsm_val, op_val = def_tc, def_gsm, def_op
            if tc_val and gsm_val:
                ans = _ask(f"Kayıtlı Mobil İmza bilgileri kullanılsın mı? ({tc_val[:3]}*****{tc_val[-3:]} - {gsm_val}) [E/h]: ")
                if ans is None:
                    continue
                if ans.lower() in ("h", "hayir", "hayır", "n", "no"):
                    tc_val = gsm_val = ""
            if not (tc_val and gsm_val):
                tc_val = _ask("T.C. Kimlik No: ")
                gsm_val = _ask("GSM No (5xx..., başında 0 olmadan 10 hane): ") if tc_val is not None else None
                op_val = _ask(f"Operatör (1: Turkcell, 2: Türk Telekom, 3: Vodafone) [{def_op}]: ") if gsm_val is not None else None
                if tc_val is None or gsm_val is None or op_val is None:
                    continue
                op_val = op_val or def_op
            if not tc_val or not gsm_val:
                print("[!] T.C. Kimlik No ve GSM No zorunludur.")
                continue
            user = do_mobil(tc_val, gsm_val, op_val)

        elif choice == "2":
            ok_ark, msg_ark = bridge.check_arksigner()
            if not ok_ark:
                print(f"[x] {msg_ark}")
                continue
            hint = " (Enter = kayıtlı PIN)" if pin else ""
            pin_in = _ask_secret(f"e-İmza PIN Kodu (ekranda görünmez){hint}: ")
            if pin_in is None:
                continue
            pin_in = pin_in or pin
            if not pin_in:
                print("[!] PIN girilmedi.")
                continue
            print("[*] e-İmza ile giriş yapılıyor...")
            ok, msg = bridge.auto_relogin(pin=pin_in)
            print(f"[{'✓' if ok else 'x'}] {msg}")
            if ok:
                pin = pin_in  # yalnızca bu çalıştırmanın belleğinde (oturum düşerse yenilemek için)
                args.pin = pin_in
                user = bridge.check_login_and_user().get("user") or {}

        elif choice == "3":
            if bridge.is_headless:
                print("[!] Tarayıcı arka planda (headless) çalışıyor; elle giriş yapılamaz. Mobil İmza'yı (1) kullanın.")
                continue
            print("[*] Açılan tarayıcı penceresinde UYAP'a giriş yapın (Mobil İmza / e-İmza / e-Devlet).")
            print("    Giriş otomatik algılanacak. En fazla 5 dk beklenir; menüye dönmek için Ctrl+C.")
            deadline = time.time() + 300
            user = {}
            try:
                while time.time() < deadline:
                    info = bridge.check_login_and_user()
                    if info.get("error"):
                        print(f"[x] {info['error']}")
                        break
                    user = info.get("user") or {}
                    if _tckn_of(user):
                        break
                    time.sleep(3.0)
                else:
                    print("[!] 5 dk içinde giriş algılanmadı.")
            except KeyboardInterrupt:
                print("\n[*] Bekleme iptal edildi.")
        else:
            print("[!] Geçersiz seçim.")
            continue

        if _tckn_of(user):
            return bridge, user


def run_cli_mode(args):
    """
    Termux / Android / Konsol / Headless CLI Modu:
    Grafik ekran (X11) gerektirmeden doğrudan terminal üzerinden çalışır.
    """
    print("\n" + "=" * 70)
    print("  UYAP Avukat Portal - Güvenli Evrak İndirici (Terminal & CLI Modu)")
    print("=" * 70)

    # 1. İndirme dizini belirle
    if args.dir:
        download_dir = Path(args.dir)
    elif Path("/sdcard/Download").exists():
        download_dir = Path("/sdcard/Download/UYAP_Indirilenler")
    else:
        download_dir = DEFAULT_DOWNLOAD_DIR
    download_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] İndirme Klasörü: {download_dir}")

    # 2. Tarayıcı + UYAP oturumu (Mobil İmza / e-İmza / elle giriş) - tek yerden
    bridge, user = cli_ensure_session(args)
    if not user:
        print("[x] UYAP oturumu açılamadı.")
        return 1
    if getattr(args, "mode", "") == "login":
        ad = f"{user.get('adi', '')} {user.get('soyadi', '')}".strip() or "Avukat"
        print(f"✅ UYAP oturumu doğrulandı: Sayın {ad}")
        return 0
    tckn = _tckn_of(user)
    pin = args.pin or DEFAULT_E_IMZA_PIN
    auto_relogin = not args.no_auto_relogin

    full_name = f"{user.get('adi', '')} {user.get('soyadi', '')}".strip() or "Avukat"
    baro = user.get("baroAdi") or ""
    print(f"[✓] Giriş Başarılı: {full_name} (TCKN: {tckn} - {baro})")

    # 4. Geçmişi yükle ve doğrula
    app_helper = UyapDownloaderApp.__new__(UyapDownloaderApp)
    app_helper.disk_roots = [download_dir]
    app_helper.history = app_helper._verify_and_clean_history()
    print(f"[✓] Kayıtlı ve diskte doğrulanmış evrak sayısı: {len(app_helper.history)} adet")
    print(f"[✓] İndirme klasöründe numarasıyla tanınan evrak: {len(app_helper._disk_index())} adet (mükerrer kontrolü için)")

    # Mod Seçimi Kontrolü
    mode = getattr(args, "mode", "islemlerim")
    if mode == "dosyalar":
        return run_cli_dosyalar_mode(args, bridge, app_helper, download_dir, tckn)
    elif mode == "durusmalar":
        return run_cli_durusmalar_mode(args, bridge, app_helper, download_dir, tckn)

    # 5. Tarih aralığını belirle
    try:
        end_d = dt.datetime.strptime(args.end_date.strip(), "%d.%m.%Y").date() if args.end_date else dt.date.today()
    except ValueError:
        end_d = dt.date.today()
    try:
        start_d = dt.datetime.strptime(args.start_date.strip(), "%d.%m.%Y").date() if args.start_date else (end_d - dt.timedelta(days=365))
    except ValueError:
        start_d = end_d - dt.timedelta(days=365)

    print(f"[*] Tarama Aralığı: {start_d.strftime('%d.%m.%Y')} - {end_d.strftime('%d.%m.%Y')}")

    chunk_days = max(7, args.chunk_days)
    ranges = []
    cur = start_d
    while cur <= end_d:
        nxt = min(cur + dt.timedelta(days=chunk_days - 1), end_d)
        ranges.append((cur, nxt))
        cur = nxt + dt.timedelta(days=1)

    cache_file = BASE_DIR / "taranan_islem_cache.json"
    all_items = []
    seen_keys = set()
    use_cache = False

    if cache_file.exists():
        try:
            cdata = json.loads(cache_file.read_text(encoding="utf-8"))
            if (
                cdata.get("start_date") == start_d.strftime("%d.%m.%Y")
                and cdata.get("end_date") == end_d.strftime("%d.%m.%Y")
                and (time.time() - cdata.get("timestamp", 0)) < 43200
                and isinstance(cdata.get("items"), list)
                and len(cdata["items"]) > 0
            ):
                all_items = cdata["items"]
                for it in all_items:
                    if "tarih" in it and "tarih_obj" not in it:
                        try:
                            it["tarih_obj"] = dt.datetime.strptime(it["tarih"], "%Y-%m-%d")
                        except Exception:
                            it["tarih_obj"] = start_d
                print(f"[✓] Önbellekten {len(all_items)} adet işlem kaydı anında yüklendi (84 dilim tekrar taranmadan devam ediliyor).")
                use_cache = True
        except Exception:
            use_cache = False

    if use_cache:
        ranges = []
    else:
        print(f"[*] İşlemlerim {len(ranges)} dilim halinde taranıyor...")

    for idx, (s_d, e_d) in enumerate(ranges, start=1):
        s_str = s_d.strftime("%d.%m.%Y")
        e_str = e_d.strftime("%d.%m.%Y")

        slice_attempt = 0
        max_slice_attempts = 4
        while slice_attempt < max_slice_attempts:
            slice_attempt += 1
            try:
                resp = bridge.query_uyap_islemlerim(tckn, s_str, e_str, islem_turu=None)
            except Exception as e:
                resp = {"status": 500, "ok": False, "error": str(e), "rawText": str(e)}

            raw_text = str(resp.get("rawText", "")).lower()

            is_session_expired = (
                resp.get("status") in (401, 403)
                or "nosessionobject" in raw_text
                or "oturum bulunamadı" in raw_text
                or "oturum sonlandı" in raw_text
            )

            # Geçici bağlantı/timeout hatası durumunda oturumun gerçekten düşüp düşmediğini kontrol et
            if not resp.get("ok") and not is_session_expired:
                u_check = bridge.check_login_and_user()
                if not u_check.get("user", {}).get("tcKimlikNo"):
                    is_session_expired = True

            if is_session_expired:
                print(f"\n[!] UYARI: UYAP oturum süresi doldu (HTTP {resp.get('status', '401')}).")
                # Kart takılıysa e-İmza, değilse oturum açılana kadar Mobil İmza
                m_ok, m_msg = bridge.akilli_oturum_ac(
                    pin=pin if auto_relogin else "",
                    status_cb=print,
                    confirm_mobil=(lambda: ask_mobil_imza_onayi(mobil_imza_ayarlari()[1])) if (sys.stdin and sys.stdin.isatty()) else False,
                )
                if m_ok:
                    print(f"[✓] {m_msg}")
                    time.sleep(2.0)
                    u_info = bridge.check_login_and_user()
                    user = u_info.get("user") or {}
                    tckn = str(user.get("tcKimlikNo") or user.get("tckn") or tckn)
                    continue
                print(f"[x] Oturum yenilenemedi: {m_msg}")

                print("[!] Lütfen UYAP'a giriş yapınız, oturum bekleniyor...")
                while True:
                    time.sleep(3.0)
                    u_info = bridge.check_login_and_user()
                    if u_info.get("user", {}).get("tcKimlikNo"):
                        user = u_info["user"]
                        tckn = str(user.get("tcKimlikNo") or tckn)
                        print("[✓] Oturum algılandı. Taramaya devam ediliyor...")
                        break
                continue

            if not resp.get("ok"):
                err_msg = resp.get("error") or resp.get("rawText") or "Zaman aşımı / Sunucu yanıtı alınamadı"
                if slice_attempt < max_slice_attempts:
                    print(f"\n  [!] Dilim [{idx}/{len(ranges)}] geçici bağlantı/gecikme hatası ({err_msg[:60]}). 4 sn sonra tekrar deneniyor...")
                    time.sleep(4.0)
                    continue
                else:
                    print(f"\n  [x] Dilim [{idx}/{len(ranges)}] ({s_str} - {e_str}) yanıt vermedi, sonraki dilime geçiliyor.")
                    break

            break

        rows = resp.get("data")
        if isinstance(rows, dict):
            if rows.get("error") or rows.get("errorCode"):
                print(f"  [!] UYAP Uyarısı ({s_str} - {e_str}): {rows.get('error') or rows.get('errorCode')}")
            rows = rows.get("data") or rows.get("list") or []
        if not isinstance(rows, list):
            rows = []

        chunk_added = 0
        for r in rows:
            if not isinstance(r, dict):
                continue
            evrak_id = str(r.get("evrakId") or "").strip()
            gg_evrak_id = str(r.get("ggEvrakId") or "").strip()
            is_emir_no = str(r.get("isEmirNo") or "").strip()

            ukey = f"islem_{is_emir_no}" if is_emir_no else f"islem_{evrak_id}_{gg_evrak_id}"
            if ukey in seen_keys:
                continue
            seen_keys.add(ukey)

            parsed_date = (
                parse_uyap_date(r.get("isEmirTarihi"))
                or parse_uyap_date(r.get("birimEvrakTarihi"))
                or s_d
            )
            birim_adi = str(r.get("birimAdi") or "Belirtilmemis_Birim").strip()
            dosya_no = str(r.get("dosyaNo") or "DosyaNo_Yok").strip()
            evrak_adi = str(r.get("name") or r.get("evrakTuru") or "Evrak").strip()
            isin_durumu = str(r.get("isinDurumu") or "Tamamlandı").strip()

            item = {
                "unique_key": ukey,
                "kaynak": "Islemlerim",
                "tarih_obj": parsed_date,
                "tarih": parsed_date.strftime("%Y-%m-%d"),
                "yil": parsed_date.strftime("%Y"),
                "yil_ay": parsed_date.strftime("%Y-%m"),
                "dosya_turu": infer_dosya_turu(birim_adi),
                "birim_adi": birim_adi,
                "dosya_no": dosya_no,
                "dosya_id": str(r.get("dosyaId") or ""),
                "islem_turu": f"Gonderilen_Islem ({isin_durumu})",
                "evrak_turu": evrak_adi,
                "evrak_turu_kod": evrak_adi,
                "evrak_adi": evrak_adi,
                "evrak_id": evrak_id,
                "gg_evrak_id": gg_evrak_id,
                "is_emir_no": is_emir_no,
                "download_params": {
                    "evrakId": evrak_id,
                    "gelenGidenEvrakId": gg_evrak_id,
                },
                "can_download": bool(evrak_id),
            }
            all_items.append(item)
            chunk_added += 1

        print(f"  [{idx}/{len(ranges)}] {s_str} - {e_str} -> {len(rows)} kayıt ({chunk_added} yeni)")
        if idx < len(ranges):
            time.sleep(random.uniform(0.3, 0.6))

    if not use_cache and all_items:
        try:
            serializable_items = []
            for it in all_items:
                item_copy = dict(it)
                item_copy.pop("tarih_obj", None)
                serializable_items.append(item_copy)
            cache_file.write_text(
                json.dumps({
                    "start_date": start_d.strftime("%d.%m.%Y"),
                    "end_date": end_d.strftime("%d.%m.%Y"),
                    "timestamp": time.time(),
                    "items": serializable_items
                }, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass

    print(f"\n[✓] Toplam {len(all_items)} işlem/evrak kaydı hazır.")

    # 6. Mükerrerlik Filtresi: Diskte sağlam olanları atla
    download_queue = [
        it for it in all_items if it["can_download"] and not app_helper.is_item_already_downloaded(it)
    ]
    skipped_count = len(all_items) - len(download_queue)
    app_helper.flush_history_if_dirty()

    print("\n" + "=" * 70)
    print(f"  TOPLAM BULUNAN İŞLEM : {len(all_items)} adet")
    print(f"  DİSKTE MEVCUT (ATLANDI): {skipped_count} adet")
    print(f"  İNDİRİLECEK YENİ EVRAK: {len(download_queue)} adet")
    print("=" * 70 + "\n")

    if not download_queue:
        print("[✓] Tebrikler! Tüm evraklar zaten diskte sağlam ve eksiksiz mevcut. İndirilecek yeni evrak yok.")
        return

    # 7. Güvenli Hızlı İndirme Döngüsü
    min_d = 0.6
    max_d = 1.2
    batch_n = 30
    batch_pause = 6.0
    downloaded_now = 0
    max_retries = 5

    print(f"[*] Güvenli hızlı indirme başlatılıyor ({min_d}-{max_d} sn bekleme, her {batch_n} dosyada {batch_pause:.0f} sn mola)...")

    for idx, item in enumerate(download_queue, start=1):
        ukey = item["unique_key"]
        success = False

        for attempt in range(1, max_retries + 1):
            resp = bridge.download_document(item["download_params"])
            err_hdr = resp.get("errorHeader")
            status_code = resp.get("status", 0)
            ct = resp.get("contentType") or ""
            raw_bytes = base64.b64decode(resp.get("base64") or "") if resp.get("base64") else b""

            is_valid, reason = is_valid_document_bytes(raw_bytes, ct)
            need_relogin = (
                not resp.get("ok")
                or status_code in (401, 403, 302, 500)
                or bool(err_hdr)
                or not is_valid
            )

            if need_relogin:
                is_session_dead = (
                    not bridge.is_logged_in()
                    or "oturum" in reason.lower()
                    or "html" in reason.lower()
                    or "nosessionobject" in reason.lower()
                    or "prtl_gnl" in reason.lower()
                    or status_code in (401, 403, 302)
                    or "text/html" in ct.lower()
                )

                if not is_session_dead and bridge.is_logged_in() and "text/html" not in ct.lower():
                    # Oturum kesin açık ve dönen yanıt HTML değil, bu evrak UYAP sunucusunda fiziken yok
                    print(f"[-] BİLGİ: {item['evrak_adi']} ({item['birim_adi']}) UYAP sunucusunda fiziksel dosya olarak mevcut değil (Ekli dosya yok). Atlandı.")
                    break

                # Oturum gerçekten düşmüşse yeniden giriş yap:
                print(f"[!] UYARI: UYAP oturumu sonlanmış ({reason}). Yeniden bağlanılıyor... [Deneme {attempt}/{max_retries}]")
                if attempt < max_retries:
                    # Kart takılıysa e-İmza, değilse oturum açılana kadar Mobil İmza
                    re_ok, re_msg = bridge.akilli_oturum_ac(
                        pin=pin if auto_relogin else "",
                        status_cb=print,
                        confirm_mobil=(lambda: ask_mobil_imza_onayi(mobil_imza_ayarlari()[1])) if (sys.stdin and sys.stdin.isatty()) else False,
                    )
                    if re_ok:
                        print(f"[✓] {re_msg}. Evrak tekrar deneniyor...")
                        time.sleep(2.0)
                        continue
                    print(f"[x] Oturum yenilenemedi: {re_msg}")
                    time.sleep(3.0)
                    continue

            if is_valid:
                cd = resp.get("contentDisposition") or ""
                cd_filename = ""
                m = re.search(r'filename\*?=["\']?(?:UTF-8\'\')?([^;"\']+)', cd, re.IGNORECASE)
                if m:
                    cd_filename = m.group(1).strip()

                ext = guess_extension(cd_filename, ct, raw_bytes)

                ayni = app_helper.ayni_icerik_var(raw_bytes)
                if ayni:
                    app_helper.history[ukey] = {"path": str(ayni), "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                                                "downloaded_at": dt.datetime.now().isoformat(timespec="seconds"),
                                                "size": len(raw_bytes), "tarih": item["tarih"], "birim_adi": item["birim_adi"],
                                                "dosya_no": item["dosya_no"], "evrak_turu": item["evrak_turu"],
                                                "is_emir_no": item.get("is_emir_no", ""), "mukerrer": True}
                    app_helper._history_dirty = True
                    print(f"[=] Mükerrer (aynı içerik zaten var, yazılmadı): {item['evrak_adi']} → {ayni.name}")
                    success = True
                    break

                target_path = app_helper.build_target_filepath(item, ext, override_dir=download_dir)

                tmp_path = target_path.with_suffix(target_path.suffix + ".part")
                safe_write_bytes(tmp_path, raw_bytes)

                ext_tmp = win_extended_path(tmp_path)
                if os.path.exists(ext_tmp) and os.path.getsize(ext_tmp) == len(raw_bytes):
                    safe_replace_file(tmp_path, target_path)
                else:
                    safe_write_bytes(target_path, raw_bytes)
                    try:
                        os.unlink(ext_tmp)
                    except OSError:
                        pass

                auto_convert_udf_to_pdf(target_path)

                sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

                app_helper.history[ukey] = {
                    "path": str(target_path),
                    "sha256": sha256_hash,
                    "downloaded_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "size": len(raw_bytes),
                    "tarih": item["tarih"],
                    "dosya_turu": item["dosya_turu"],
                    "birim_adi": item["birim_adi"],
                    "dosya_no": item["dosya_no"],
                    "islem_turu": item["islem_turu"],
                    "evrak_turu": item["evrak_turu"],
                    "evrak_id": item["evrak_id"],
                    "is_emir_no": item.get("is_emir_no", ""),
                }
                app_helper._save_history()
                downloaded_now += 1
                success = True

                pct = (idx / len(download_queue)) * 100
                bar = ("█" * int(pct // 5)).ljust(20, "░")
                print(f"[{idx}/{len(download_queue)}] [{bar}] %{pct:.1f} Kaydedildi ({len(raw_bytes)//1024} KB): {item['birim_adi']} ({item['dosya_no']}) - {item['evrak_adi']}")
                break

        if not success:
            print(f"[x] HATA: {item['evrak_adi']} ({ukey}) indirilemedi, atlandı.")

        if idx < len(download_queue):
            if downloaded_now > 0 and downloaded_now % batch_n == 0:
                print(f"[*] UYAP koruma molası: {downloaded_now} dosya indirildi, {batch_pause:.0f} sn dinleniliyor...")
                time.sleep(batch_pause)
            else:
                time.sleep(random.uniform(min_d, max_d))

    # CSV İndeksi yaz
    try:
        csv_path = download_dir / "indirme_indeksi.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([
                "Durum", "Tarih", "Dosya Türü", "Birim Adı", "Dosya No",
                "İşlem Türü", "Evrak Türü", "Evrak ID", "Kaydedilen Dosya Yolu"
            ])
            for it in all_items:
                ukey = it["unique_key"]
                h = app_helper.history.get(ukey, {})
                writer.writerow([
                    "İndirildi" if h else "Bekliyor",
                    it["tarih"],
                    it["dosya_turu"],
                    it["birim_adi"],
                    it["dosya_no"],
                    it["islem_turu"],
                    it["evrak_turu"],
                    it["evrak_id"],
                    h.get("path", ""),
                ])
        print(f"[✓] CSV İndeksi kaydedildi: {csv_path}")
    except Exception as e:
        print(f"[!] CSV kaydedilemedi: {e}")

    print("\n" + "=" * 70)
    print(f"  İNDİRME TAMAMLANDI! Bu oturumda {downloaded_now} dosya eksiksiz indirildi.")
    print(f"  Kayıt Konumu: {download_dir}")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="UYAP Avukat Portal Güvenli Toplu Evrak İndirici")
    parser.add_argument("--cli", "-c", action="store_true", help="Grafik arayüz (Tkinter) yerine Terminal / CLI modunda çalıştır")
    parser.add_argument("--headless", action="store_true", help="Chromium'u arkaplanda (penceresiz / headless) çalıştır")
    parser.add_argument("--port", type=int, default=CDP_PORT, help="Chromium CDP portu (varsayılan: 9223)")
    parser.add_argument("--pin", type=str, default="", help="e-İmza PIN kodu (varsayılan: pin.txt veya boş)")
    parser.add_argument("--start-date", type=str, default="", help="Başlangıç tarihi (GG.AA.YYYY)")
    parser.add_argument("--end-date", type=str, default="", help="Bitiş tarihi (GG.AA.YYYY)")
    parser.add_argument("--chunk-days", type=int, default=30, help="Sorgu dilim aralığı (gün)")
    parser.add_argument("--dir", type=str, default="", help="İndirme klasörü")
    parser.add_argument("--no-auto-relogin", action="store_true", help="Otomatik e-imza girişini devre dışı bırak")
    parser.add_argument("--tc", type=str, default="", help="Mobil İmza için T.C. Kimlik Numarası")
    parser.add_argument("--gsm", type=str, default="", help="Mobil İmza için GSM Numarası (başında sıfır olmadan 10 hane)")
    parser.add_argument("--operator", type=str, default="", choices=["", "turktelekom", "turkcell", "vodafone", "1", "2", "3"], help="Mobil İmza operatörü (turktelekom, turkcell, vodafone)")
    parser.add_argument("--mobil-imza", action="store_true", help="Oturum yoksa doğrudan Mobil İmza akışını başlat")
    # v4.9.3: "login" modu eklendi — Görevler'deki "UYAP oturum aç (e-imza)" bu modu çağırıyordu ama argparse
    # tanımıyordu ("invalid choice: 'login'", kod 2). Yalnızca oturumu açar/doğrular ve çıkar, indirme yapmaz.
    parser.add_argument("--mode", type=str, default="islemlerim", choices=["islemlerim", "dosyalar", "durusmalar", "login"], help="Çalışma modu: islemlerim, dosyalar (dava dosyası evrakları), durusmalar (duruşma takvimi), login (yalnız oturum aç)")
    parser.add_argument("--evrak-turu", type=str, default="", help="Dava dosyalarından indirilecek evrak türü (durusma, bilirkisi, karar, tensip, dilekce, iddianame, kesinlesme, tumu veya serbest metin)")
    parser.add_argument("--include-attachments", action="store_true", help="Evrakların ek belgelerini de indir")
    parser.add_argument("--scope", type=str, default="all", choices=["all", "acik", "fav"], help="Taranacak dosya kapsamı: all (Açık + Kapalı - 700+ Dosya), acik (Yalnızca Açık), fav (Sık Kullanılanlar)")
    parser.add_argument("--include-closed", action="store_true", default=True, help="Kapalı/Karara Çıkmış dosyaları da dahil et (varsayılan: True)")
    parser.add_argument("--no-closed", dest="include_closed", action="store_false", help="Kapalı dosyaları tarama dışı bırak")
    parser.add_argument("--filter-birim", type=str, default="", help="Yalnızca birim adı veya dosya no bu kelimeyi içeren dosyaları tara (örn: erzurum, 2025/506)")
    parser.add_argument("--days", type=int, default=0, help="Geriye dönük taranacak gün sayısı (örn: 5, 7, 14, 30, 60, 90)")
    parser.add_argument("--yargi-turu", type=str, default="", choices=["", "all", "tumu", "hukuk", "ceza", "idari", "icra"], help="Taranacak dosya/yargı türü: hukuk, ceza, idari, icra (boş bırakılırsa tümü)")

    parser.add_argument("--dry-run", action="store_true", help="Tara ve mükerrer kontrolü yap, hiçbir şey indirme (dava dosyası modları)")
    parser.add_argument("--browser-only",action="store_true", help="Sadece UYAP tarayıcısını (CDP portu açık, ayrı profil) başlat ve çık")
    parser.add_argument("--katalog", action="store_true", help="Evrak kataloğu arayüzü: tüm evrakları tara, filtrele, seçip bir kez indir")
    parser.add_argument("--watcher", action="store_true", help="Kataloğu nöbetçi bot modu ile başlatır")
    parser.add_argument("--katalog-tara", action="store_true", help="Kataloğu terminalden güncelle (indirme yapmaz; sunucu/zamanlanmış görev için)")

    args = parser.parse_args()

    if args.katalog:
        import katalog_gui
        katalog_gui.main(watcher_mode=args.watcher)
        return

    if args.katalog_tara:
        import evrak_katalog
        try:
            bridge, user = cli_ensure_session(args)
            if not user:
                sys.exit(1)
            motor = evrak_katalog.Motor(bridge, evrak_katalog.Katalog(),
                                        Path(args.dir) if args.dir else DEFAULT_DOWNLOAD_DIR,
                                        progress=lambda d, t, s="": print(f"\r  {d}/{t} {s}".ljust(70), end="", flush=True))
            motor.relogin = lambda: bool(cli_ensure_session(args)[1])
            motor.scan(include_closed=args.include_closed)
            print()
        except KeyboardInterrupt:
            print("\n[*] Durduruldu.")
            sys.exit(130)
        except UyapBrowserError as e:
            print(f"\n[x] {e}")
            sys.exit(2)
        sys.exit(0)

    if args.browser_only:
        b = UyapBrowserBridge(port=args.port)
        ok, msg = b.ensure_browser(headless=args.headless)
        if ok:
            ok, msg2 = b.ensure_ready("uyap")
            msg = f"{msg} {msg2}"
        print(f"[{'✓' if ok else 'x'}] {msg}")
        if not ok:
            print("  Elle başlatmak için:\n" + b._manual_launch_hint())
        sys.exit(0 if ok else 2)

    if args.days > 0 and not args.start_date:
        args.start_date = (dt.date.today() - dt.timedelta(days=args.days)).strftime("%d.%m.%Y")

    has_display = sys.platform == "win32" or bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    if args.cli or not has_display or not HAS_TKINTER:
        if not HAS_TKINTER and not args.cli:
            print("[i] Bilgi: Tkinter grafik modülü bulunamadı, otomatik olarak Terminal / CLI modunda başlatılıyor.")
        elif not has_display and not args.cli:
            print("[i] Bilgi: Ekran (DISPLAY/X11) bulunamadı, otomatik olarak Terminal / CLI modunda başlatılıyor.")
        try:
            rc = run_cli_mode(args)
        except KeyboardInterrupt:
            print("\n[*] İşlem kullanıcı tarafından durduruldu (Ctrl+C). İndirilenler kaydedildi; tekrar çalıştırınca kaldığı yerden devam eder.")
            sys.exit(130)
        except UyapBrowserError as e:
            print(f"\n[x] {e}")
            sys.exit(2)
        except Exception as e:
            import traceback
            file_logger.error("Beklenmeyen hata:\n" + traceback.format_exc())
            print(f"\n[x] Beklenmeyen hata: {e}")
            print(f"    Ayrıntılar log dosyasına yazıldı: {LOG_FILE}")
            sys.exit(1)
        sys.exit(rc if isinstance(rc, int) else 0)
    else:
        root = tk.Tk()
        app = UyapDownloaderApp(root)
        root.mainloop()


if __name__ == "__main__":
    main()
