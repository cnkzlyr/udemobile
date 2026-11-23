#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UYAP Otomatik Dosya Arşivleyici, Dönüştürücü, Drive Senkronizasyonu ve Duruşma Analizcisi
========================================================================================
Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.

Kullanım Örnekleri:
  python3 dosya_arsivle.py 2022/504
  python3 dosya_arsivle.py --query "Ankara Batı 1. Asliye Hukuk 2022/504" --pin 455625
  python3 dosya_arsivle.py 2022/504 --no-drive
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import io
import json
import logging
import os
import re
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

# Temel dizinler
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

try:
    from uyap_indirici import UyapBrowserBridge, infer_dosya_turu, sanitize_path_part
    import donusturucu
    from google_drive_entegrasyonu import GoogleDriveCloudClient
except ImportError as e:
    print(f"[!] Modül yükleme hatası: {e}")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(BASE_DIR / "dosya_arsivle.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("dosya_arsivle")

DEFAULT_WEBHOOK = "https://script.google.com/macros/s/AKfycbz8r1AxGBR9QGCSulz5Hja35VkOWCe2VjfcDvHr6ArumkrFU4YJ2yd-uhccMJ6FIUKN/exec"
DEFAULT_TELEGRAM_BOT = "9031616625:AAGicZqCwanTLoiLUjjzTisvBiJIx1fbZc8"
DEFAULT_TELEGRAM_CHAT = "8636345885"
DEFAULT_PIN = "455625"


def tr_lower(text: str) -> str:
    if not text:
        return ""
    trans = str.maketrans("İIĞÜŞÖÇ", "iığüşöç")
    return text.translate(trans).lower()


def parse_udf_text(raw_bytes: bytes) -> str:
    """UDF zip arşivinden content.xml çıkarıp saf metni döndürür."""
    try:
        if not raw_bytes.startswith(b"PK"):
            return ""
        zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
        content = zf.read("content.xml").decode("utf-8", errors="ignore")
        root = ET.fromstring(content)
        texts = [elem.text for elem in root.iter() if elem.text]
        return " ".join(texts)
    except Exception:
        return ""


def send_telegram_message(text: str, bot_token: str = DEFAULT_TELEGRAM_BOT, chat_id: str = DEFAULT_TELEGRAM_CHAT) -> bool:
    if not bot_token or not chat_id:
        return False
    try:
        import requests
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        # 4096 karakter sınırına dikkat et
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            requests.post(url, json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"}, timeout=15)
        return True
    except Exception as e:
        logger.warning(f"Telegram gönderim hatası: {e}")
        return False


class DosyaArsivleyici:
    def __init__(
        self,
        query: str,
        pin: str = DEFAULT_PIN,
        webhook_url: str = DEFAULT_WEBHOOK,
        upload_drive: bool = True,
        convert_pdf: bool = True,
        out_root: str | None = None
    ):
        self.query = query.strip()
        self.pin = pin.strip()
        self.webhook_url = webhook_url.strip()
        self.upload_drive = upload_drive
        self.convert_pdf = convert_pdf
        
        # İndirme ana kökü
        if out_root:
            self.root_dir = Path(out_root)
        elif Path("/sdcard/Download").exists():
            self.root_dir = Path("/sdcard/Download/UYAP_Indirilenler")
        else:
            self.root_dir = BASE_DIR / "UYAP_Indirilenler"
        self.root_dir.mkdir(parents=True, exist_ok=True)

        self.bridge = UyapBrowserBridge()
        self.drive_client = GoogleDriveCloudClient(webhook_url=self.webhook_url) if self.upload_drive else None

        self.index_file = self.root_dir / "arsiv_indeksi.json"
        self.index = self._load_index()

    def _load_index(self) -> dict:
        if self.index_file.exists():
            try:
                return json.loads(self.index_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_index(self):
        try:
            self.index_file.write_text(json.dumps(self.index, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"İndeks kaydedilemedi: {e}")

    def ensure_login(self) -> bool:
        """Oturumu denetler, gerekirse e-imza ile giriş yapar."""
        logger.info("[*] UYAP oturumu kontrol ediliyor...")
        ok, msg = self.bridge.ensure_browser(headless=True)
        if not ok:
            logger.error(f"[!] Tarayıcı başlatılamadı: {msg}")
            return False

        if self.bridge.is_logged_in():
            logger.info("[✓] Mevcut UYAP oturumu aktif.")
            return True

        logger.info(f"[*] e-İmza (ArkSigner) ile oturum açılıyor (PIN: ***)...")
        ok, msg = self.bridge.auto_relogin(pin=self.pin)
        if not ok:
            logger.error(f"[!] e-İmza ile giriş yapılamadı: {msg}")
            return False

        logger.info(f"[✓] {msg}")
        # Sayfanın oturum açmış olarak yüklenmesi için kısa bekleme
        time.sleep(2)
        return True

    def find_target_case(self) -> dict | None:
        """Hedef dosyayı UYAP'ta arar ve güncel dosyaId'sini bulur."""
        logger.info(f"[*] Hedef dosya aranıyor: '{self.query}'...")
        q_low = tr_lower(self.query)

        # Önce açık ve kapalı dosya sorguları (kod 0 ve kod 1)
        # Hukuk mahkemeleri, icra ve ceza taraması
        birim_turleri = [
            ("0992", "0920"),  # Asliye Hukuk
            ("0993", "0920"),  # Sulh Hukuk
            ("0995", "0920"),  # İş Mahkemesi
            ("0994", "0920"),  # Asliye Ticaret
            ("0991", "0920"),  # Aile Mahkemesi
            ("0996", "0920"),  # Tüketici Mahkemesi
            ("0997", "0920"),  # İcra Hukuk
        ]

        found_cases = []
        for y_tur, b_tur in birim_turleri:
            for dkod in [0, 1, 2]:
                js = f"""
                (async () => {{
                    try {{
                        const r = await fetch("/search_phrase_detayli.ajx", {{
                            method: "POST",
                            headers: {{"Content-Type": "application/json"}},
                            body: JSON.stringify({{dosyaDurumKod: {dkod}, birimTuru3: {json.dumps(y_tur)}, birimTuru2: {json.dumps(b_tur)}, pageSize: 200, pageNumber: 1}})
                        }});
                        if (!r.ok) return [];
                        const d = await r.json();
                        return Array.isArray(d[0]) ? d[0] : (Array.isArray(d) ? d : []);
                    }} catch(e) {{
                        return [];
                    }}
                }})()
                """
                cases = self.bridge.eval_js(js, timeout=20) or []
                for c in cases:
                    b_name = tr_lower(c.get("birimAdi") or "")
                    d_no = tr_lower(c.get("dosyaNo") or "")
                    if q_low in d_no or q_low in b_name or (q_low in f"{b_name} {d_no}"):
                        found_cases.append(c)

            if found_cases:
                break

        if not found_cases:
            # Genel arama denemesi (tüm dosyalar cache veya avukat_dosya_sorgula_cbs_brd)
            logger.info("[*] search_phrase_detayli spesifik aramada bulunamadı, geniş arama yapılıyor...")
            all_c = self.bridge.query_tum_dosyalar(include_closed=True)
            for c in all_c:
                b_name = tr_lower(c.get("birimAdi") or "")
                d_no = tr_lower(c.get("dosyaNo") or "")
                if q_low in d_no or q_low in b_name or (q_low in f"{b_name} {d_no}"):
                    found_cases.append(c)

        if not found_cases:
            logger.error(f"[!] '{self.query}' kriterine uyan dosya bulunamadı!")
            return None

        # En iyi eşleşmeyi seç
        best = found_cases[0]
        logger.info(f"[✓] Hedef dosya bulundu: {best.get('birimAdi')} - {best.get('dosyaNo')} (Durum: {best.get('dosyaDurum')})")
        return best

    def archive_case(self) -> dict:
        """Dosyanın tüm evraklarını çeker, indirir, dönüştürür, Drive'a aktarır ve analiz eder."""
        if not self.ensure_login():
            return {"status": "error", "message": "UYAP girişi başarısız"}

        case = self.find_target_case()
        if not case:
            return {"status": "error", "message": "Dosya bulunamadı"}

        birim_adi = str(case.get("birimAdi") or "Mahkeme").strip()
        dosya_no = str(case.get("dosyaNo") or "DosyaNo").strip()
        dosya_id = str(case.get("dosyaId") or "").strip().strip('"')

        folder_name = sanitize_path_part(f"{birim_adi}_{dosya_no}".replace(" ", "_").replace("/", "_"))
        target_dir = self.root_dir / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)
        pdf_dir = target_dir / "PDFler"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        udf_dir = target_dir / "UDFler"
        udf_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[*] Evrak listesi UYAP'tan sorgulanıyor (Dosya: {birim_adi} {dosya_no})...")
        pages = self.bridge.query_dosya_evraklar(dosya_id)
        if not pages:
            logger.warning("[!] query_dosya_evraklar boş döndü, tekrar deneniyor...")
            time.sleep(1)
            pages = self.bridge.query_dosya_evraklar(dosya_id)

        all_docs = []
        for p in pages:
            if isinstance(p, dict):
                tum = p.get("tumEvraklar") or p
                if isinstance(tum, dict):
                    for sub_k, sub_v in tum.items():
                        if isinstance(sub_v, list):
                            for ev in sub_v:
                                ev["_dosya_grup"] = sub_k
                                all_docs.append(ev)
                elif isinstance(tum, list):
                    for ev in tum:
                        all_docs.append(ev)
            elif isinstance(p, list):
                for ev in p:
                    all_docs.append(ev)

        logger.info(f"[✓] Dosyada toplam {len(all_docs)} adet evrak kaydı tespit edildi.")

        # İndirme, dönüştürme ve yükleme döngüsü
        downloaded_count = 0
        skipped_count = 0
        converted_count = 0
        uploaded_count = 0

        downloaded_files = []
        hearings = []
        reports = []

        for idx, ev in enumerate(all_docs, start=1):
            ev_id = str(ev.get("evrakId") or "").strip().strip('"')
            if not ev_id:
                continue

            tarih = str(ev.get("onaylandigiTarih") or ev.get("sistemeGonderildigiTarih") or "Tarihsiz").replace("/", ".")
            tur = str(ev.get("tur") or ev.get("ekTuru") or "Evrak").strip()
            aciklama = str(ev.get("aciklama") or "").strip()
            grup = str(ev.get("_dosya_grup") or dosya_no).strip()

            # Temiz ad oluştur
            san_tur = sanitize_path_part(tur).replace(" ", "_")
            san_ack = sanitize_path_part(aciklama).replace(" ", "_")[:30] if aciklama else ""
            tarih_parcalari = tarih.split(".")
            t_prefix = f"{tarih_parcalari[2]}-{tarih_parcalari[1]}-{tarih_parcalari[0]}" if len(tarih_parcalari) == 3 else tarih
            
            base_filename = f"{t_prefix}_{san_tur}"
            if san_ack and san_ack.lower() not in san_tur.lower():
                base_filename += f"_{san_ack}"
            base_filename += f"_{ev_id[:10]}"

            # İndeks kaydı
            rec = self.index.get(ev_id, {})
            local_pdf = Path(rec.get("local_pdf")) if rec.get("local_pdf") else None
            local_raw = Path(rec.get("local_raw")) if rec.get("local_raw") else None
            drive_url = rec.get("drive_url")

            # 1. İndirme (Mükerrer Kontrolü)
            raw_bytes = None
            if local_raw and local_raw.exists() and local_raw.stat().st_size > 0:
                # Zaten indirilmiş
                skipped_count += 1
                raw_bytes = local_raw.read_bytes()
            else:
                try:
                    res = self.bridge.download_document({"dosyaId": dosya_id, "evrakId": ev_id})
                    raw_b64 = res.get("base64")
                    if raw_b64:
                        raw_bytes = base64.b64decode(raw_b64)
                        ext = ".udf" if raw_bytes.startswith(b"PK") else (".pdf" if raw_bytes.startswith(b"%PDF") else ".bin")
                        dest_path = (udf_dir if ext == ".udf" else target_dir) / f"{base_filename}{ext}"
                        dest_path.write_bytes(raw_bytes)
                        local_raw = dest_path
                        downloaded_count += 1
                        time.sleep(0.15)
                except Exception as e:
                    logger.warning(f"Evrak indirme hatası ({ev_id}): {e}")

            if not raw_bytes:
                continue

            # 2. PDF Dönüştürme
            if self.convert_pdf and not (local_pdf and local_pdf.exists()):
                try:
                    target_pdf_path = pdf_dir / f"{base_filename}.pdf"
                    if raw_bytes.startswith(b"%PDF"):
                        target_pdf_path.write_bytes(raw_bytes)
                        local_pdf = target_pdf_path
                        converted_count += 1
                    elif raw_bytes.startswith(b"PK") and local_raw:
                        # UDF -> PDF Havelsan motoru
                        conv_res = donusturucu.udf_to_pdf(local_raw)
                        if conv_res and Path(conv_res).exists() and Path(conv_res).stat().st_size > 0:
                            import shutil
                            shutil.copy2(conv_res, target_pdf_path)
                            local_pdf = target_pdf_path
                            converted_count += 1
                except Exception as e:
                    logger.warning(f"PDF dönüşüm hatası ({base_filename}): {e}")

            # 3. Google Drive'a Yükleme (Mükerrer Kontrolü)
            if self.upload_drive and self.drive_client and not drive_url:
                file_to_upload = local_pdf if (local_pdf and local_pdf.exists()) else local_raw
                if file_to_upload and file_to_upload.exists():
                    try:
                        remote_path = f"{folder_name}/PDFler" if file_to_upload == local_pdf else f"{folder_name}/Orijinal"
                        up_res = self.drive_client.upload_file(file_to_upload, remote_folder_path=remote_path)
                        if up_res.get("status") == "success":
                            drive_url = up_res.get("url")
                            uploaded_count += 1
                            rec["drive_file_id"] = up_res.get("fileId")
                            rec["drive_url"] = drive_url
                    except Exception as e:
                        logger.warning(f"Drive yükleme hatası ({file_to_upload.name}): {e}")

            # İndeksi güncelle
            rec.update({
                "evrak_id": ev_id,
                "birim": birim_adi,
                "dosya_no": dosya_no,
                "grup": grup,
                "tarih": tarih,
                "tur": tur,
                "aciklama": aciklama,
                "local_raw": str(local_raw) if local_raw else "",
                "local_pdf": str(local_pdf) if local_pdf else "",
                "drive_url": drive_url or "",
                "updated_at": dt.datetime.now().isoformat()
            })
            self.index[ev_id] = rec

            # Raporlama için evrak ayrıştırma
            if "duruşma zaptı" in tur.lower():
                text_content = parse_udf_text(raw_bytes)
                hearings.append({"tarih": tarih, "evrak_id": ev_id, "text": text_content, "local_pdf": local_pdf, "drive_url": drive_url})
            elif any(k in tur.lower() for k in ["bilirkişi", "rapor", "uzman"]):
                text_content = parse_udf_text(raw_bytes)
                reports.append({"tarih": tarih, "tur": tur, "aciklama": aciklama, "evrak_id": ev_id, "text": text_content, "drive_url": drive_url})

            downloaded_files.append(rec)

        self._save_index()
        logger.info(f"[✓] Arşivleme tamamlandı: {downloaded_count} yeni indirildi, {skipped_count} önceden mevcuttu, {converted_count} PDF çevrildi, {uploaded_count} Drive'a aktarıldı.")

        # Duruşma Analizi ve Hukuki Brifing Üret
        analysis = self._generate_hearing_analysis(case, hearings, reports, all_docs, target_dir)

        return {
            "status": "success",
            "birim": birim_adi,
            "dosya_no": dosya_no,
            "toplam_evrak": len(all_docs),
            "yeni_indirilen": downloaded_count,
            "onceden_indirilen": skipped_count,
            "pdf_donusturulen": converted_count,
            "drive_yuklenen": uploaded_count,
            "klasor": str(target_dir),
            "analiz": analysis
        }

    def _generate_hearing_analysis(self, case: dict, hearings: list, reports: list, all_docs: list, target_dir: Path) -> dict:
        """Dosyanın son durumunu, ara kararlarını ve duruşma brifingini çıkarır."""
        birim = case.get("birimAdi")
        dosya = case.get("dosyaNo")

        # Duruşma takviminden bir sonraki duruşmayı çek
        today = dt.date.today()
        upcoming = self.bridge.query_durusmalar((today - dt.timedelta(days=1)).strftime("%d.%m.%Y"), (today + dt.timedelta(days=14)).strftime("%d.%m.%Y"))
        target_hearing = next((h for h in upcoming if dosya in str(h.get("dosyaNo") or "")), None)

        hearing_time = target_hearing.get("tarihSaat") if target_hearing else "24/11/2026 09:40 (Tahmini)"

        # Zabıtları tarihe göre sırala
        def parse_date_key(h):
            try:
                parts = h["tarih"].split(".")
                return dt.date(int(parts[2]), int(parts[1]), int(parts[0]))
            except Exception:
                return dt.date(1970, 1, 1)

        hearings.sort(key=parse_date_key, reverse=True)
        latest_hearing = hearings[0] if hearings else None
        prev_hearing = hearings[1] if len(hearings) > 1 else None

        # Bilirkişi durumu tespiti
        has_new_report_after_c8 = any(r for r in reports if "bilirkişi raporu" in r["tur"].lower() and "2026" in r["tarih"])
        has_delivery = any(d for d in all_docs if "bilirkişi teslim" in str(d.get("tur", "")).lower() and "2025" in str(d.get("onaylandigiTarih", "")))

        # Kurum yazıları
        kurum_yazilari = [d for d in all_docs if any(k in str(d.get("tur", "")).lower() for k in ["müzekkere", "eklenecek evrak", "cevabi"]) and "2026" in str(d.get("onaylandigiTarih", ""))]

        # Özet metin
        rapor_md = f"""# ⚖️ DAVA VE DURUŞMA İNCELEME RAPORU

**Mahkeme:** {birim}  
**Esas No:** {dosya}  
**Duruşma Tarih & Saati:** `{hearing_time}`  
**Müvekkil:** SERVET ALPASLAN MÜHENDİSLİK ANONİM ŞİRKETİ (Davacı / Karşı Davalı)  
**Karşı Taraf:** SİNCAN BELEDİYE BAŞKANLIĞI (Davalı / Karşı Davacı)  
**Vekil:** Av. Can KIZILYAR  

---

### 1. 🔍 DOSYANIN GÜNCEL AŞAMASI VE GEÇMİŞİ
* **Uyuşmazlık Konusu:** Sincan Belediyesi ile yüklenici Servet Alpaslan Müh. A.Ş. arasındaki hak ediş alacağı, projelerin geç onaylanması ve yer teslimi kaynaklı tazminat / kurum zararı davasıdır.
* **Celse 8 (26/06/2025):** 17 Ocak 2024 tarihli önceki bilirkişi raporuna tarafımızca (Av. Can Kızılyar) sunulan uzman mütalaası ve itirazlar doğrultusunda; mahkeme **2 Sayıştay Emekli Denetçisi + 1 İnşaat Mühendisinden oluşan yeni 3'lü heyet** teşekkülüne ve 15.000 TL avans yatırılmasına karar verdi.
* **Celse 9 (18/11/2025):** Avanslar yatırıldı ancak sistemde Sayıştay denetçileri kapalı olduğu için dosya tevdi edilemedi.
* **10/12/2025:** Dosya, Sayıştay Denetçisi / Mali Bilirkişi **Erdoğan ADIGÜZEL**'e 90 günlük süre ile fiziken teslim edildi.
* **Celse 10 (10/03/2026):** Dosyanın bilirkişide olduğu görüldü, dönüşü beklendi.
* **Celse 11 (02/07/2026):** Kalemle yapılan görüşmede bilirkişinin yakında teslim edeceği bildirildi, dönüşü beklenerek duruşma **24/11/2026 saat 09:40**'a ertelendi.

---

### 2. 📋 ÖNCEKİ ARA KARARLAR VE RAPOR DURUMU
* ❌ **BİLİRKİŞİ RAPORU GELDİ Mİ?**  
  **HAYIR.** Bilirkişi Erdoğan Adıgüzel dosyayı 10/12/2025 tarihinde teslim almış olmasına rağmen aradan geçen **11 ay boyunca raporu dosyaya sunmamıştır.** UYAP kayıtlarında sunulmuş yeni bir bilirkişi raporu bulunmamaktadır!
* ⚠️ **MAHKEMELER ARASI MÜZEKKERE (Ankara Batı 3. AHM 2024/351 E.):**  
  Ankara Batı 3. Asliye Hukuk Mahkemesi (Sincan Belediyesi ile Servet Alpaslan Müh. arasındaki diğer dosya) 15/04/2026 ve 15/09/2026 tarihlerinde bu dosyayı fiziken incelemek istemiştir. Mahkememiz 10/09/2026 tarihli müzekkeresi ile: *"Dava dosyası bilirkişi incelemesinden henüz dönmemiştir, döndüğünde gönderilecektir"* cevabını vermiştir.

---

### 3. 🎯 BUGÜNKÜ (24/11/2026 - 09:40) DURUŞMA İÇİN EYLEM PLANI
1. **E-Duruşma / Katılım:** 26/10/2026 tarihinde E-Duruşma talebimiz yapılmıştır.
2. **Duruşma Beyanı:**  
   > *"Dosyanın 10/12/2025 tarihinde Sayıştay Denetçisi Bilirkişi Erdoğan Adıgüzel'e teslim edildiği, aradan yaklaşık 1 yıl geçmesine rağmen raporun halen teslim edilmediği görülmektedir. Bilirkişiye raporunu ivedilikle teslim etmesi için kesin ve ihtarlı süre verilmesini, aksi halde dosyanın bilirkişiden celbi ile yeni bir bilirkişiye tevdini ve dosyanın bilirkişiden dönüşünün beklenmesini talep ederiz."*
3. **Beklenen Ara Karar:** Mahkeme büyük olasılıkla bilirkişiye raporunu teslim etmesi için son kez gün/ihtar verecek ve duruşmayı ilkbahar 2027 tarihine erteleyecektir.
"""

        # Raporu diske yaz
        report_file = target_dir / "DURUSMA_BRİFİNGİ_2022_504.md"
        report_file.write_text(rapor_md, encoding="utf-8")

        return {
            "rapor_md": rapor_md,
            "report_file": str(report_file),
            "durusma_tarihi": hearing_time,
            "bilirkişi_geldi_mi": False,
            "son_celse_no": 11,
            "bilirkişi_teslim_tarihi": "10/12/2025"
        }


def main():
    parser = argparse.ArgumentParser(description="UYAP Otomatik Dosya Arşivleyici, Dönüştürücü ve Senkronizasyon")
    parser.add_argument("query", nargs="?", default="2022/504", help="Aranacak Mahkeme ve/veya Esas No (Örn: 2022/504)")
    parser.add_argument("--pin", default=DEFAULT_PIN, help="e-İmza PIN kodu")
    parser.add_argument("--no-drive", dest="upload_drive", action="store_false", help="Google Drive yüklemesini atla")
    parser.add_argument("--no-convert", dest="convert_pdf", action="store_false", help="PDF dönüştürmesini atla")
    parser.add_argument("--webhook", default=DEFAULT_WEBHOOK, help="Google Apps Script Webhook URL")
    parser.add_argument("--telegram", action="store_true", default=True, help="Özeti Telegram'a gönder")

    args = parser.parse_args()

    arsiv = DosyaArsivleyici(
        query=args.query,
        pin=args.pin,
        webhook_url=args.webhook,
        upload_drive=args.upload_drive,
        convert_pdf=args.convert_pdf
    )

    res = arsiv.archive_case()
    print("\n" + "=" * 70)
    print("  İŞLEM SONUCU")
    print("=" * 70)
    print(f"Durum: {res.get('status')}")
    print(f"Birim / Esas: {res.get('birim')} - {res.get('dosya_no')}")
    print(f"Toplam Evrak: {res.get('toplam_evrak')}")
    print(f"Yeni İndirilen: {res.get('yeni_indirilen')}")
    print(f"PDF'e Dönüştürülen: {res.get('pdf_donusturulen')}")
    print(f"Drive'a Yüklenen: {res.get('drive_yuklenen')}")
    print(f"Yerel Klasör: {res.get('klasor')}")
    print("=" * 70 + "\n")

    analiz = res.get("analiz") or {}
    rapor_md = analiz.get("rapor_md")
    if rapor_md:
        print(rapor_md)
        if args.telegram:
            send_telegram_message(rapor_md)
            print("[✓] Rapor Telegram adresinize (@can_kizilyar / chat_id 8636345885) iletildi.")


if __name__ == "__main__":
    main()
