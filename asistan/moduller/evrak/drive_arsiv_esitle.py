#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UYAP Google Drive Akıllı ve Tam Eşitleyici (Full Autonomous Sync Engine)
========================================================================
Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.

Özellikler:
  1. Kademeli Zaman Akışı (--asama kademeli):
     - Aşama 1: Son 1 Gün
     - Aşama 2: Son 1 Hafta (7 gün)
     - Aşama 3: Son 1 Ay (30 gün)
     - Aşama 4: Son 2 Ay (60 gün)
     - Aşama 5: Geri kalan tüm arşiv
  2. Hibrit Senkronizasyon:
     - Yerelde (/sdcard/Download/UYAP_Indirilenler) mevcut olan dosyalar doğrudan Drive'a yüklenir.
     - Ne yerelde ne Drive'da olan evraklar UYAP Avukat Portalından arka planda indirilip,
       PDF'e çevrilerek Drive'a yüklenir.
  3. Akıllı Filtreleme:
     - 'baydar', 'casmoni', 'emre oral', 'turan solmaz' dava ve evrakları otomatik atlanır.
  4. Arka Plan (Daemon) Yönetimi:
     - --daemon / --start : Arka planda kesintisiz çalıştırır.
     - --status           : Çalışma durumunu ve ilerlemeyi gösterir.
     - --stop             : Arka plan servisini güvenle durdurur.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import requests

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

DB_PATH = BASE_DIR / "uyap_katalog.db"
SDCARD_ARCHIVE_DIR = Path("/sdcard/Download/UYAP_Indirilenler")
INDEX_JSON_PATH = SDCARD_ARCHIVE_DIR / "arsiv_indeksi.json"
if not SDCARD_ARCHIVE_DIR.exists():
    INDEX_JSON_PATH = BASE_DIR / "arsiv_indeksi.json"

PID_FILE = BASE_DIR / "drive_esitle.pid"
STATUS_FILE = BASE_DIR / "drive_esitle_status.json"
LOG_FILE = BASE_DIR / "drive_esitle.log"

try:  # v4.10.0: kişisel değerler koda yazılmaz (bkz. asistan/kisisel_ayar.py)
    import kisisel_ayar as _ka
except ImportError:
    import sys as _sys_ka
    for _p in (Path(__file__).resolve().parents[2], Path(__file__).resolve().parents[1] / "asistan"):
        if (_p / "kisisel_ayar.py").is_file():
            _sys_ka.path.insert(0, str(_p))
            break
    import kisisel_ayar as _ka
DEFAULT_WEBHOOK = _ka.al("drive_webhook")

# Hariç tutulacak anahtar kelimeler (küçük harf)
EXCLUDE_KEYWORDS = ["baydar", "casmoni", "emre oral", "turan solmaz"]

# Kullanıcı Kimlik Bilgileri (Gerektiğinde Mobil İmza ile oturum açmak için)
USER_TC = _ka.al("tc")
USER_GSM = _ka.al("gsm")
USER_OPERATOR = _ka.al("operator", "turktelekom")
USER_PIN = _ka.al("pin")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
)
logger = logging.getLogger("drive_esitle")

# Küresel HTTP Oturumu (Keep-Alive ve bağlantı havuzu)
_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3)
_session.mount("https://", adapter)
_session.mount("http://", adapter)


def tr_lower(text: str) -> str:
    if not text:
        return ""
    trans = str.maketrans("İIĞÜŞÖÇ", "iığüşöç")
    return text.translate(trans).lower()


def is_excluded(text: str) -> bool:
    if not text:
        return False
    low = tr_lower(text)
    for kw in EXCLUDE_KEYWORDS:
        if kw in low:
            return True
    return False


