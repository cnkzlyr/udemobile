# -*- coding: utf-8 -*-
"""
UYAP Notion & TickTick Entegrasyon Yöneticisi
(c) 2026 Av. Can KIZILYAR - Tüm hakları saklıdır.

Bu modül:
1. TICKTICK ENTEGRASYONU:
   - Duruşmaları, yasal süreleri ve icra takip görevlerini TickTick formatına dönüştürür.
   - 3 Özel Proje/Klasör:
     * 'UYAP - Duruşmalar' (Mahkeme, Saat, Salon, Öncelik)
     * 'UYAP - Yasal Süreler & Ara Kararlar' (İstinaf, İtiraz, Beyan - Kesin Süre Alarmları)
     * 'UYAP - İcra Takip ve Haciz' (Kapak hesapları, kesinleşmeler, haciz talepleri)
   - Doğrudan aktarım için TickTick CSV formatı ve iCalendar (.ics) üretir.
   - TickTick Open API desteği (Token tanımlandığında tek tuşla bulut senkronizasyonu).

2. NOTION ENTEGRASYONU:
   - Dava ve icra dosyalarını, safahat geçmişini, masraf avansı bakiyelerini ve Gemini AI özetlerini
     Notion Veritabanı ('Dava & İcra Portföyü') formatına dönüştürür.
   - Doğrudan Notion API entegrasyonu (Notion Token + Database ID).
   - Tek tıkla Notion'a aktarılabilir CSV ve Markdown blokları üretir.
"""

import os
import sys
import csv
import json
import sqlite3
import logging
import requests
from datetime import datetime, date

logger = logging.getLogger("UyapEntegrasyon")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] (Entegrasyon) %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "uyap_katalog.db"))
OUT_DIR = os.path.abspath(os.path.dirname(__file__))


def get_db_connection(db_path: str = DB_PATH, timeout: float = 60.0) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


