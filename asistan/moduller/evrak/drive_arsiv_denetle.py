#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Drive & UYAP Arşiv Kapsamlı Denetim ve Raporlama Motoru
=============================================================
Arşivdeki tüm evrakları inceler:
  1. Formatlama ve Adlandırma standartları kontrolü
  2. Mükerrer (Duplicate) dosya tespiti (SHA-256 ve evrak ID bazlı)
  3. Bozuk dosya tespiti (0 bayt, sahte HTML, geçersiz PDF/UDF)
  4. Google Drive yükleme durumu analizi
  5. Tüm sonuçları CSV ve JSON formatında dışa aktarma
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
import zipfile
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "uyap_katalog.db"
LOCAL_ARCHIVE_DIR = BASE_DIR / r"G:\Drive'ım\UYAP_Arsiv"
SDCARD_ARCHIVE_DIR = Path("/sdcard/Download/UYAP_Indirilenler")
INDEX_JSON_PATH = SDCARD_ARCHIVE_DIR / "arsiv_indeksi.json"
if not INDEX_JSON_PATH.exists():
    INDEX_JSON_PATH = BASE_DIR / "arsiv_indeksi.json"

REPORT_JSON = BASE_DIR / "drive_durum_raporu.json"
REPORT_CSV_MEVCUT = BASE_DIR / "arsiv_mevcut_dosyalar.csv"
REPORT_CSV_EKSIK = BASE_DIR / "arsiv_eksik_dosyalar.csv"
REPORT_CSV_SORUNLU = BASE_DIR / "arsiv_sorunlu_dosyalar.csv"


def sha256_file(path: Path) -> str:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def validate_file_content(path: Path) -> tuple[bool, str]:
    """Dosyanın gerçek içeriğini kontrol eder (boşluk, HTML hata sayfası, geçerli PDF/UDF)."""
    try:
        if not path.exists():
            return False, "DOSYA_YOK"
        sz = path.stat().st_size
        if sz == 0:
            return False, "SIFIR_BAYT"
        
        with open(path, "rb") as f:
            header = f.read(512)
        
        # HTML hata sayfası kontrolü
        lower_header = header.lower()
        if b"<!doctype html" in lower_header or b"<html" in lower_header or "giriş yap".encode("utf-8") in lower_header:
            return False, "HTML_HATA_SAYFASI"
        
        ext = path.suffix.lower()
        if ext == ".pdf":
            if not header.startswith(b"%PDF-"):
                return False, "GECERSIZ_PDF_BASLIGI"
            return True, "OK_PDF"
        elif ext == ".udf":
            if not header.startswith(b"PK"):
                return False, "GECERSIZ_UDF_ZIP"
            # Zip geçerliliği
            try:
                with zipfile.ZipFile(path, "r") as zf:
                    if "content.xml" not in zf.namelist():
                        return False, "UDF_CONTENT_XML_EKSIK"
            except Exception as e:
                return False, f"BOZUK_ZIP_{e}"
            return True, "OK_UDF"
        elif ext in [".tiff", ".tif", ".jpg", ".png"]:
            return True, "OK_IMAGE"
        else:
            return True, f"OK_{ext}"
    except Exception as e:
        return False, f"OKUMA_HATASI_{e}"


def check_naming_convention(filename: str) -> tuple[bool, str]:
    """Dosya adının standart YYYY-AA-GG formatına ve temiz karakter yapısına uyup uymadığını denetler."""
    # Standart: 202X-XX-XX_Tür_Açıklama.ext
    has_date_prefix = bool(re.match(r"^\d{4}-\d{2}-\d{2}_", filename))
    has_dirty_chars = bool(re.search(r"[@+%$#*?\"<>|]", filename))
    
    if not has_date_prefix and has_dirty_chars:
        return False, "TARIHSIZ_VE_GECERSIZ_KARAKTER"
    if not has_date_prefix:
        return False, "TARIH_ON_EKI_YOK"
    if has_dirty_chars:
        return False, "UYGUNSUZ_KARAKTER_ICERIR"
    return True, "STANDART_UYGUN"


