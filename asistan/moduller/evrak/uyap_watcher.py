#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır. / All rights reserved.
"""
UYAP Nöbetçi Bot & Arka Plan İzleyici (Watcher)
==============================================
Avukat Portal'ı arka planda izler, açık (derdest) dosyalardaki yeni evrakları,
karşı taraf dilekçelerini, tensip ve duruşma zabıtlarını, bilirkişi raporlarını
ve tebligatları otomatik yakalar; indirip PDF'e dönüştürür ve Telegram'dan
anlık bildirim + PDF eki olarak avukata iletir.

Özellikler:
  1. Oturum Koruyucu (Keep-Alive Heartbeat): UYAP oturumunu 3 dakikada bir pingle canlı tutar.
  2. Açık Dosya Nöbetçisi: Yalnızca derdest (açık) 149 dosyayı nazikçe sorgular (WAF dostu).
  3. Anlık İndirme & PDF: Yeni evrak düştüğü an indirilir, UDF/TIF ise anında PDF yapılır.
  4. Hukuki Süre Analizi: Tebligat, tensip veya bilirkişi raporu için yasal süreleri hesaplar.
  5. Telegram Entegrasyonu: Yeni evrakı, dosya bilgilerini ve PDF belgesini doğrudan iletir.
  6. Duruşma Hatırlatıcı: Yaklaşan duruşmaları gün başında / öncesinde hatırlatır.
  7. Google Drive Senkronizasyon Kancası: İnen evrakları ve SQLite yedeğini Drive'a eşitler.

Kullanım:
  python uyap_watcher.py --setup           # Telegram bot ayarlarını yap
  python uyap_watcher.py --test-telegram   # Telegram bağlantısını test et
  python uyap_watcher.py                   # Nöbetçiyi başlat (varsayılan: 30 dk)
  python uyap_watcher.py --interval 15     # 15 dakikalık aralıkla çalıştır
  python uyap_watcher.py --drive-dir "G:\\Drive'ım\\UYAP_Arsiv"  # Google Drive eşitlemesiyle çalıştır
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
DATA_DIR = Path(os.environ.get("UYAP_VERI_DIZINI") or BASE_DIR)
CONFIG_FILE = DATA_DIR / "watcher_config.json"
LOG_DIR = DATA_DIR / "loglar"

# Günlük
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (Watcher) %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "watcher.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("uyap.watcher")

# Katalog ve Dönüştürücü İçe Aktarımı
sys.path.insert(0, str(BASE_DIR))
import evrak_katalog as ek
import donusturucu as dn


# ---------------------------------------------------------------------------
# Telegram Bot İstemcisi (Sıfır ek kütüphane bağımlılığı)
# ---------------------------------------------------------------------------
class TelegramClient:
    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = bot_token.strip()
        self.chat_id = chat_id.strip()

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.is_configured:
            return False
        import requests
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                return True
            logger.error("Telegram mesaj hatası: %s - %s", resp.status_code, resp.text)
        except Exception as e:
            logger.error("Telegram bağlantı hatası: %s", e)
        return False

    def send_document(self, file_path: Path | str, caption: str = "") -> bool:
        if not self.is_configured:
            return False
        import requests
        p = Path(file_path)
        if not p.exists() or p.stat().st_size == 0:
            return False
        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        data = {"chat_id": self.chat_id, "caption": caption[:1000], "parse_mode": "HTML"}
        try:
            with open(p, "rb") as f:
                files = {"document": (p.name, f)}
                resp = requests.post(url, data=data, files=files, timeout=45)
                if resp.status_code == 200:
                    return True
                logger.error("Telegram evrak gönderme hatası: %s - %s", resp.status_code, resp.text)
        except Exception as e:
            logger.error("Telegram dosya aktarım hatası: %s", e)
        return False


# ---------------------------------------------------------------------------
# Yapılandırma Yönetimi
# ---------------------------------------------------------------------------
DEFAULT_WATCHED_CATEGORIES = [
    "durusma", "bilirkisi", "karar", "tensip", "dilekce",
    "layihalar", "tebligat", "kesinlesme", "iddianame", "tutuklama"
]

def load_config() -> dict:
    cfg = {}
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    cfg.setdefault("telegram_token", os.environ.get("UYAP_TELEGRAM_TOKEN", ""))
    cfg.setdefault("telegram_chat_id", os.environ.get("UYAP_TELEGRAM_CHAT_ID", ""))
    cfg.setdefault("interval_minutes", 15)
    cfg.setdefault("keepalive_minutes", 3)
    cfg.setdefault("google_drive_dir", "G:\\Drive'ım\\UYAP_Arsiv")
    cfg.setdefault("google_drive_webhook", "")
    cfg.setdefault("check_open_cases", True)
    cfg.setdefault("check_durusma", True)
    cfg.setdefault("check_tebligat", True)
    cfg.setdefault("telegram_summary_report", True)
    cfg.setdefault("watched_categories", DEFAULT_WATCHED_CATEGORIES)
    cfg.setdefault("auto_download_missing", True)
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Yapılandırma kaydedildi: %s", CONFIG_FILE)


# ---------------------------------------------------------------------------
# Hukuki Süre Analizcisi
# ---------------------------------------------------------------------------
def calculate_legal_deadline(tur: str, aciklama: str) -> str:
    """Evrak türü ve açıklamasına göre yasal itiraz/cevap süresini hesaplar."""
    t_lower = (tur + " " + aciklama).lower()
    bugun = dt.date.today()

    if "bilirkişi" in t_lower or "bilirkisi" in t_lower or "ek rapor" in t_lower:
        son_gun = bugun + dt.timedelta(days=14)
        return (f"⚖️ <b>Yasal Süre:</b> Bilirkişi Raporuna İtiraz (HMK m. 281)\n"
                f"Tebliğden itibaren <b>2 hafta</b>. (Tahmini son gün: {son_gun.strftime('%d.%m.%Y')})")

    if "tebligat" in t_lower or "uets" in t_lower or "mazbata" in t_lower:
        teblig_tarihi = bugun + dt.timedelta(days=5)  # TK 7/a elektronik tebligat 5 gün
        cevap_son = teblig_tarihi + dt.timedelta(days=14)
        return (f"📬 <b>Tebligat Kanunu m. 7/a:</b> Elektronik tebligat 5 gün sonra ({teblig_tarihi.strftime('%d.%m.%Y')}) tebliğ sayılır.\n"
                f"2 haftalık yasal cevap/istinaf süresi için son gün: <b>{cevap_son.strftime('%d.%m.%Y')}</b>")

    if "tensip" in t_lower:
        return ("📋 <b>Tensip Zaptı:</b> Mahkemenin tensip ara kararlarını ve delil/avans "
                "kesin sürelerini zaptı açarak kontrol ediniz.")

    if "gerekçeli karar" in t_lower or "hüküm" in t_lower:
        istinaf_son = bugun + dt.timedelta(days=14)
        return (f"📜 <b>Gerekçeli Karar:</b> HMK istinaf süresi tebliğden itibaren <b>2 hafta</b> "
                f"(Tahmini son gün: {istinaf_son.strftime('%d.%m.%Y')}). Ceza davalarında 7 gün.")

    if "dava dilekçesi" in t_lower or "cevap dilekçesi" in t_lower:
        return "📝 <b>Dilekçe Değişimi:</b> Karşı tarafın sunduğu dilekçeye karşı 2 haftalık cevap/itiraz süresi başlayabilir."

    return ""


# ---------------------------------------------------------------------------
# UYAP Nöbetçi Motoru (Watcher Engine)
# ---------------------------------------------------------------------------
class UyapWatcher:
    def __init__(self, config: dict):
        self.config = config
        self.katalog = ek.Katalog()
        self.tg = TelegramClient(
            config.get("telegram_token", ""),
            config.get("telegram_chat_id", "")
        )
        from google_drive_entegrasyonu import GoogleDriveCloudClient
        self.cloud = GoogleDriveCloudClient(
            webhook_url=config.get("google_drive_webhook", ""),
            local_drive_dir=config.get("google_drive_dir", "")
        )
        import uyap_indirici as ui
        self.is_termux = getattr(ui, "IS_TERMUX", False) or sys.platform != "win32"
        gdrive_cfg = config.get("google_drive_dir", "")
        if self.is_termux:
            sd_cand = Path("/sdcard/UYAP_Indirilenler")
            self.download_dir = sd_cand if sd_cand.parent.exists() else DATA_DIR / "UYAP_Indirilenler"
        else:
            self.download_dir = Path(gdrive_cfg or os.environ.get("UYAP_INDIRME_DIZINI") or DATA_DIR / "UYAP_Indirilenler")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.bridge = None
        self.motor = None
        self.last_keepalive = 0
        self.last_intel_sync = 0
        self.notified_durusmalar = set()

        from uyap_finans_safahat import UyapFinansSafahatManager
        self.finans_mgr = UyapFinansSafahatManager()
        from uyap_sure_analiz import UyapSureAnalizManager
        self.sure_mgr = UyapSureAnalizManager()

    def connect_bridge(self) -> bool:
        """Açık olan UYAP Chrome oturumuna bağlanır ve oturumu doğrular."""
        try:
            import uyap_indirici as ui
            self.bridge = ui.UyapBrowserBridge(port=ui.CDP_PORT)
            ready, msg = self.bridge.ensure_ready("uyap")
            if not ready:
                logger.warning("UYAP tarayıcısına bağlanılamadı: %s", msg)
                return False

            # Kesin Oturum Kontrolü
            if not self.bridge.is_logged_in():
                logger.warning("⚠️ UYAP oturumu açık değil! Giriş doğrulanıyor...")

                # 1. Android / Termux Ortamı
                if getattr(ui, "IS_TERMUX", False):
                    cfg_path = Path(".uyap_config.json")
                    tc, gsm, op = "", "", "3"
                    if cfg_path.exists():
                        try:
                            with open(cfg_path, "r", encoding="utf-8") as f:
                                cdata = json.load(f)
                                tc = cdata.get("tc", "")
                                gsm = cdata.get("gsm", "")
                                op = cdata.get("operator", "3")
                        except Exception:
                            pass

                    if tc and gsm:
                        logger.info("📲 Android/Termux: Mobil İmza ile giriş başlatılıyor (TC: %s, GSM: %s)...", tc, gsm)
                        logger.info("🔔 Lütfen telefon ekranınıza gelecek olan SIM İmza Onayını (PIN) onaylayınız.")
                        ok_m, msg_m = self.bridge.login_with_mobil_imza(tc=tc, gsm=gsm, operator=op, status_cb=logger.info)
                        if not ok_m:
                            logger.error("❌ Mobil İmza ile giriş başarısız: %s", msg_m)
                            return False
                    else:
                        logger.error("❌ Termux'ta UYAP oturumu açık değil ve Mobil İmza ayarları (.uyap_config.json) bulunamadı.")
                        logger.error("👉 Android'de USB e-İmza yerine Mobil İmza kullanılır. Lütfen .uyap_config.json içine tc ve gsm bilgilerinizi kaydedin.")
                        return False

                # 2. Windows / Masaüstü Ortamı (e-İmza)
                else:
                    pin = getattr(ui, "DEFAULT_E_IMZA_PIN", None)
                    if not pin and os.path.exists("pin.txt"):
                        try:
                            with open("pin.txt", "r", encoding="utf-8") as f:
                                pin = f.read().strip()
                        except Exception:
                            pass

                    if pin:
                        logger.info("🔑 e-İmza PIN ile otomatik UYAP oturumu açılıyor...")
                        ok_re, msg_re = self.bridge.auto_relogin(pin=pin)
                        if not ok_re:
                            logger.warning("⚠️ e-İmza otomatik giriş başarısız: %s", msg_re)
                            logger.warning("👉 Lütfen e-İmzanızın (USB token) takılı olduğunu ve ArkSigner'ın çalıştığını kontrol ediniz.")
                            return False
                    else:
                        logger.warning("⚠️ e-İmza PIN'i (pin.txt) bulunamadı. Lütfen tarayıcıdan giriş yapınız.")
                        return False

            # Son kontrol (sayfa yükleniyorsa 4 denemeyle doğrula)
            logged_in = False
            for _ in range(4):
                if self.bridge.is_logged_in():
                    logged_in = True
                    break
                time.sleep(1.5)

            if not logged_in:
                logger.warning("⚠️ UYAP oturumu doğrulanamadı. Lütfen giriş yapınız.")
                return False

            uinfo = self.bridge.check_login_and_user()
            usr = uinfo.get("user") or {}
            full_name = f"{usr.get('ad', '') or usr.get('adi', '')} {usr.get('soyad', '') or usr.get('soyadi', '')}".strip() or "Avukat"
            logger.info("✅ UYAP oturumu doğrulandı: Sayın %s", full_name)

            relogin_fn = (lambda: self.bridge.auto_relogin(pin=ui.DEFAULT_E_IMZA_PIN)[0]) if getattr(ui, "DEFAULT_E_IMZA_PIN", None) else None
            self.motor = ek.Motor(self.bridge, self.katalog, self.download_dir, log=logger.info, relogin=relogin_fn)
            self.finans_mgr.bridge = self.bridge
            logger.info("UYAP tarayıcı köprüsüne başarıyla bağlandı (Port: %d).", self.bridge.port)
            return True
        except Exception as e:
            logger.error("Köprü bağlantı hatası: %s", e)
            return False

    def heartbeat(self) -> None:
        """Oturumun düşmemesi için 3 dakikada bir UYAP'a hafif bir AJAX isteği gönderir."""
        now = time.time()
        keepalive_s = self.config.get("keepalive_minutes", 3) * 60
        if now - self.last_keepalive < keepalive_s:
            return
        if not self.bridge:
            return
        try:
            js = "fetch('/kullanici_bilgileri.ajx').then(r=>r.status).catch(e=>0)"
            res = self.bridge.eval_js(js, timeout=10.0)
            self.last_keepalive = now
            logger.debug("Oturum nabzı (Heartbeat) gönderildi: durum=%s", res)
        except Exception as e:
            logger.debug("Heartbeat hatası: %s", e)

    def scan_open_cases(self) -> dict:
        """Açık (derdest) 149 dosyayı nazikçe sorgular; yeni evrakları yakalayıp indirir ve detaylı raporlar."""
        if not self.bridge:
            return {"new_downloaded": 0, "total_docs": 0, "already_in_drive": 0}

        start_time = time.time()

        # Sadece 'Açık' durumdaki dosyaları çek
        cur = self.katalog.db.execute(
            "SELECT dkey, birim, dosya_no, dosya_id, evrak_sayisi FROM dosya WHERE durum='Açık' ORDER BY taranma ASC"
        )
        open_cases = cur.fetchall()
        total_cases = len(open_cases)

        if total_cases == 0:
            logger.info("Katalogda açık dosya bulunamadı. UYAP'tan güncel dosya listesi çekiliyor...")
            try:
                raw_cases = self.bridge.query_tum_dosyalar()
                for c in raw_cases:
                    self.katalog.upsert_dosya(c, c.get("dosyaTaraflari") or c.get("tarafList"), "", "", "")
                cur = self.katalog.db.execute(
                    "SELECT dkey, birim, dosya_no, dosya_id, evrak_sayisi FROM dosya WHERE durum='Açık' ORDER BY taranma ASC"
                )
                open_cases = cur.fetchall()
                total_cases = len(open_cases)
                logger.info("UYAP'tan %d adet açık dosya kataloğa işlendi.", total_cases)
            except Exception as e:
                logger.warning("Dosya listesi çekilemedi: %s", e)

        logger.info("Derdest (Açık) Dosya Nöbetçisi: %d dosya kontrol ediliyor...", total_cases)

        stats = {
            "total_cases": total_cases,
            "processed_cases": 0,
            "total_docs": 0,
            "already_in_drive": 0,
            "filtered_category": 0,
            "old_existing": 0,
            "new_downloaded": 0,
            "elapsed_seconds": 0.0,
        }

        download_dir = self.download_dir
        drive_dir = Path(self.config.get("google_drive_dir")) if (self.config.get("google_drive_dir") and not self.is_termux) else None

        for idx, case in enumerate(open_cases, 1):
            self.heartbeat()
            dkey = case["dkey"]
            dosya_id = case["dosya_id"]
            if not dosya_id:
                continue

            stats["processed_cases"] += 1
            logger.info("  [%d/%d] 📂 %s (%s)...", idx, total_cases, case["birim"], case["dosya_no"])

            try:
                # UYAP'tan dosyanın güncel evrak sayfalarını al
                evrak_pages = self.bridge.query_dosya_evraklar(dosya_id)
                if not evrak_pages:
                    time.sleep(1.0)
                    continue

                # Bu dosyanın tarama öncesinde veritabanında bilinen mevcut evrak kimlikleri (skey)
                existing_skeys = {
                    r[0] for r in self.katalog.db.execute(
                        "SELECT skey FROM evrak WHERE dkey=?", (dkey,)
                    ).fetchall()
                }

                # Sayfaları kataloğa işle (tüm ekler ve gruplar dahil)
                self.katalog.ingest_pages(dkey, evrak_pages, oturum="watcher")

                # Dosya bilgileriyle (yargi, birim, dosya_no) birleştirilmiş evrak listesi
                cur = self.katalog.db.execute(
                    """SELECT e.*, d.yargi, d.birim, d.dosya_no
                       FROM evrak e
                       JOIN dosya d ON e.dkey = d.dkey
                       WHERE e.dkey = ?
                       ORDER BY e.id ASC""",
                    (dkey,)
                )
                all_case_docs = cur.fetchall()
                stats["total_docs"] += len(all_case_docs)

                truly_fresh = []
                watched_cats = set(self.config.get("watched_categories") or DEFAULT_WATCHED_CATEGORIES)
                allow_all = "tumu" in watched_cats or "*" in watched_cats

                for row in all_case_docs:
                    skey = row["skey"]

                    # 1. Zaten indirilmiş veya mükerrer olarak işaretlenmişse
                    if row["durum"] in ("indirildi", "mukerrer"):
                        stats["already_in_drive"] += 1
                        continue

                    # 2. Veritabanında kayıtlı pdf_path varsa ve fiziken diskte/Drive'da mevcutsa
                    if row["pdf_path"]:
                        p_check = Path(row["pdf_path"])
                        if p_check.exists() and p_check.stat().st_size > 0:
                            stats["already_in_drive"] += 1
                            continue

                    # 3. Kategori Filtresi: Yalnızca kullanıcının ilgilendiği hayati evraklar
                    kat = str(row["kategori"] or row["ust_kategori"] or "").lower()
                    if not allow_all and kat and kat not in watched_cats:
                        stats["filtered_category"] += 1
                        continue

                    # 4. Google Drive hedef yolu
                    target_pdf = ek.target_path_for(row, download_dir / "DAVA_EVRAKLARI", ".pdf")

                    # 5. Google Drive / diskte hedef PDF fiziken mevcut mu?
                    if target_pdf.exists() and target_pdf.stat().st_size > 0:
                        self.katalog.set_result(row["id"], durum="indirildi", pdf_path=str(target_pdf))
                        stats["already_in_drive"] += 1
                        continue

                    # 6. Bu evrak daha önceki taramalarda zaten veritabanında mevcut muydu?
                    # Açık dosya nöbetçisi YALNIZCA UYAP'a yeni düşmüş taze evrakları indirir ve bildirir.
                    # Eski eksik evraklar zaten döngü başında reconcile_missing_docs tarafından GUI filtreleriyle tamamlanır.
                    if skey in existing_skeys:
                        stats["old_existing"] += 1
                        continue

                    # 7. UYAP'a bu döngüde İLK KEZ düşmüş GERÇEK YENİ EVRAK!
                    truly_fresh.append((row, target_pdf, True))

                if truly_fresh:
                    new_alerts = [x for x in truly_fresh if x[2]]
                    if new_alerts:
                        logger.info("🔔 [%s - %s] %d GERÇEKTEN YENİ EVRAK BULUNDU!", case["birim"], case["dosya_no"], len(new_alerts))

                    for row, target_pdf, is_new_alert in truly_fresh:
                        tur = str(row["tur"] or "Evrak")
                        acik = str(row["aciklama"] or "")
                        gonderen = str(row["gonderen"] or "")
                        tarih = str(row["tarih"] or "")

                        # Evrakı Motor ile güvenli indir, PDF yap ve Google Drive'a eşitle
                        pdf_path = None
                        if getattr(self, "motor", None):
                            self.motor.download([row["id"]])
                            row_up = self.katalog.get(row["id"])
                            if row_up and row_up["pdf_path"]:
                                pdf_path = Path(row_up["pdf_path"])
                                if pdf_path.exists() and self.cloud and self.cloud.is_configured:
                                    rel_folder = f"DAVA_EVRAKLARI/{case['birim']}/{case['dosya_no']}"
                                    self.cloud.upload_file(pdf_path, remote_folder_path=rel_folder)

                        # Yasal süre hesabı
                        sure_bilgisi = calculate_legal_deadline(tur, acik)

                        # Telegram Bildirimi Hazırla (SADECE gerçekten yeni evraklar için bildirim gönder!)
                        if is_new_alert:
                            msg_lines = [
                                f"🔔 <b>UYAP: Yeni Evrak Geldi!</b>",
                                f"🏢 <b>Birim:</b> {case['birim']}",
                                f"📁 <b>Dosya:</b> {case['dosya_no']}",
                                f"📄 <b>Evrak Türü:</b> {tur}",
                                f"📅 <b>Tarih:</b> {tarih}",
                            ]
                            if gonderen:
                                msg_lines.append(f"👤 <b>Gönderen:</b> {gonderen}")
                            if acik:
                                msg_lines.append(f"📝 <b>Açıklama:</b> {acik}")
                            if sure_bilgisi:
                                msg_lines.append(f"\n{sure_bilgisi}")

                            msg_text = "\n".join(msg_lines)

                            # Telegram'a gönder (PDF varsa iliştir)
                            if pdf_path and pdf_path.exists() and pdf_path.stat().st_size <= 45 * 1024 * 1024:
                                self.tg.send_document(pdf_path, caption=msg_text)
                            else:
                                self.tg.send_message(msg_text)

                        stats["new_downloaded"] += 1

                # Taranma zamanını tazele
                # Finans ve Safahat güncelle (yeni evrak düştüğünde anında mali durumu ve safahati tazele)
                if truly_fresh:
                    try:
                        is_icra = "İcra" in (case["birim"] or "") or "Icra" in (case["birim"] or "")
                        if is_icra:
                            self.finans_mgr.fetch_icra_hesap(dosya_id, dkey, case["birim"], case["dosya_no"])
                        else:
                            self.finans_mgr.fetch_finans(dosya_id, dkey, case["birim"], case["dosya_no"])
                            self.finans_mgr.fetch_safahat(dosya_id, dkey, case["birim"], case["dosya_no"])
                    except Exception as fe:
                        logger.debug("Finans/safahat tazeleme hatası: %s", fe)

                now_str = dt.datetime.now().isoformat()[:19]
                self.katalog.db.execute("UPDATE dosya SET taranma=? WHERE dkey=?", (now_str, dkey))
                self.katalog.db.commit()

            except Exception as e:
                logger.warning("[%s] Evrak tarama hatası: %s", case["dosya_no"], e)

            # Periyodik ilerleme gösterimi (Her 15 dosyada bir veya son dosyada)
            if idx % 15 == 0 or idx == total_cases:
                pct = int((idx / total_cases) * 100)
                logger.info(
                    "⏳ İlerleme: [%d/%d - %%%d] | Taranan: %d | Drive'da Mevcut: %d | Filtrelenen (Rutin): %d | Yeni: %d",
                    idx, total_cases, pct, stats["total_docs"], stats["already_in_drive"], stats["filtered_category"], stats["new_downloaded"]
                )

            # WAF'a takılmamak için nazik bekleme
            time.sleep(0.4)

        # Google Drive varsa veritabanı anlık snapshot'ını güncelle
        if drive_dir:
            self.katalog.cloud_backup(drive_dir / "uyap_katalog_yedek.db")

        stats["elapsed_seconds"] = round(time.time() - start_time, 1)
        mins = int(stats["elapsed_seconds"] // 60)
        secs = int(stats["elapsed_seconds"] % 60)
        duration_str = f"{mins} dk {secs} sn" if mins > 0 else f"{secs} sn"

        # Detaylı Terminal Raporu
        logger.info("=" * 65)
        logger.info("  UYAP Nöbetçi Tarama Raporu (Döngü Tamamlandı)")
        logger.info("=" * 65)
        logger.info("  📁 Kontrol Edilen Açık Dosya : %d / %d", stats["processed_cases"], stats["total_cases"])
        logger.info("  📄 Taranan Toplam Evrak      : %d adet", stats["total_docs"])
        logger.info("  ☁️ Google Drive'da Mevcut    : %d adet", stats["already_in_drive"])
        logger.info("  🛡️ Filtrelenen (Rutin Evrak) : %d adet", stats["filtered_category"])
        logger.info("  📦 Eski / Önceden Kayıtlı    : %d adet", stats["old_existing"])
        logger.info("  🔔 Yeni İndirilen & Bildirilen: %d adet", stats["new_downloaded"])
        logger.info("  ⏱️ Toplam Tarama Süresi      : %s", duration_str)
        logger.info("=" * 65)

        # Telegram Döngü Özeti Gönderimi
        if self.tg.is_configured and self.config.get("telegram_summary_report", True):
            now_time = dt.datetime.now().strftime("%H:%M")
            next_mins = self.config.get("interval_minutes", 15)
            next_time = (dt.datetime.now() + dt.timedelta(minutes=next_mins)).strftime("%H:%M")

            tg_report = (
                f"📊 <b>UYAP Nöbetçi Tarama Raporu</b>\n"
                f"⏰ <b>Saat:</b> {now_time} | <b>Süre:</b> {duration_str}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 <b>İncelenen Açık Dosya:</b> {stats['processed_cases']}\n"
                f"📄 <b>Taranan Toplam Evrak:</b> {stats['total_docs']:,}\n"
                f"☁️ <b>Google Drive'da Mevcut:</b> {stats['already_in_drive']:,}\n"
                f"🛡️ <b>Filtrelenen Rutin Evrak:</b> {stats['filtered_category']:,}\n"
                f"📦 <b>Eski / Arşiv Kayıtlı:</b> {stats['old_existing']:,}\n"
                f"🔔 <b>Yeni İndirilen Evrak:</b> {stats['new_downloaded']}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏳ <b>Sonraki Kontrol:</b> {next_time} ({next_mins} dk sonra)"
            ).replace(",", ".")
            self.tg.send_message(tg_report)

        return stats

    def check_upcoming_hearings(self) -> None:
        """Önümüzdeki 7 günün duruşmalarını çeker, yaklaşanları Telegram'dan bildirir."""
        if not self.bridge or not self.config.get("check_durusma", True):
            return
        try:
            today = dt.date.today()
            end_d = today + dt.timedelta(days=7)
            durusmalar = self.bridge.query_durusmalar(today.strftime("%d/%m/%Y"), end_d.strftime("%d/%m/%Y"))
            if not durusmalar:
                return

            for d in durusmalar:
                dt_str = str(d.get("tarihSaat") or "")
                birim = str(d.get("yerelBirimAd") or "")
                dno = str(d.get("dosyaNo") or "")
                key = f"{dt_str}|{birim}|{dno}"

                if key not in self.notified_durusmalar:
                    # Kataloğa duruşmayı kaydet
                    t_part = dt_str.split()[0] if " " in dt_str else dt_str
                    s_part = dt_str.split()[1] if " " in dt_str else ""
                    self.katalog.upsert_durusma({
                        "birim": birim,
                        "dosya_no": dno,
                        "tarih": t_part,
                        "saat": s_part,
                        "yer": birim,
                        "aciklama": d.get("islemTuruAciklama", ""),
                    })

                    # Telegram Hatırlatması
                    tg_msg = (
                        f"⚖️ <b>DURUŞMA HATIRLATICI</b>\n"
                        f"📅 <b>Tarih & Saat:</b> {dt_str}\n"
                        f"🏢 <b>Mahkeme:</b> {birim}\n"
                        f"📁 <b>Dosya No:</b> {dno}\n"
                        f"📌 <b>Açıklama:</b> {d.get('islemTuruAciklama', '')}"
                    )
                    self.tg.send_message(tg_msg)
                    self.notified_durusmalar.add(key)
        except Exception as e:
            logger.debug("Duruşma sorgulama atlandı: %s", e)

    def get_priority_backlog_ids(self, limit: int = 50) -> list[int]:
        """Katalogdaki 526 binlik arşivden henüz indirilmemiş evrakları kesin HUKUKİ ÖNEM sırasına göre döner:
        1. Kararlar (Gerekçeli Karar, Hüküm, İcra Emri, İhtiyati Tedbir/Haciz)
        2. Duruşma Zabıtları ve Tensip Tutanakları (Ara kararlar, kesin süreler)
        3. Bilirkişi Raporları ve Keşif Tutanakları
        4. Tebligat ve Mazbatalar (Tüm tebligatlar ve mazbata parçaları)
        5. Dilekçeler ve Layihalar (Dava, Cevap, İtiraz, Beyan)
        6. İcra / Haciz / Satış İşlemleri
        7. Müzekkereler ve Kurum Cevapları (SGK, Tapu, Banka)
        8. Rutin Makbuzlar, Harçlar, Üst Yazılar
        Her kategori içinde EN YENİ TARİHLİDEN ESKİYE (tarih DESC) sıralanır.
        Mükerrer ve zaten indirilmiş olanlar kesinlikle filtrelenir.
        """
        sql = """
        SELECT e.id
        FROM evrak e
        WHERE e.durum NOT IN ('indirildi', 'mukerrer')
          AND (e.pdf_path IS NULL OR e.pdf_path = '')
        ORDER BY 
            CASE 
                WHEN e.kategori IN ('karar') THEN 1
                WHEN e.kategori IN ('durusma', 'tensip') THEN 2
                WHEN e.kategori IN ('bilirkisi') THEN 3
                WHEN e.kategori IN ('tebligat') THEN 4
                WHEN e.kategori IN ('dilekce', 'layihalar') THEN 5
                WHEN e.kategori IN ('icra') THEN 6
                WHEN e.kategori IN ('muzekkere') THEN 7
                ELSE 8
            END ASC,
            CASE WHEN e.tarih IS NOT NULL AND e.tarih != '' THEN e.tarih ELSE '1900-01-01' END DESC,
            e.id DESC
        LIMIT ?
        """
        cur = self.katalog.db.execute(sql, (limit,))
        return [r[0] for r in cur.fetchall()]

    def get_missing_doc_ids(self, limit: int = 100) -> list[int]:
        """Varsa GUI filtrelerini (.katalog_filtre.json) okur; yoksa doğrudan HUKUKİ ÖNEM sırasına göre ID'leri döner."""
        filter_file = DATA_DIR / ".katalog_filtre.json"
        filt = {}
        if filter_file.exists():
            try:
                saved = json.loads(filter_file.read_text(encoding="utf-8"))
                has_active = any(saved.get("text", {}).values()) or any(
                    any(v != 0 for v in st.values()) for st in saved.get("tri", {}).values()
                )
                if has_active:
                    filt = {k: saved.get("text", {}).get(k, "") for k in ["arama", "birim", "dosya_no", "muvekkil", "taraf", "baslangic", "bitis", "tur_haric"]}
                    filt["sadece_muvekkilli"] = saved.get("bool", {}).get("sadece_muvekkilli", False)
                    filt["kategori_ust"] = saved.get("bool", {}).get("kategori_ust", False)
                    filt["ek"] = saved.get("ek", "hepsi")
                    filt["ayni_ad_tek"] = saved.get("bool", {}).get("ayni_ad_tek", False)
                    filt["mukerrer_gizle"] = True

                    sec = {}
                    for fk, st in saved.get("tri", {}).items():
                        if fk == "durum":
                            continue
                        dahil = [k for k, v in st.items() if v == 1]
                        haric = [k for k, v in st.items() if v == -1]
                        if dahil or haric:
                            sec[fk] = {"dahil": dahil, "haric": haric}
                    sec["durum"] = {"dahil": ["yeni"], "haric": ["indirildi", "mukerrer"]}
                    filt["sec"] = sec
                    ids = self.katalog.ids_for(filt)
                    if ids:
                        return ids[:limit]
            except Exception as e:
                logger.warning("Filtre dosyası okunamadı: %s", e)

        # Özel filtre yoksa veya tümü seçiliyse HUKUKİ ÖNEM SIRASINA GÖRE çek!
        return self.get_priority_backlog_ids(limit=limit)

    def reconcile_missing_docs(self, max_batch: int = 40) -> int:
        """Katalogdaki tüm davalarda indirilmeyi bekleyen evrakları GUI filtrelerine (.katalog_filtre.json)
        uygun olarak sırayla indirir, PDF'e çevirir ve Google Drive'a eşitler."""
        if not self.bridge:
            return 0
        if not self.motor:
            import uyap_indirici as ui
            relogin_fn = (lambda: self.bridge.auto_relogin(pin=ui.DEFAULT_E_IMZA_PIN)[0]) if getattr(ui, "DEFAULT_E_IMZA_PIN", None) else None
            self.motor = ek.Motor(self.bridge, self.katalog, self.download_dir, log=logger.info, relogin=relogin_fn)

        target_ids = self.get_missing_doc_ids(limit=max_batch)
        if not target_ids:
            logger.info("✨ Tüm evraklar güncel! İndirilmeyi bekleyen eksik evrak bulunamadı.")
            return 0

        logger.info("🔄 Eksik Evrak Tamamlayıcı: %d eksik evrak indiriliyor ve Google Drive'a eşitleniyor...", len(target_ids))
        stats = self.motor.download(target_ids)
        downloaded = stats.get("indirildi", 0) + stats.get("onbellek", 0)
        mukerrer = stats.get("mukerrer", 0)

        # Google Drive bulut eşitlemesi (Telefon / Termux / Webhook / Yerel Klasör)
        if self.cloud and self.cloud.is_configured:
            for eid in target_ids:
                row_up = self.katalog.get(eid)
                if row_up and row_up.get("pdf_path"):
                    p = Path(row_up["pdf_path"])
                    if p.exists():
                        rel_folder = f"DAVA_EVRAKLARI/{row_up.get('birim', 'Diger')}/{row_up.get('dosya_no', 'Genel')}"
                        self.cloud.upload_file(p, remote_folder_path=rel_folder)

        logger.info("✅ Eksik Evrak Tamamlama Bitti: %d indirildi, %d mükerrer, %d hata.",
                    downloaded, mukerrer, stats.get("hata", 0))
        return downloaded

    def sync_intel_and_deadlines(self, force: bool = False) -> None:
        """Süreleri, duruşmaları, ara kararları ve portal işlemlerini günceller; Telegram alarmı gönderir."""
        now = time.time()
        # En fazla 30 dakikada bir veya force olduğunda tara
        if not force and (now - self.last_intel_sync < 1800):
            return

        try:
            logger.info("📅 Canlı Duruşma, Yasal Süre, Ara Karar ve Portal İşlemlerim Analizi çalıştırılıyor...")
            self.sure_mgr.scan_all(bridge=self.bridge)
            self.finans_mgr.fetch_portal_islemlerim(days_back=14)
            self.last_intel_sync = now

            if self.tg.is_configured:
                alert = self.sure_mgr.build_telegram_alert_message(max_days=3)
                if alert:
                    self.tg.send_message(alert)
                    logger.info("📢 Yaklaşan kritik süreler Telegram üzerinden iletildi.")
        except Exception as e:
            logger.warning("İstihbarat ve süre senkronizasyon hatası: %s", e)

    def run_loop(self, once: bool = False) -> None:
        """Sürekli arka plan nöbet döngüsü veya tek seferlik tarama (--once)."""
        logger.info("=" * 65)
        logger.info("  UYAP Nöbetçi Bot Devrede")
        logger.info("  Döngü Aralığı: %d dakika", self.config.get("interval_minutes", 15))
        if self.tg.is_configured:
            logger.info("  Telegram Bildirimleri: AKTİF")
            if not once:
                self.tg.send_message("🛡️ <b>UYAP Nöbetçi Bot Başlatıldı!</b>\nAçık dosyalar ve yeni evraklar izleniyor.")
        else:
            logger.warning("  Telegram Bildirimleri: YAPILANDIRILMAMIŞ (Terminal loglanacak)")
        logger.info("=" * 65)

        interval_s = self.config.get("interval_minutes", 15) * 60

        while True:
            try:
                if not self.bridge or not self.bridge.is_browser_alive():
                    logger.info("UYAP tarayıcısı aranıyor / bağlanılıyor...")
                    if not self.connect_bridge():
                        logger.warning("UYAP bağlantısı kurulamadı. 60 sn sonra tekrar denenecek.")
                        if once:
                            break
                        time.sleep(60)
                        continue

                # 1. Oturum nabzı
                self.heartbeat()

                # 2. V.I.P. ŞERİT: Derdest açık dosyaların evrak kontrolü (Yeni evrak anında yakalanır, indirilir ve Drive'a aktarılır)
                if self.config.get("check_open_cases", True):
                    stats = self.scan_open_cases()
                    yeni_sayisi = stats.get("new_downloaded", 0) if isinstance(stats, dict) else stats
                    if yeni_sayisi > 0:
                        logger.info("🔔 V.I.P. Nöbetçi: %d adet taze evrak yakalandı ve Google Drive'a yüklendi!", yeni_sayisi)

                # 3. Duruşma kontrolü (Önümüzdeki 7 gün)
                self.check_upcoming_hearings()

                # 4. Canlı Duruşma, Yasal Süre, Ara Karar ve Portal İşlemlerim Analizi
                self.sync_intel_and_deadlines(force=once)

                # 5. ARŞİV EŞİTLEME ŞERİDİ: Kalan 506 bin evrakı kesin HUKUKİ ÖNEM sırasına göre Google Drive'a pompala
                if self.config.get("auto_download_missing", True):
                    eksikler = self.reconcile_missing_docs(max_batch=50)
                    if eksikler > 0:
                        logger.info("📦 Öncelikli Arşiv Eşitleme: %d evrak Google Drive'a aktarıldı.", eksikler)

                if once:
                    logger.info("Tek seferlik nöbetçi kontrolü (--once) tamamlandı.")
                    break

                # Kalan arşiv evrak kontrolü
                cur_rem = self.katalog.db.execute(
                    "SELECT COUNT(*) FROM evrak WHERE durum NOT IN ('indirildi', 'mukerrer') AND (pdf_path IS NULL OR pdf_path = '')"
                )
                kalan_evrak = cur_rem.fetchone()[0]

                if kalan_evrak > 0:
                    logger.info("⏳ UYAP Arşiv Eşitlemesi Devam Ediyor: Kalan %d evrak önem sırasıyla indiriliyor (Sonraki paket 3 sn)...", kalan_evrak)
                    time.sleep(3.0)
                else:
                    logger.info("✨ Tüm UYAP arşivi Google Drive ile %100 eşitlendi! Tam Nöbetçi Bekleme Modu (%d dakika)...", self.config.get("interval_minutes", 15))
                    time.sleep(interval_s)

            except KeyboardInterrupt:
                logger.info("Nöbetçi kullanıcı tarafından durduruldu.")
                break
            except Exception as e:
                logger.error("Nöbetçi döngü hatası: %s", e)
                if once:
                    break
                time.sleep(10)


# ---------------------------------------------------------------------------
# CLI & Kurulum Menüsü
# ---------------------------------------------------------------------------
def interactive_setup() -> None:
    print("=" * 65)
    print("  UYAP Watcher / Telegram Yapılandırma Sihirbazı")
    print("=" * 65)
    cfg = load_config()

    print("\n1) Telegram Bot Token:")
    print("   (Telegram'da @BotFather üzerinden oluşturulan bot token'ı)")
    t = input(f"   Token [{cfg.get('telegram_token', '')}]: ").strip()
    if t:
        cfg["telegram_token"] = t

    print("\n2) Telegram Chat ID:")
    print("   (Kendi kullanıcı ID'niz veya mesajların gideceği grup ID'si)")
    print("   (Öğrenmek için Telegram'da @userinfobot botuna /start yazabilirsiniz)")
    c = input(f"   Chat ID [{cfg.get('telegram_chat_id', '')}]: ").strip()
    if c:
        cfg["telegram_chat_id"] = c

    print("\n3) Kontrol Sıklığı (Dakika):")
    inv = input(f"   Dakika [{cfg.get('interval_minutes', 30)}]: ").strip()
    if inv and inv.isdigit():
        cfg["interval_minutes"] = int(inv)

    print("\n4) Google Drive Yedekleme Klasörü (Opsiyonel):")
    print("   (Örn: G:\\Drive'ım\\UYAP_Arsiv veya boş bırakabilirsiniz)")
    drv = input(f"   Klasör [{cfg.get('google_drive_dir', '')}]: ").strip()
    if drv:
        cfg["google_drive_dir"] = drv

    save_config(cfg)
    print("\n[✓] Ayarlar kaydedildi!")

    if cfg.get("telegram_token") and cfg.get("telegram_chat_id"):
        print("\n[*] Telegram test mesajı gönderiliyor...")
        tg = TelegramClient(cfg["telegram_token"], cfg["telegram_chat_id"])
        if tg.send_message("🔔 <b>Tebrikler!</b> UYAP Nöbetçi Bot bağlantısı başarıyla kuruldu."):
            print("[✓] Test mesajı Telegram'a ulaştı!")
        else:
            print("[!] Test mesajı gönderilemedi. Token ve Chat ID'yi kontrol ediniz.")


def main():
    parser = argparse.ArgumentParser(description="UYAP Nöbetçi Bot & Arka Plan İzleyici")
    parser.add_argument("--setup", action="store_true", help="Telegram ve nöbetçi ayarlarını yap")
    parser.add_argument("--test-telegram", action="store_true", help="Telegram bağlantısını test et")
    parser.add_argument("--once", action="store_true", help="Tek bir tarama turu yap, raporla ve çık")
    parser.add_argument("--interval", type=int, default=None, help="Kontrol aralığı (dakika)")
    parser.add_argument("--drive-dir", type=str, default=None, help="Google Drive hedef klasörü")
    parser.add_argument("--tamamla", action="store_true", help="Katalogdaki tüm eksik evrakları sırayla indirip Drive'a eşitler")
    parser.add_argument("--no-tamamla", action="store_true", help="Eksik evrak tamamlama döngüsünü devre dışı bırakır")
    args = parser.parse_args()

    if args.setup:
        interactive_setup()
        return

    cfg = load_config()
    if args.interval:
        cfg["interval_minutes"] = args.interval
    if args.drive_dir:
        cfg["google_drive_dir"] = args.drive_dir
    if args.tamamla:
        cfg["auto_download_missing"] = True
    elif args.no_tamamla:
        cfg["auto_download_missing"] = False

    if args.test_telegram:
        tg = TelegramClient(cfg.get("telegram_token", ""), cfg.get("telegram_chat_id", ""))
        if not tg.is_configured:
            print("[!] Telegram henüz yapılandırılmamış. Lütfen 'python uyap_watcher.py --setup' çalıştırın.")
            return
        if tg.send_message("🔔 <b>UYAP Test Bildirimi:</b> Telegram bağlantısı aktiftir."):
            print("[✓] Test mesajı başarıyla iletildi!")
        else:
            print("[!] Test mesajı gönderilemedi.")
        return

    watcher = UyapWatcher(cfg)
    watcher.run_loop(once=args.once)


if __name__ == "__main__":
    main()