def parse_date_str(text: str) -> str:
    """Metin veya dosya adından YYYY-MM-DD formatında tarih çeker."""
    if not text:
        return ""
    # YYYY-MM-DD veya YYYY_MM_DD
    m1 = re.search(r'(\b\d{4})[-_](\d{2})[-_](\d{2})', text)
    if m1:
        return f"{m1.group(1)}-{m1.group(2)}-{m1.group(3)}"
    # DD.MM.YYYY
    m2 = re.search(r'(\b\d{2})\.(\d{2})\.(\d{4})', text)
    if m2:
        return f"{m2.group(3)}-{m2.group(2)}-{m2.group(1)}"
    return ""


def load_drive_index() -> dict:
    if INDEX_JSON_PATH.exists():
        try:
            return json.loads(INDEX_JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_drive_index(index_data: dict):
    try:
        INDEX_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        INDEX_JSON_PATH.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"İndeks kaydedilemedi: {e}")


def write_status(stage: str, stage_current: int, stage_total: int, uploaded_total: int, note: str = ""):
    data = {
        "pid": os.getpid(),
        "status": "calisiyor",
        "current_stage": stage,
        "stage_progress": f"{stage_current}/{stage_total}",
        "uploaded_total": uploaded_total,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": note
    }
    try:
        STATUS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def upload_to_drive_webhook(file_path: Path, remote_folder: str, webhook_url: str = DEFAULT_WEBHOOK, retries: int = 3) -> dict:
    """Dosyayı doğrudan Apps Script Webhook üzerinden Google Drive'a yükler."""
    if not file_path.exists() or file_path.stat().st_size == 0:
        return {"status": "error", "message": "Dosya yok veya 0 bayt"}

    sz = file_path.stat().st_size
    if sz > 25 * 1024 * 1024:
        logger.warning(f"Dosya çok büyük ({round(sz/(1024*1024), 1)} MB), atlanıyor: {file_path.name}")
        return {"status": "error", "message": "Dosya 25MB üzerinde"}

    for attempt in range(1, retries + 1):
        try:
            raw = file_path.read_bytes()
            b64_content = base64.b64encode(raw).decode("utf-8")
            payload = {
                "filename": file_path.name,
                "folder_path": remote_folder.replace("\\", "/"),
                "content": b64_content
            }

            resp = _session.post(webhook_url, json=payload, timeout=50)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success" or "fileId" in data:
                    return {
                        "status": "success",
                        "file_id": data.get("fileId", ""),
                        "url": data.get("url", f"https://drive.google.com/file/d/{data.get('fileId')}/view"),
                        "filename": file_path.name,
                        "folder": remote_folder
                    }
                return {"status": "error", "message": f"Webhook hatası: {resp.text[:200]}"}
            elif resp.status_code == 429:
                time.sleep(attempt * 3)
            else:
                if attempt == retries:
                    return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            if attempt == retries:
                return {"status": "error", "message": str(e)}
            time.sleep(attempt * 2)

    return {"status": "error", "message": "Bilinmeyen yükleme hatası"}


def ensure_uyap_session(bridge) -> bool:
    """UYAP oturumunu kontrol eder, yoksa e-imza veya Mobil İmza ile oturum açar."""
    try:
        ok, _ = bridge.ensure_browser(headless=True)
        if not ok:
            return False

        if bridge.is_logged_in():
            logger.info("[✓] Mevcut UYAP oturumu aktif.")
            return True

        # 1. Öncelik: e-İmza (ArkSigner USB kartı takılıysa)
        logger.info("[*] USB E-İmza donanımı kontrol ediliyor...")
        try:
            ok_e, msg_e = bridge.auto_relogin(pin=USER_PIN)
            if ok_e:
                logger.info(f"[✓] E-İmza ile oturum açıldı: {msg_e}")
                return True
        except Exception:
            pass

        # 2. Öncelik: Mobil İmza (SIM onaylı — yalnızca etkileşimli açık kullanıcı onayıyla)
        from uyap_indirici import ask_mobil_imza_onayi
        if not ask_mobil_imza_onayi(gsm=USER_GSM):
            logger.info("[i] Otomatik mobil imza kapalı: 'Mobil imza isteği gönderilsin mi?' onayı verilmedi.")
            return False
        logger.info(f"[*] Mobil İmza isteği gönderiliyor (GSM: {USER_GSM})...")
        ok_m, msg_m = bridge.login_with_mobil_imza(
            tc=USER_TC,
            gsm=USER_GSM,
            operator=USER_OPERATOR,
            timeout_s=120.0,
            confirmed=True,
        )
        if ok_m:
            logger.info(f"[✓] Mobil İmza ile oturum açıldı: {msg_m}")
            return True
        logger.warning(f"[!] Mobil İmza girişi henüz tamamlanmadı: {msg_m}")
    except Exception as e:
        logger.warning(f"[!] UYAP oturum denetim hatası: {e}")

    return False


