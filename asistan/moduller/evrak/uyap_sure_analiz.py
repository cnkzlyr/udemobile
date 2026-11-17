# -*- coding: utf-8 -*-
"""
UYAP Süre, Görev ve Duruşma Analiz Yöneticisi
(c) 2026 Av. Can KIZILYAR - Tüm hakları saklıdır.

Bu modül:
1. Tebligatları (PTT ve UETS) tarar, yasal süreleri hesaplar (İstinaf: 2 hafta, Bilirkişi: 2 hafta, İcra: 7 gün).
2. Yaklaşan duruşmaları ve duruşma zaptı ara kararlarındaki kesin süreleri çıkarır.
3. Görev ve süreleri 'gorev_sure' tablosunda tutar.
4. Kalan günü hesaplayarak yaklaşan süreler için Telegram bildirimleri üretir.
5. GUI ve CLI'da anlık geri sayım (chip/badge) verilerini sunar.
"""

import os
import sys
import re
import json
import sqlite3
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger("UyapSureAnaliz")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] (SureAnaliz) %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "uyap_katalog.db"))


def get_db_connection(db_path: str = DB_PATH, timeout: float = 60.0) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def init_sure_tables(db_path: str = DB_PATH):
    """gorev_sure tablosunu oluşturur."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS gorev_sure (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dkey TEXT NOT NULL,
        birim TEXT,
        dosya_no TEXT,
        kaynak_turu TEXT,
        kaynak_id TEXT,
        gorev_baslik TEXT,
        aciklama TEXT,
        teblig_tarihi TEXT,
        son_tarih TEXT,
        kalan_gun INTEGER,
        oncelik TEXT,
        durum TEXT DEFAULT 'BEKLIYOR',
        telegram_bildirildi INTEGER DEFAULT 0,
        kayit_tarihi TEXT,
        UNIQUE(dkey, kaynak_turu, gorev_baslik, son_tarih) ON CONFLICT REPLACE
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gorev_son_tarih ON gorev_sure(son_tarih)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gorev_durum ON gorev_sure(durum)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gorev_dkey ON gorev_sure(dkey)")
    conn.commit()
    conn.close()


def parse_any_date(date_str: str) -> date | None:
    """Farklı biçimlerdeki tarih dizgilerini parse eder."""
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip().split()[0]  # saat varsa at
    formats = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    return None


class UyapSureAnalizManager:
    """Tebligat ve duruşma sürelerini analiz edip görevleri yöneten sınıf."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        init_sure_tables(self.db_path)

    def scan_tebligat_sureleri(self) -> int:
        """Tebligat tablosunu tarayarak yasal süreleri hesaplar ve gorev_sure tablosuna yazar."""
        conn = get_db_connection(self.db_path)
        cur = conn.cursor()

        # Tebliğ tarihi olan tebligatları çek
        cur.execute("""
        SELECT barkod_delil, dkey, birim, dosya_no, muvekkil, muhatap, tebligat_turu, 
               gonderim_tarihi, teblig_tarihi, durum
        FROM tebligat 
        WHERE teblig_tarihi IS NOT NULL AND teblig_tarihi != ''
        """)
        rows = cur.fetchall()

        today = date.today()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        added = 0

        for r in rows:
            t_tarih = parse_any_date(r["teblig_tarihi"])
            if not t_tarih:
                continue

            tur = (r["tebligat_turu"] or "").lower()
            birim = r["birim"] or ""
            dosya_no = r["dosya_no"] or ""
            dkey = r["dkey"] or f"{birim}-{dosya_no}"
            barkod = r["barkod_delil"] or ""

            # Yasal süre ve görev türü belirleme
            gun_ekle = 14
            gorev_baslik = "Tebligata Karşı Hukuki Süre"
            oncelik = "NORMAL"

            if "karar" in tur or "gerekçeli" in tur:
                gun_ekle = 14  # 2 hafta istinaf
                gorev_baslik = "İstinaf / Kanun Yolu Başvuru Süresi"
                oncelik = "YUKSEK"
            elif "bilirkişi" in tur or "rapor" in tur:
                gun_ekle = 14  # 2 hafta itiraz
                gorev_baslik = "Bilirkişi Raporuna İtiraz / Beyan Süresi"
                oncelik = "YUKSEK"
            elif "ödeme emri" in tur or "icra" in tur or "icra" in birim.lower():
                gun_ekle = 7   # 7 gün itiraz ve mal beyanı
                gorev_baslik = "İcra Ödeme Emrine İtiraz / Mal Beyanı"
                oncelik = "ACIL"
            elif "dava dilekçesi" in tur or "tensip" in tur:
                gun_ekle = 14  # 2 hafta cevap
                gorev_baslik = "Dava Dilekçesine Cevap Verme Süresi"
                oncelik = "YUKSEK"
            elif "ihtiyati" in tur:
                gun_ekle = 7
                gorev_baslik = "İhtiyati Tedbir/Haciz İtiraz Süresi"
                oncelik = "ACIL"

            son_tarih_dt = t_tarih + timedelta(days=gun_ekle)
            kalan = (son_tarih_dt - today).days

            # Öncelik ayarlaması (son 3 gün acil)
            if kalan <= 2 and kalan >= 0:
                oncelik = "ACIL"
            elif kalan <= 5 and kalan > 2:
                oncelik = "YUKSEK"

            durum = "BEKLIYOR"
            if kalan < 0:
                durum = "SURESI_DOLDU"

            aciklama = f"Tebliğ Tarihi: {t_tarih.strftime('%d.%m.%Y')} | Evrak Türü: {r['tebligat_turu'] or 'Tebligat'} | Muhatap: {r['muhatap'] or ''}"

            cur.execute("""
            INSERT OR REPLACE INTO gorev_sure
            (dkey, birim, dosya_no, kaynak_turu, kaynak_id, gorev_baslik, aciklama, teblig_tarihi,
             son_tarih, kalan_gun, oncelik, durum, kayit_tarihi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dkey, birim, dosya_no, "TEBLIGAT", barkod,
                gorev_baslik, aciklama, t_tarih.strftime("%Y-%m-%d"),
                son_tarih_dt.strftime("%Y-%m-%d"), kalan, oncelik, durum, now_str
            ))
            added += 1

        conn.commit()
        conn.close()
        logger.info(f"Tebligat analizinden {added} adet yasal süre kaydı işlendi.")
        return added

    def scan_durusma_gorevleri(self) -> int:
        """Duruşma tablosunu tarayarak yaklaşan duruşmaları görev olarak işler."""
        conn = get_db_connection(self.db_path)
        cur = conn.cursor()

        cur.execute("SELECT id, dkey, birim, dosya_no, tarih, saat, yer, aciklama, durum FROM durusma")
        rows = cur.fetchall()

        today = date.today()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        added = 0

        for r in rows:
            d_tarih = parse_any_date(r["tarih"])
            if not d_tarih:
                continue

            kalan = (d_tarih - today).days
            oncelik = "NORMAL"
            if kalan <= 2 and kalan >= 0:
                oncelik = "ACIL"
            elif kalan <= 7 and kalan > 2:
                oncelik = "YUKSEK"

            durum = "BEKLIYOR"
            if kalan < 0:
                durum = "TAMAMLANDI"

            birim = r["birim"] or ""
            dosya_no = r["dosya_no"] or ""
            dkey = r["dkey"] or f"{birim}-{dosya_no}"
            saat = r["saat"] or ""
            yer = r["yer"] or ""

            gorev_baslik = f"Duruşma: {birim} - {dosya_no}"
            aciklama = f"Tarih/Saat: {d_tarih.strftime('%d.%m.%Y')} {saat} | Salon/Yer: {yer} | {r['aciklama'] or ''}".strip()

            cur.execute("""
            INSERT OR REPLACE INTO gorev_sure
            (dkey, birim, dosya_no, kaynak_turu, kaynak_id, gorev_baslik, aciklama, teblig_tarihi,
             son_tarih, kalan_gun, oncelik, durum, kayit_tarihi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dkey, birim, dosya_no, "DURUSMA_GUNU", str(r["id"]),
                gorev_baslik, aciklama, "",
                d_tarih.strftime("%Y-%m-%d"), kalan, oncelik, durum, now_str
            ))
            added += 1

        conn.commit()
        conn.close()
        logger.info(f"Duruşma takviminden {added} adet duruşma görevi işlendi.")
        return added

    def scan_durusma_zapti_metinleri(self) -> int:
        """İndirilen duruşma tutanaklarındaki kesin süre ve ara kararları regex ile yakalar."""
        conn = get_db_connection(self.db_path)
        cur = conn.cursor()

        # Son indirilen duruşma zaptı evrakları
        cur.execute("""
        SELECT e.skey, e.dkey, d.birim, d.dosya_no, e.tarih, e.path, e.pdf_path
        FROM evrak e
        LEFT JOIN dosya d ON e.dkey = d.dkey
        WHERE (e.tur LIKE '%Duruşma%' OR e.tur LIKE '%Zapt%')
          AND ((e.pdf_path IS NOT NULL AND e.pdf_path != '') OR (e.path IS NOT NULL AND e.path != ''))
        ORDER BY e.tarih DESC LIMIT 100
        """)
        rows = cur.fetchall()

        today = date.today()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        added = 0

        # Regex desenleri
        kesin_sure_pat = re.compile(r"(\d+)\s*(hafta|gün|ay)\s*(?:lik)?\s*kesin\s*süre", re.IGNORECASE)
        gd_pat = re.compile(r"(?:G\.?\s*D\.?|GEREĞİ DÜŞÜNÜLDÜ)([\s\S]*?)(?:Katip|Hakim|$)", re.IGNORECASE)

        for r in rows:
            file_path = r["pdf_path"] or r["path"]
            if not file_path or not os.path.exists(file_path):
                continue

            content = ""
            # Text extraction for PDF
            if file_path.lower().endswith(".pdf"):
                try:
                    import pypdf
                    reader = pypdf.PdfReader(file_path)
                    for page in reader.pages[:5]:
                        content += (page.extract_text() or "") + "\n"
                except Exception:
                    pass

            if not content:
                continue

            matches = kesin_sure_pat.findall(content)
            if not matches:
                continue

            d_tarih = parse_any_date(r["tarih"]) or today
            birim = r["birim"] or ""
            dosya_no = r["dosya_no"] or ""
            dkey = r["dkey"] or f"{birim}-{dosya_no}"

            for m in matches:
                sayi = int(m[0])
                birim_zaman = m[1].lower()
                gun_ekle = sayi * 7 if "hafta" in birim_zaman else (sayi * 30 if "ay" in birim_zaman else sayi)

                son_dt = d_tarih + timedelta(days=gun_ekle)
                kalan = (son_dt - today).days

                gorev_baslik = f"Ara Karar Kesin Süre: {sayi} {birim_zaman.title()}"
                aciklama = f"Duruşma Zaptı Tarihi: {d_tarih.strftime('%d.%m.%Y')} | Dosya: {birim} - {dosya_no}"
                oncelik = "ACIL" if kalan <= 3 else "YUKSEK"
                durum = "BEKLIYOR" if kalan >= 0 else "SURESI_DOLDU"

                cur.execute("""
                INSERT OR REPLACE INTO gorev_sure
                (dkey, birim, dosya_no, kaynak_turu, kaynak_id, gorev_baslik, aciklama, teblig_tarihi,
                 son_tarih, kalan_gun, oncelik, durum, kayit_tarihi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    dkey, birim, dosya_no, "DURUSMA_ARAKARAR", r["skey"],
                    gorev_baslik, aciklama, d_tarih.strftime("%Y-%m-%d"),
                    son_dt.strftime("%Y-%m-%d"), kalan, oncelik, durum, now_str
                ))
                added += 1

        conn.commit()
        conn.close()
        logger.info(f"Duruşma zabıtları taranarak {added} adet kesin süre ara kararı çıkarıldı.")
        return added

    def fetch_and_sync_live_durusmalar(self, bridge=None, days_ahead: int = 60) -> int:
        """UYAP Portalından canlı duruşmaları çeker (30'ar günlük pencerelerle),
        hem 'durusma' tablosunu hem de 'gorev_sure' tablosunu günceller."""
        if not bridge:
            try:
                from uyap_indirici import UyapBrowserBridge
                bridge = UyapBrowserBridge(port=9223)
            except Exception as e:
                logger.warning(f"UYAP köprüsü başlatılamadı: {e}")
                return 0

        today = date.today()
        all_durusmalar = []
        step_days = 28  # 30 günden küçük güvenli aralık

        for chunk_start in range(0, days_ahead, step_days):
            d_from = today + timedelta(days=chunk_start)
            d_to = min(today + timedelta(days=days_ahead), d_from + timedelta(days=step_days - 1))
            start_str = d_from.strftime("%d.%m.%Y")
            end_str = d_to.strftime("%d.%m.%Y")

            js = f"""
            (async () => {{
                try {{
                    const resp = await fetch('/avukat_durusma_sorgula_brd.ajx', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            baslangicTarihi: {json.dumps(start_str)},
                            bitisTarihi: {json.dumps(end_str)}
                        }})
                    }});
                    return await resp.json();
                }} catch(e) {{
                    return {{error: String(e)}};
                }}
            }})()
            """
            res = bridge.eval_js(js)
            if isinstance(res, list):
                all_durusmalar.extend(res)

        if not all_durusmalar:
            logger.info("Planlanmış canlı duruşma bulunamadı.")
            return 0

        conn = get_db_connection(self.db_path)
        cur = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        added = 0

        for d in all_durusmalar:
            birim = d.get("yerelBirimAd") or d.get("birimAdi") or ""
            dosya_no = d.get("dosyaNo") or ""
            dkey = f"{birim}-{dosya_no}"
            tarih_saat = d.get("tarihSaat") or ""
            
            # 2026-11-17 09:20:00.0
            dt_parts = tarih_saat.split()
            t_str = dt_parts[0] if dt_parts else ""
            s_str = dt_parts[1][:5] if len(dt_parts) > 1 else ""
            
            d_date = parse_any_date(t_str)
            if not d_date:
                continue

            kalan = (d_date - today).days
            oncelik = "NORMAL"
            if kalan <= 1:
                oncelik = "ACIL"
            elif kalan <= 3:
                oncelik = "YUKSEK"
            elif kalan <= 7:
                oncelik = "YUKSEK"

            # 1. durusma tablosuna ekle
            cur.execute("""
            INSERT OR REPLACE INTO durusma (dkey, birim, dosya_no, tarih, saat, yer, aciklama, durum)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (dkey, birim, dosya_no, t_str, s_str, birim, f"İşlem: {d.get('islemTuruAciklama', 'Duruşma')} - {d.get('islemSonucuAciklama', '')}", "BEKLIYOR"))

            # 2. gorev_sure tablosuna ekle
            gorev_baslik = f"Duruşma: {birim} - {dosya_no} ({s_str})"
            aciklama = f"Tarih/Saat: {d_date.strftime('%d.%m.%Y')} Saat: {s_str} | Mahkeme: {birim}"

            cur.execute("""
            INSERT OR REPLACE INTO gorev_sure
            (dkey, birim, dosya_no, kaynak_turu, kaynak_id, gorev_baslik, aciklama, teblig_tarihi,
             son_tarih, kalan_gun, oncelik, durum, kayit_tarihi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dkey, birim, dosya_no, "DURUSMA_GUNU", str(d.get("kayitId", "")),
                gorev_baslik, aciklama, "",
                t_str, kalan, oncelik, "BEKLIYOR" if kalan >= 0 else "TAMAMLANDI", now_str
            ))
            added += 1

        conn.commit()
        conn.close()
        logger.info(f"Canlı UYAP takviminden {added} duruşma kaydedildi ve görevlere işlendi.")
        return added

    def scan_all(self, bridge=None):
        """Tüm süre, görev ve duruşma analizlerini topluca çalıştırır."""
        logger.info("Süre ve Görev Analizi Başlatılıyor...")
        t_count = self.scan_tebligat_sureleri()
        live_d_count = self.fetch_and_sync_live_durusmalar(bridge=bridge, days_ahead=60)
        d_count = self.scan_durusma_gorevleri()
        z_count = self.scan_durusma_zapti_metinleri()
        logger.info(f"Analiz tamamlandı: Toplam {t_count + live_d_count + d_count + z_count} görev güncellendi.")

    def get_yaklasan_gorevler(self, limit: int = 50, sadece_bekleyen: bool = True) -> list:
        """Yaklaşan veya süresi kritik görevleri kalan gün sırasıyla döndürür."""
        conn = get_db_connection(self.db_path)
        cur = conn.cursor()

        where_clause = "WHERE durum = 'BEKLIYOR'" if sadece_bekleyen else ""
        cur.execute(f"""
        SELECT id, dkey, birim, dosya_no, kaynak_turu, gorev_baslik, aciklama,
               teblig_tarihi, son_tarih, kalan_gun, oncelik, durum, telegram_bildirildi
        FROM gorev_sure
        {where_clause}
        ORDER BY son_tarih ASC
        LIMIT ?
        """, (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def build_telegram_alert_message(self, max_days: int = 7) -> str:
        """Kritik yaklaşan görevler için Telegram formatında bildirim mesajı oluşturur."""
        gorevler = self.get_yaklasan_gorevler(limit=25, sadece_bekleyen=True)
        kritikler = [g for g in gorevler if g.get("kalan_gun", 999) <= max_days]

        if not kritikler:
            return ""

        msg = "⚠️ *UYAP SÜRE VE GÖREV ALARMI*\n"
        msg += f"🗓️ {date.today().strftime('%d.%m.%Y')} | Son {max_days} Gün İçindeki Kritik İşler:\n\n"

        for g in kritikler:
            kalan = g.get("kalan_gun", 0)
            if kalan <= 0:
                badge = "🔴 *BUGÜN/DOLDU*"
            elif kalan == 1:
                badge = "🔴 *YARIN (1 GÜN)*"
            elif kalan <= 3:
                badge = f"🟡 *{kalan} GÜN KALDI*"
            else:
                badge = f"🟢 *{kalan} GÜN*"

            msg += f"{badge} - {g.get('gorev_baslik')}\n"
            msg += f"📁 *{g.get('birim')}* - `{g.get('dosya_no')}`\n"
            msg += f"⏳ Son Tarih: `{g.get('son_tarih')}`\n"
            if g.get("aciklama"):
                msg += f"ℹ️ {g.get('aciklama')[:120]}\n"
            msg += "───────────────────\n"

        return msg


if __name__ == "__main__":
    init_sure_tables()
    mgr = UyapSureAnalizManager()
    mgr.scan_all()
    yaklasanlar = mgr.get_yaklasan_gorevler(limit=10)
    print(f"\n--- YAKLAŞAN KRİTİK GÖREVLER ({len(yaklasanlar)} adet) ---")
    for y in yaklasanlar:
        print(f"[{y['kalan_gun']} Gün | {y['oncelik']}] {y['gorev_baslik']} ({y['birim']} - {y['dosya_no']}) -> Son: {y['son_tarih']}")