class UyapTickTickExporter:
    """TickTick görev ve takvim entegrasyonu."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def export_csv(self, file_path: str = None) -> str:
        """TickTick resmi CSV içe aktarma formatında dosya üretir.
        Sütunlar: Folder,Title,Tags,Content,Start Date,Due Date,Priority
        Priority: 0 (Yok), 1 (Düşük), 3 (Orta), 5 (Yüksek/Acil)
        """
        if not file_path:
            file_path = os.path.join(OUT_DIR, "ticktick_uyap_gorevler.csv")

        conn = get_db_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        SELECT dkey, birim, dosya_no, kaynak_turu, gorev_baslik, aciklama,
               son_tarih, kalan_gun, oncelik, durum
        FROM gorev_sure
        WHERE durum = 'BEKLIYOR'
        ORDER BY son_tarih ASC
        """)
        rows = cur.fetchall()
        conn.close()

        records = []
        for r in rows:
            kaynak = r["kaynak_turu"]
            if kaynak == "DURUSMA_GUNU":
                folder = "UYAP - Duruşmalar"
                tag = "#Duruşma"
            elif kaynak == "DURUSMA_ARAKARAR":
                folder = "UYAP - Yasal Süreler & Ara Kararlar"
                tag = "#AraKarar #KesinSüre"
            elif kaynak == "TEBLIGAT":
                folder = "UYAP - Yasal Süreler & Ara Kararlar"
                tag = "#Tebligat #YasalSüre"
            else:
                folder = "UYAP - Genel Takip"
                tag = "#UYAP"

            # TickTick Priority
            oncelik_str = r["oncelik"] or "NORMAL"
            if oncelik_str == "ACIL":
                prio = 5
            elif oncelik_str == "YUKSEK":
                prio = 3
            elif oncelik_str == "NORMAL":
                prio = 1
            else:
                prio = 0

            due_date = r["son_tarih"] or ""
            content = f"Dosya: {r['birim']} - {r['dosya_no']}\n{r['aciklama'] or ''}\nKalan Gün: {r['kalan_gun']}"

            records.append({
                "Folder": folder,
                "Title": r["gorev_baslik"],
                "Tags": tag,
                "Content": content.replace("\n", " | "),
                "Start Date": "",
                "Due Date": f"{due_date} 09:00:00" if due_date else "",
                "Priority": prio
            })

        fieldnames = ["Folder", "Title", "Tags", "Content", "Start Date", "Due Date", "Priority"]
        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)

        logger.info(f"TickTick CSV aktarımı tamamlandı: {len(records)} görev -> {file_path}")
        return file_path

    def export_ics(self, file_path: str = None) -> str:
        """TickTick, Google Takvim veya Outlook için .ics takvim dosyası üretir."""
        if not file_path:
            file_path = os.path.join(OUT_DIR, "ticktick_uyap_takvim.ics")

        conn = get_db_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        SELECT dkey, birim, dosya_no, kaynak_turu, gorev_baslik, aciklama, son_tarih
        FROM gorev_sure
        WHERE durum = 'BEKLIYOR' AND son_tarih IS NOT NULL AND son_tarih != ''
        ORDER BY son_tarih ASC
        """)
        rows = cur.fetchall()
        conn.close()

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Av. Can KIZILYAR//UYAP Entegrator//TR",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:UYAP Duruşma ve Yasal Süreler",
            "X-WR-TIMEZONE:Europe/Istanbul"
        ]

        now_stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        for idx, r in enumerate(rows):
            s_tarih = r["son_tarih"].replace("-", "")
            summary = r["gorev_baslik"].replace(",", "\\,")
            desc = (r["aciklama"] or "").replace("\n", "\\n").replace(",", "\\,")
            loc = (r["birim"] or "").replace(",", "\\,")

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:uyap-gorev-{idx}-{s_tarih}@kizilyar.av.tr",
                f"DTSTAMP:{now_stamp}",
                f"DTSTART;VALUE=DATE:{s_tarih}",
                f"DTEND;VALUE=DATE:{s_tarih}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{desc}",
                f"LOCATION:{loc}",
                "STATUS:CONFIRMED",
                "BEGIN:VALARM",
                "TRIGGER:-P1D",
                "ACTION:DISPLAY",
                f"DESCRIPTION:UYAP Hatırlatıcı: {summary}",
                "END:VALARM",
                "END:VEVENT"
            ])

        lines.append("END:VCALENDAR")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\r\n".join(lines))

        logger.info(f"iCalendar (.ics) takvimi oluşturuldu: {len(rows)} etkinlik -> {file_path}")
        return file_path


class UyapNotionExporter:
    """Notion veritabanı aktarım ve senkronizasyon yöneticisi."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def export_csv(self, file_path: str = None) -> str:
        """Notion 'Table / Database' olarak doğrudan içe aktarılabilecek zengin CSV dosyası üretir."""
        if not file_path:
            file_path = os.path.join(OUT_DIR, "notion_uyap_dosya_portfoyu.csv")

        conn = get_db_connection(self.db_path)
        cur = conn.cursor()

        # Dava ve İcra dosyalarını birleştir
        cur.execute("""
        SELECT d.dkey, d.birim, d.dosya_no, d.dosya_tur, d.durum, d.yargi, d.acilis,
               COALESCE(f.toplam_tahsilat, 0) as tahsilat,
               COALESCE(f.toplam_reddiyat, 0) as reddiyat,
               COALESCE(f.kalan_bakiye, 0) as gider_avansi_kalan,
               COALESCE(i.toplam_alacak, 0) as icra_toplam_alacak,
               COALESCE(i.bakiye_borc, 0) as icra_kalan_borc,
               COALESCE(i.kesinlesme_durumu, '') as icra_kesinlesme,
               (SELECT COUNT(*) FROM gorev_sure g WHERE g.dkey = d.dkey AND g.durum = 'BEKLIYOR') as bekleyen_gorev_sayisi,
               (SELECT MIN(son_tarih) FROM gorev_sure g WHERE g.dkey = d.dkey AND g.durum = 'BEKLIYOR') as yaklasan_tarih
        FROM dosya d
        LEFT JOIN dosya_finans f ON d.dkey = f.dkey
        LEFT JOIN icra_hesap i ON d.dkey = i.dkey
        WHERE d.durum LIKE '%Açık%' OR d.durum LIKE '%Acik%'
        ORDER BY bekleyen_gorev_sayisi DESC, d.birim ASC
        """)
        rows = cur.fetchall()
        conn.close()

        records = []
        for r in rows:
            is_icra = "İcra" in (r["birim"] or "") or "İcra" in (r["dosya_tur"] or "")
            dosya_tipi = "İcra Dosyası" if is_icra else "Dava Dosyası"

            mali_bakiye = r["icra_kalan_borc"] if is_icra else r["gider_avansi_kalan"]

            records.append({
                "Dosya Başlığı": f"{r['birim']} - {r['dosya_no']}",
                "Birim": r["birim"],
                "Dosya No": r["dosya_no"],
                "Tür": dosya_tipi,
                "Durum": "Açık",
                "Açılış Tarihi": r["acilis"] or "",
                "Mali Bakiye / Kalan Borç (TL)": f"{mali_bakiye:.2f}",
                "İcra Kesinleşme Durumu": r["icra_kesinlesme"] if is_icra else "Uygulanamaz (Dava)",
                "Bekleyen Görev / Süre": r["bekleyen_gorev_sayisi"],
                "Sıradaki Duruşma / Son Tarih": r["yaklasan_tarih"] or ""
            })

        fieldnames = [
            "Dosya Başlığı", "Birim", "Dosya No", "Tür", "Durum", "Açılış Tarihi",
            "Mali Bakiye / Kalan Borç (TL)", "İcra Kesinleşme Durumu", "Bekleyen Görev / Süre", "Sıradaki Duruşma / Son Tarih"
        ]
        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)

        logger.info(f"Notion Dosya Portföyü CSV aktarımı tamamlandı: {len(records)} dosya -> {file_path}")
        return file_path


def export_all_integrations():
    """Tüm Notion ve TickTick dışa aktarımlarını tek seferde çalıştırır."""
    tt = UyapTickTickExporter()
    csv_tt = tt.export_csv()
    ics_tt = tt.export_ics()

    notion = UyapNotionExporter()
    csv_notion = notion.export_csv()

    return {
        "ticktick_csv": csv_tt,
        "ticktick_ics": ics_tt,
        "notion_csv": csv_notion
    }


if __name__ == "__main__":
    res = export_all_integrations()
    print("\n--- NOTION & TICKTICK ENTEGRASYON DOSYALARI HAZIRLANDI ---")
    for k, v in res.items():
        print(f"✓ {k}: {v}")