def collect_local_files(index: dict) -> tuple[list[dict], set[str]]:
    """Telefonda mevcut olup henüz Drive'a yüklenmemiş tüm geçerli dosyaları toplar."""
    ignored_exts = ('.json', '.csv', '.ics', '.log', '.tmp', '.py', '.sh', '.bak')
    scan_roots = [SDCARD_ARCHIVE_DIR]
    local_files = []
    local_tokens = set()

    for sr in scan_roots:
        if not sr.exists():
            continue
        for root, _, files in os.walk(sr):
            for fn in files:
                if fn.endswith(ignored_exts) or fn.startswith('.'):
                    continue
                fp = Path(root) / fn
                if fp.stat().st_size == 0:
                    continue

                # Yerel eşleşme için tokenları ve dosya adını kaydet
                local_tokens.add(fn)
                for tok in re.findall(r'[a-zA-Z0-9_-]{4,}', fn):
                    local_tokens.add(tok)

                rel_p = str(fp.relative_to(sr))
                # Filtre kontrolü
                if is_excluded(f"{rel_p} {fn}"):
                    continue

                # Zaten Drive'a yüklendi mi?
                if fn in index or rel_p in index:
                    continue

                tarih = parse_date_str(fn)
                if not tarih:
                    # Dosya değiştirilme tarihinden al
                    tarih = datetime.fromtimestamp(fp.stat().st_mtime).strftime("%Y-%m-%d")

                # Klasör hiyerarşisi: UYAP_Arsiv/<relative_folder>
                parent_rel = str(Path(rel_p).parent)
                if parent_rel == "." or not parent_rel:
                    remote_folder = "UYAP_Arsiv/DIGER"
                else:
                    remote_folder = f"UYAP_Arsiv/{parent_rel}"

                local_files.append({
                    "source": "local",
                    "file_path": fp,
                    "filename": fn,
                    "rel_path": rel_p,
                    "remote_folder": remote_folder,
                    "tarih": tarih,
                    "key": fn
                })

    return local_files, local_tokens


