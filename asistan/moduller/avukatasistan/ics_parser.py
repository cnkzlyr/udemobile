#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📅 CELSE & UYAP TAKVİMİ (.ICS) AYRIŞTIRICI
İndirilenler klasöründeki Celse / UYAP / Google Takvim (.ics) dosyalarını tarar,
duruşma, ön inceleme ve keşif celselerini hatasız ayrıştırır.
"""

import os
import re
import glob
from datetime import datetime, timezone, timedelta
from config import CONFIG, TZ_TURKEY
from utils import normalize_tr

def scan_all_ics_files():
    """Download dizinlerindeki tüm .ics dosyalarını bulur."""
    ics_files = []
    for d in CONFIG["DOWNLOAD_DIRS"]:
        if os.path.exists(d):
            for pat in ["*.ics", "*.ICS"]:
                ics_files.extend(glob.glob(os.path.join(d, pat)))
    ics_files = list(set(ics_files))
    ics_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return ics_files

def parse_ics_file(ics_path):
    """
    Belirtilen .ics dosyasını okur ve içindeki güncel duruşma etkinliklerini döndürür.
    """
    if not os.path.exists(ics_path):
        return []

    try:
        with open(ics_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"⚠️ ICS dosyası okunamadı ({ics_path}): {e}")
        return []

    events = content.split("BEGIN:VEVENT")
    now_dt = datetime.now(TZ_TURKEY)
    today_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    hearings = []

    for ev in events[1:]:
        lines = ev.splitlines()
        d = {}
        curr_key = None
        for l in lines:
            if l.startswith(" "):
                if curr_key:
                    d[curr_key] += l[1:]
                continue
            parts = l.split(":", 1)
            if len(parts) == 2:
                key = parts[0].split(";")[0]
                val = parts[1]
                d[key] = val
                curr_key = key

        summary = d.get("SUMMARY", "").strip()
        location = d.get("LOCATION", "").strip()
        desc = d.get("DESCRIPTION", "").replace("\\n", "\n")
        dtstart = d.get("DTSTART", "").strip()

        sum_norm = normalize_tr(summary)
        if not any(k in sum_norm for k in ["duruşma", "durusma", "ön inceleme", "on inceleme", "keşif", "kesif"]):
            continue

        # Tarih ve Saat Çözümleme (Örn: 20261115T093000 veya 20261115)
        h_date_str = ""
        h_time_str = ""
        try:
            m_dt = re.search(r"(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2}))?", dtstart)
            if m_dt:
                y, m, day = m_dt.group(1), m_dt.group(2), m_dt.group(3)
                h_date_str = f"{day}/{m}/{y}"
                if m_dt.group(4):
                    h_time_str = f"{m_dt.group(4)}:{m_dt.group(5)}"
                
                # Geçmiş duruşmaları atla (MAX_SCAN_DAYS kuralı)
                ev_dt = datetime(int(y), int(m), int(day), tzinfo=TZ_TURKEY)
                if (today_start - ev_dt).days > CONFIG["MAX_SCAN_DAYS"]:
                    continue
        except Exception:
            pass

        if not h_date_str:
            continue

        court = location
        esas_no = ""

        # 1. Başlıktan Esas No Çıkarma: "DURUŞMA - 2026/83 Ankara 5. İş Mahkemesi"
        m_title = re.match(r"^(?:duruşma|durusma|ön inceleme|on inceleme|keşif|kesif)\s*[-:]*\s*(\d{4}/\d+)\s*(.*)$", summary, re.IGNORECASE)
        if m_title:
            esas_no = m_title.group(1).strip()
            rest = m_title.group(2).strip()
            if not court and rest:
                court = rest
        else:
            # Genel esas regex
            m_esas = re.search(r"(\d{4}/\d+)", summary) or re.search(r"(\d{4}/\d+)", desc)
            if m_esas:
                esas_no = m_esas.group(1)

        # 2. Açıklamadan Mahkeme Çıkarma
        if not court or "T.C." in desc or "MAHKEMESİ" in desc.upper():
            m_court = re.search(r"T\.C\.\s*([^\n\r]+MAHKEMES[İI])", desc, re.IGNORECASE)
            if m_court:
                court = m_court.group(1).strip()
            elif not court:
                m_court2 = re.search(r"([^\n\r]+Mahkemesi)", desc, re.IGNORECASE)
                if m_court2:
                    court = m_court2.group(1).strip()

        if esas_no:
            hearings.append({
                "court": court or "Mahkeme",
                "esas_no": esas_no,
                "hearing_date": h_date_str,
                "hearing_time": h_time_str,
                "doc_type": summary or "Celse Takvimi Duruşması",
                "summary": summary,
                "description": desc,
                "source": "ics",
                "file_path": ics_path
            })

    return hearings