def denetle():
    print("=" * 65)
    print("  GOOGLE DRIVE & UYAP ARŞİV KAPSAMLI DENETİM BAŞLATILDI")
    print("=" * 65)

    # 1. Drive İndeksini Yükle
    drive_index = {}
    if INDEX_JSON_PATH.exists():
        try:
            drive_index = json.loads(INDEX_JSON_PATH.read_text(encoding="utf-8"))
            print(f"[*] Google Drive Senkronizasyon İndeksi Yüklendi: {len(drive_index)} evrak kayıtlı.")
        except Exception as e:
            print(f"[!] İndeks JSON okunamadı: {e}")

    # 2. Yerel Fiziksel Dosyaları Tara
    scan_dirs = []
    if SDCARD_ARCHIVE_DIR.exists():
        scan_dirs.append(SDCARD_ARCHIVE_DIR)
    if LOCAL_ARCHIVE_DIR.exists():
        scan_dirs.append(LOCAL_ARCHIVE_DIR)

    physical_files = []
    for sdir in scan_dirs:
        for root, _, files in os.walk(sdir):
            for fn in files:
                if fn.endswith((".json", ".csv", ".log", ".ics")):
                    continue
                p = Path(root) / fn
                physical_files.append(p)

    print(f"[*] Taranan Fiziksel Evrak Sayısı: {len(physical_files)} adet.")

    # 3. Dosyaları Analiz Et: Bozukluk, Formatlama, Mükerrerlik
    sha_map = {}
    mevcut_listesi = []
    sorunlu_listesi = []

    for p in physical_files:
        sz = p.stat().st_size
        sha = sha256_file(p)
        is_valid, reason = validate_file_content(p)
        name_ok, name_reason = check_naming_convention(p.name)

        is_dup = False
        dup_target = ""
        if sha:
            if sha in sha_map:
                is_dup = True
                dup_target = str(sha_map[sha])
            else:
                sha_map[sha] = p

        rec = {
            "dosya_adi": p.name,
            "yol": str(p),
            "boyut_bayt": sz,
            "boyut_kb": round(sz / 1024, 2),
            "uzanti": p.suffix.lower(),
            "sha256": sha,
            "icerik_gecerli": is_valid,
            "durum_detay": reason,
            "adlandirma_uygun": name_ok,
            "adlandirma_detay": name_reason,
            "mukerrer": is_dup,
            "mukerrer_kaynak": dup_target,
            "degistirilme_tarihi": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        }

        if not is_valid or not name_ok or is_dup:
            sorunlu_listesi.append(rec)
        mevcut_listesi.append(rec)

    # Yerel dosya token seti oluştur
    local_tokens = set()
    for x in mevcut_listesi:
        local_tokens.add(x["dosya_adi"])
        for tok in re.findall(r'[a-zA-Z0-9_-]{4,}', x["dosya_adi"]):
            local_tokens.add(tok)

    # 4. UYAP Kataloğu (uyap_katalog.db) ile Karşılaştırma
    katalog_evrak_sayisi = 0
    katalog_dosya_sayisi = 0
    eksik_evraklar = []

    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            katalog_dosya_sayisi = cur.execute("SELECT count(*) FROM dosya").fetchone()[0]
            katalog_evrak_sayisi = cur.execute("SELECT count(*) FROM evrak").fetchone()[0]

            rows = cur.execute("""
                SELECT id, dkey, tur, aciklama, tarih, gercek_id, evrak_id, uzanti, path, pdf_path
                FROM evrak
                ORDER BY tarih DESC
            """).fetchall()

            for r in rows:
                eid = r[0]
                dkey = r[1] or ""
                tur = r[2] or ""
                aciklama = r[3] or ""
                tarih = r[4] or ""
                gercek_id = str(r[5] or "")
                evrak_uuid = str(r[6] or "")
                uzanti = r[7] or ""
                path = r[8] or ""
                pdf_path = r[9] or ""

                # Drive veya yerel arşivde var mı?
                in_drive = (evrak_uuid in drive_index) or (gercek_id in drive_index) or (str(eid) in drive_index)
                in_local = False
                if (path and Path(path).exists()) or (pdf_path and Path(pdf_path).exists()):
                    in_local = True
                elif (evrak_uuid and evrak_uuid in local_tokens) or (gercek_id and gercek_id in local_tokens):
                    in_local = True

                if not in_drive and not in_local:
                    eksik_evraklar.append({
                        "id": eid,
                        "dkey": dkey,
                        "tarih": tarih,
                        "tur": tur,
                        "aciklama": aciklama,
                        "gercek_id": gercek_id,
                        "evrak_id": evrak_uuid,
                        "uzanti": uzanti
                    })
            conn.close()
        except Exception as e:
            print(f"[!] Veritabanı okuma hatası: {e}")

    # 5. Özet Rapor Oluştur
    toplam_fiziksel = len(mevcut_listesi)
    toplam_bozuk = sum(1 for x in mevcut_listesi if not x["icerik_gecerli"])
    toplam_mukerrer = sum(1 for x in mevcut_listesi if x["mukerrer"])
    toplam_adlandirma_hatasi = sum(1 for x in mevcut_listesi if not x["adlandirma_uygun"])
    toplam_drive_yuklu = len(drive_index)

    ozet = {
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "katalog_toplam_dosya_sayisi": katalog_dosya_sayisi,
        "katalog_toplam_evrak_sayisi": katalog_evrak_sayisi,
        "fiziksel_mevcut_dosya_sayisi": toplam_fiziksel,
        "google_drive_yuklu_evrak_sayisi": toplam_drive_yuklu,
        "eksik_indirilecek_evrak_sayisi": len(eksik_evraklar),
        "bozuk_dosya_sayisi": toplam_bozuk,
        "mukerrer_dosya_sayisi": toplam_mukerrer,
        "adlandirma_uygunsuz_dosya_sayisi": toplam_adlandirma_hatasi,
        "durum": "SAGLIKLI" if (toplam_bozuk == 0 and toplam_mukerrer == 0) else "INCELEME_GEREKIR"
    }

    # 6. JSON ve CSV Dosyalarına Kaydet
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump({"ozet": ozet, "sorunlu_dosyalar": sorunlu_listesi[:200]}, f, ensure_ascii=False, indent=2)

    # CSV 1: Mevcut Dosyalar
    if mevcut_listesi:
        with open(REPORT_CSV_MEVCUT, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(mevcut_listesi[0].keys()))
            writer.writeheader()
            writer.writerows(mevcut_listesi)

    # CSV 2: Sorunlu Dosyalar
    if sorunlu_listesi:
        with open(REPORT_CSV_SORUNLU, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(sorunlu_listesi[0].keys()))
            writer.writeheader()
            writer.writerows(sorunlu_listesi)

    # CSV 3: Eksik Dosyalar (İlk 1000 kayıt)
    if eksik_evraklar:
        with open(REPORT_CSV_EKSIK, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(eksik_evraklar[0].keys()))
            writer.writeheader()
            writer.writerows(eksik_evraklar[:5000])

    print("-" * 65)
    print("  DENETİM SONUÇLARI ÖZETİ:")
    print(f"  • Katalogdaki Toplam Dava/İşlem Dosyası : {katalog_dosya_sayisi:,}")
    print(f"  • Katalogdaki Toplam Evrak Kaydı       : {katalog_evrak_sayisi:,}")
    print(f"  • Yerelde Taranan Fiziksel Dosya       : {toplam_fiziksel:,}")
    print(f"  • Google Drive'da Yüklü Evrak          : {toplam_drive_yuklu:,}")
    print(f"  • Bozuk (0 Byte / Hatalı İçerik)        : {toplam_bozuk}")
    print(f"  • Mükerrer (Duplicate SHA-256)         : {toplam_mukerrer}")
    print(f"  • Adlandırma Standardına Uymayan       : {toplam_adlandirma_hatasi}")
    print(f"  • Eksik / Henüz İndirilmemiş Evrak    : {len(eksik_evraklar):,}")
    print("-" * 65)
    print(f"[✓] Rapor JSON  : {REPORT_JSON}")
    print(f"[✓] Mevcut CSV  : {REPORT_CSV_MEVCUT}")
    print(f"[✓] Sorunlu CSV : {REPORT_CSV_SORUNLU}")
    print(f"[✓] Eksik CSV   : {REPORT_CSV_EKSIK}")
    print("=" * 65)

    return ozet, eksik_evraklar


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Google Drive & UYAP Arşiv Kapsamlı Denetim ve Raporlama Motoru")
    parser.add_argument("--ozet", action="store_true", help="Mevcut denetim raporunun özetini anında gösterir")
    args = parser.parse_args()

    if args.ozet and REPORT_JSON.exists():
        try:
            with open(REPORT_JSON, "r", encoding="utf-8") as f:
                rep = json.load(f)
            oz = rep.get("ozet", {})
            print("=" * 65)
            print("  MEVCUT ARŞİV VE GOOGLE DRIVE DENETİM RAPORU ÖZETİ")
            print("=" * 65)
            print(f"  • Rapor Tarihi                          : {oz.get('tarih', '-')}")
            print(f"  • Katalogdaki Toplam Dava/İşlem Dosyası : {oz.get('katalog_toplam_dosya_sayisi', 0):,}")
            print(f"  • Katalogdaki Toplam Evrak Kaydı       : {oz.get('katalog_toplam_evrak_sayisi', 0):,}")
            print(f"  • Yerelde Taranan Fiziksel Dosya       : {oz.get('fiziksel_mevcut_dosya_sayisi', 0):,}")
            print(f"  • Google Drive'da Yüklü Evrak          : {oz.get('google_drive_yuklu_evrak_sayisi', 0):,}")
            print(f"  • Bozuk (0 Byte / Hatalı İçerik)        : {oz.get('bozuk_dosya_sayisi', 0)}")
            print(f"  • Mükerrer (Duplicate SHA-256)         : {oz.get('mukerrer_dosya_sayisi', 0)}")
            print(f"  • Adlandırma Standardına Uymayan       : {oz.get('adlandirma_uygunsuz_dosya_sayisi', 0)}")
            print(f"  • Eksik / Henüz İndirilmemiş Evrak    : {oz.get('eksik_indirilecek_evrak_sayisi', 0):,}")
            print("=" * 65)
            print(f"[✓] Rapor JSON  : {REPORT_JSON}")
            print(f"[✓] Mevcut CSV  : {REPORT_CSV_MEVCUT}")
            print(f"[✓] Sorunlu CSV : {REPORT_CSV_SORUNLU}")
            print(f"[✓] Eksik CSV   : {REPORT_CSV_EKSIK}")
            sys.exit(0)
        except Exception:
            pass

    denetle()