def collect_remote_records(index: dict, local_tokens: set[str]) -> list[dict]:
    """Veritabanında kayıtlı olup yerelde veya Drive'da olmayan tüm evrakları toplar."""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    query = """
        SELECT e.id, e.dkey, e.tur, e.aciklama, e.tarih, e.evrak_id, e.gercek_id, e.birim_evrak_no,
               d.dosya_id, d.birim, d.dosya_no
        FROM evrak e
        JOIN dosya d ON e.dkey = d.dkey
        WHERE e.evrak_id IS NOT NULL AND e.evrak_id != ''
        ORDER BY e.tarih DESC
    """
    rows = cur.execute(query).fetchall()
    conn.close()

    remote_items = []
    for r in rows:
        eid, dkey, tur, aciklama, tarih, evrak_uuid, gercek_id, birim_ev_no, dosya_id, birim, dosya_no = r

        if is_excluded(f"{dkey} {tur or ''} {aciklama or ''}"):
            continue

        clean_ev_id = str(evrak_uuid or "").strip().strip('"')
        clean_d_id = str(dosya_id or "").strip().strip('"')
        clean_g_id = str(gercek_id or "").strip().strip('"')
        clean_ev_no = str(birim_ev_no or "").strip()

        if not clean_ev_id or not clean_d_id:
            continue

        # Drive'da var mı?
        if clean_ev_id in index or clean_g_id in index or str(eid) in index:
            continue

        # Yerelde zaten dosya olarak var mı (O(1) kontrol)?
        if (clean_ev_id in local_tokens or
            (clean_g_id and clean_g_id in local_tokens) or
            (clean_ev_no and clean_ev_no in local_tokens)):
            continue

        folder_clean = re.sub(r'[/\\:*?"<>|]', '_', dkey.replace('|', '_')).strip()
        remote_folder = f"UYAP_Arsiv/DAVA_EVRAKLARI/{folder_clean}"

        remote_items.append({
            "source": "uyap_remote",
            "id": eid,
            "dkey": dkey,
            "tur": tur or "Evrak",
            "aciklama": aciklama or "",
            "tarih": tarih or "2026-01-01",
            "evrak_id": clean_ev_id,
            "dosya_id": clean_d_id,
            "birim": birim or "Mahkeme",
            "dosya_no": dosya_no or "DosyaNo",
            "remote_folder": remote_folder,
            "key": clean_ev_id
        })

    return remote_items


def sync_stage(stage_label: str, items: list[dict], index: dict, bridge=None, dry_run: bool = False, limit: int = 0) -> int:
    """Belirli bir zaman dilimindeki evrakları sırayla işler ve Drive'a aktarır."""
    if not items:
        logger.info(f"[*] [{stage_label}] İşlenecek evrak bulunmuyor.")
        return 0

    total_stage = len(items) if limit == 0 else min(len(items), limit)
    logger.info("-----------------------------------------------------------------")
    logger.info(f"  {stage_label.upper()} BAŞLATILIYOR ({total_stage} Evrak)")
    logger.info("-----------------------------------------------------------------")

    success_count = 0
    checked_session = False
    session_active = False

    for idx, item in enumerate(items[:total_stage], 1):
        write_status(stage_label, idx, total_stage, len(index), f"{item['source']}: {item['key']}")
        src = item["source"]

        if src == "local":
            fp = item["file_path"]
            remote_folder = item["remote_folder"]
            logger.info(f"[*] [{stage_label}] Yerelden Yükleniyor ({idx}/{total_stage}): {fp.name}")

            if dry_run:
                logger.info(f"    [DRY-RUN] Hedef: {remote_folder}/{fp.name}")
                success_count += 1
                continue

            res = upload_to_drive_webhook(fp, remote_folder)
            if res.get("status") == "success":
                logger.info(f"    [✓] Drive'a Yüklendi! FileID: {res.get('file_id')}")
                index[item["key"]] = {
                    "drive_file_id": res.get("file_id"),
                    "drive_url": res.get("url"),
                    "filename": fp.name,
                    "rel_path": item["rel_path"],
                    "folder": remote_folder,
                    "tarih": item["tarih"],
                    "source": "local",
                    "yukleme_zamani": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                save_drive_index(index)
                success_count += 1
                time.sleep(0.5)
            else:
                logger.warning(f"    [!] Yükleme başarısız: {res.get('message')}")

        elif src == "uyap_remote":
            logger.info(f"[*] [{stage_label}] UYAP'tan İndiriliyor ({idx}/{total_stage}): {item['dkey']} - {item['tur']}")

            if dry_run:
                logger.info(f"    [DRY-RUN] UYAP İndirme: {item['evrak_id']}")
                success_count += 1
                continue

            # UYAP oturumunu kontrol et
            if not checked_session or not session_active:
                if bridge:
                    session_active = bridge.is_logged_in()
                    if not session_active:
                        session_active = ensure_uyap_session(bridge)
                    checked_session = True

            if not session_active:
                logger.warning(f"    [!] UYAP oturumu aktif değil, evrak indirilemedi ({item['evrak_id']}).")
                continue

            # İndirme işlemi
            try:
                from uyap_indirici import sanitize_path_part
                import donusturucu

                dkey = item["dkey"]
                ev_id = item["evrak_id"]
                d_id = item["dosya_id"]
                tur = item["tur"]
                tarih = item["tarih"]

                folder_clean = re.sub(r'[/\\:*?"<>|]', '_', dkey.replace('|', '_')).strip()
                case_dir = SDCARD_ARCHIVE_DIR / folder_clean
                case_dir.mkdir(parents=True, exist_ok=True)
                pdf_dir = case_dir / "PDFler"
                pdf_dir.mkdir(parents=True, exist_ok=True)

                san_tur = sanitize_path_part(tur).replace(" ", "_")
                san_ack = sanitize_path_part(item["aciklama"] or "").replace(" ", "_")[:25]
                fname_base = f"{tarih}_{san_tur}"
                if san_ack and san_ack.lower() not in san_tur.lower():
                    fname_base += f"_{san_ack}"
                fname_base += f"_{ev_id[:8]}"

                res_dl = bridge.download_document({"dosyaId": d_id, "evrakId": ev_id})
                raw_b64 = res_dl.get("base64")
                if not raw_b64:
                    logger.warning(f"    [!] Evrak indirilemedi: {res_dl.get('error') or res_dl.get('errorHeader')}")
                    continue

                raw_bytes = base64.b64decode(raw_b64)
                is_pdf = raw_bytes.startswith(b"%PDF")
                is_udf = raw_bytes.startswith(b"PK")
                ext = ".pdf" if is_pdf else (".udf" if is_udf else ".bin")

                dest_raw = case_dir / f"{fname_base}{ext}"
                dest_raw.write_bytes(raw_bytes)

                dest_pdf = None
                if is_pdf:
                    dest_pdf = dest_raw
                elif is_udf:
                    try:
                        c_path = donusturucu.udf_to_pdf(dest_raw)
                        if c_path and Path(c_path).exists():
                            target_pdf = pdf_dir / f"{fname_base}.pdf"
                            import shutil
                            shutil.copy2(c_path, target_pdf)
                            dest_pdf = target_pdf
                    except Exception as ex:
                        logger.warning(f"    [!] PDF dönüşüm hatası: {ex}")

                file_to_drive = dest_pdf if (dest_pdf and dest_pdf.exists()) else dest_raw
                res_up = upload_to_drive_webhook(file_to_drive, item["remote_folder"])
                if res_up.get("status") == "success":
                    logger.info(f"    [✓] UYAP'tan İndirilip Drive'a Yüklendi! FileID: {res_up.get('file_id')}")
                    index[ev_id] = {
                        "drive_file_id": res_up.get("file_id"),
                        "drive_url": res_up.get("url"),
                        "evrak_id": ev_id,
                        "dkey": dkey,
                        "tur": tur,
                        "tarih": tarih,
                        "source": "uyap_download",
                        "local_raw": str(dest_raw),
                        "local_pdf": str(dest_pdf) if dest_pdf else "",
                        "yukleme_zamani": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    save_drive_index(index)
                    success_count += 1
                    time.sleep(0.5)
                else:
                    logger.warning(f"    [!] Drive yükleme hatası: {res_up.get('message')}")

            except Exception as e:
                logger.error(f"    [!] İndirme/Yükleme istisnası: {e}")

    logger.info(f"[✓] {stage_label} Tamamlandı: {success_count} evrak başarıyla eşitlendi.")
    return success_count


def run_full_sync(asama: str = "kademeli", limit: int = 0, dry_run: bool = False):
    """Tüm senkronizasyon motorunu kademeli ve güvenli olarak çalıştırır."""
    logger.info("=================================================================")
    logger.info("  UYAP TAM OTONOM GOOGLE DRIVE EŞİTLEME MOTORU")
    logger.info("  Tarih: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=================================================================")

    # PID kaydet
    PID_FILE.write_text(str(os.getpid()))

    index = load_drive_index()
    logger.info(f"[*] Mevcut Drive İndeksinde {len(index):,} evrak kayıtlı.")

    # 1. Yerel ve Uzak evrak havuzunu hazırla
    logger.info("[*] Yerel ve UYAP veritabanı taranıyor...")
    local_items, local_tokens = collect_local_files(index)
    remote_items = collect_remote_records(index, local_tokens)

    logger.info(f"[+] Yerelde Yüklenmeye Hazır Evrak : {len(local_items):,}")
    logger.info(f"[+] UYAP'tan İndirilecek Eksik Evrak: {len(remote_items):,}")
    logger.info(f"[+] Toplam Senkronize Edilecek    : {len(local_items) + len(remote_items):,}")

    # UYAP Bridge hazırla
    bridge = None
    try:
        from uyap_indirici import UyapBrowserBridge
        bridge = UyapBrowserBridge()
    except Exception as e:
        logger.warning(f"[*] UYAP Bridge yüklenemedi (yalnızca yerel eşitleme aktif): {e}")

    now = datetime.now()
    d1 = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    d7 = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    d30 = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    d60 = (now - timedelta(days=60)).strftime("%Y-%m-%d")

    stages_plan = []
    if asama == "1gun":
        stages_plan = [("Aşama 1: Son 1 Gün", lambda d: d >= d1)]
    elif asama == "1hafta":
        stages_plan = [("Aşama 2: Son 1 Hafta", lambda d: d >= d7)]
    elif asama == "1ay":
        stages_plan = [("Aşama 3: Son 1 Ay", lambda d: d >= d30)]
    elif asama == "2ay":
        stages_plan = [("Aşama 4: Son 2 Ay", lambda d: d >= d60)]
    elif asama == "hepsi":
        stages_plan = [("Tüm Arşiv", lambda d: True)]
    else:  # "kademeli" (varsayılan)
        stages_plan = [
            ("Aşama 1: Son 1 Gün (Bugün ve Dün)", lambda d: d >= d1),
            ("Aşama 2: Son 1 Hafta (Son 7 Gün)", lambda d: d1 > d >= d7),
            ("Aşama 3: Son 1 Ay (Son 30 Gün)", lambda d: d7 > d >= d30),
            ("Aşama 4: Son 2 Ay (Son 60 Gün)", lambda d: d30 > d >= d60),
            ("Aşama 5: Tüm Arşiv (Geriye Kalanlar)", lambda d: d < d60 or not d)
        ]

    toplam_yuklenen = 0
    all_combined = local_items + remote_items

    for label, date_matcher in stages_plan:
        stage_items = [it for it in all_combined if date_matcher(it["tarih"])]
        # En yeni tarihten eskiye sırala
        stage_items.sort(key=lambda x: x["tarih"] or "", reverse=True)

        logger.info(f"[*] {label}: {len(stage_items)} adet evrak belirlendi.")
        if stage_items:
            c = sync_stage(label, stage_items, index, bridge=bridge, dry_run=dry_run, limit=limit)
            toplam_yuklenen += c

    write_status("tamamlandi", 100, 100, len(index), f"Toplam {toplam_yuklenen} yeni evrak eşitlendi.")
    if PID_FILE.exists():
        PID_FILE.unlink()

    logger.info("=================================================================")
    logger.info("  TAM EŞİTLEME BAŞARIYLA TAMAMLANDI")
    logger.info(f"  • Bu Oturumda Yüklenen Yeni Evrak : {toplam_yuklenen:,}")
    logger.info(f"  • Drive'daki Güncel Toplam Evrak  : {len(index):,}")
    logger.info("=================================================================")


def get_status():
    """Çalışan arka plan sürecinin durumunu ekrana basar."""
    is_running = False
    pid = 0
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            is_running = True
        except Exception:
            is_running = False

    print("=================================================================")
    print("  UYAP GOOGLE DRIVE EŞİTLEME DURUMU")
    print("=================================================================")
    print(f"  • Servis Durumu       : {'[ÇALIŞIYOR]' if is_running else '[DURDU / BOŞTA]'}")
    if is_running:
        print(f"  • Süreç Kimliği (PID) : {pid}")

    if STATUS_FILE.exists():
        try:
            st = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            print(f"  • Aktif Aşama         : {st.get('current_stage')}")
            print(f"  • Aşama İlerlemesi    : {st.get('stage_progress')}")
            print(f"  • Drive Toplam Evrak  : {st.get('uploaded_total')}")
            print(f"  • Son Güncelleme      : {st.get('last_update')}")
            if st.get("note"):
                print(f"  • Son İşlem           : {st.get('note')}")
        except Exception:
            pass

    if LOG_FILE.exists():
        print("-----------------------------------------------------------------")
        print("  SON LOG ÇIKTILARI:")
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()[-8:]
        for ln in lines:
            print("  ", ln)
    print("=================================================================")


def stop_daemon():
    """Çalışan arka plan servisini sonlandırır."""
    if not PID_FILE.exists():
        print("[*] Çalışan aktif bir eşitleme servisi bulunamadı.")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        if PID_FILE.exists():
            PID_FILE.unlink()
        print(f"[✓] Eşitleme servisi (PID {pid}) güvenle durduruldu.")
    except Exception as e:
        print(f"[!] Servis durdurulamadı: {e}")
        if PID_FILE.exists():
            PID_FILE.unlink()


def start_daemon_process(args_list: list[str]):
    """Arka planda bağımsız bir süreç başlatır."""
    cmd = [sys.executable, str(Path(__file__).resolve())] + args_list
    # --daemon ve --start bayraklarını komuttan çıkar
    cmd = [c for c in cmd if c not in ("--daemon", "--start")]

    proc = subprocess.Popen(
        cmd,
        stdout=open(LOG_FILE, "a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    PID_FILE.write_text(str(proc.pid))
    print(f"[✓] UYAP Google Drive Eşitleyici arka planda başlatıldı! (PID: {proc.pid})")
    print(f"    Log dosyası: {LOG_FILE}")
    print("    Durumu kontrol etmek için: uyap-drive-esitle --status")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UYAP Google Drive Akıllı ve Tam Eşitleyici")
    parser.add_argument("--asama", choices=["1gun", "1hafta", "1ay", "2ay", "hepsi", "kademeli"], default="kademeli", help="Zaman aşaması (varsayılan: kademeli)")
    parser.add_argument("--limit", type=int, default=0, help="Her aşamada işlenecek maksimum evrak sayısı (0 = sınırsız)")
    parser.add_argument("--dry-run", action="store_true", help="Gerçek yükleme/indirme yapmadan simüle et")
    parser.add_argument("--daemon", "--start", dest="start_daemon", action="store_true", help="Arka planda kesintisiz çalıştır")
    parser.add_argument("--status", action="store_true", help="Çalışma durumunu ve son logları göster")
    parser.add_argument("--stop", action="store_true", help="Çalışan arka plan servisini durdur")

    args = parser.parse_args()

    if args.status:
        get_status()
    elif args.stop:
        stop_daemon()
    elif args.start_daemon:
        forward_args = []
        if args.asama: forward_args.extend(["--asama", args.asama])
        if args.limit: forward_args.extend(["--limit", str(args.limit)])
        if args.dry_run: forward_args.append("--dry-run")
        start_daemon_process(forward_args)
    else:
        run_full_sync(asama=args.asama, limit=args.limit, dry_run=args.dry_run)
