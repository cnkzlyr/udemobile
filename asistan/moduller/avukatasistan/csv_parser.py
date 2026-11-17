#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UETS CSV Ayrıştırıcı
/sdcard/Download/ dizinindeki tebligatlar.csv dosyalarını tarar ve en güncelini okur.
"""

import os
import glob
import csv
import re
from datetime import datetime
from config import CONFIG, TZ_TURKEY
from utils import calculate_deadlines, is_excluded

def find_latest_tebligat_csv(max_age_minutes=None):
    """Download klasörlerindeki en güncel tebligatlar*.csv dosyasını bulur."""
    all_csvs = []
    for d in CONFIG["DOWNLOAD_DIRS"]:
        if os.path.exists(d):
            # tebligatlar.csv, tebligatlar (1).csv, Tebligatlar*.csv
            patterns = [
                os.path.join(d, "*tebligat*.csv"),
                os.path.join(d, "*Tebligat*.csv")
            ]
            for pat in patterns:
                all_csvs.extend(glob.glob(pat))
                
    if not all_csvs:
        return None
        
    # En son değiştirilme tarihine göre sırala
    all_csvs = list(set(all_csvs))
    all_csvs.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    latest = all_csvs[0]
    if max_age_minutes is not None:
        import time
        age_seconds = time.time() - os.path.getmtime(latest)
        if age_seconds > max_age_minutes * 60:
            return None
    return latest

def parse_csv_file(csv_path=None):
    """
    En güncel CSV dosyasını okuyup tebligat kayıtlarını döndürür.
    Format: Gönderen;Konu;Durumu;Teslim Tarihi;Silineceği Tarih;Boyut
    """
    if not csv_path:
        csv_path = find_latest_tebligat_csv()
        
    if not csv_path or not os.path.exists(csv_path):
        return []
        
    tebligatlar = []
    
    with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        # İlk satırlardaki boşlukları ve başlıkları temizle
        lines = f.readlines()
        
    # Başlık satırını bul
    header_idx = -1
    for i, line in enumerate(lines):
        if "Gönderen" in line and "Konu" in line:
            header_idx = i
            break
            
    if header_idx == -1:
        return []
        
    reader = csv.DictReader(lines[header_idx:], delimiter=";")
    
    for row in reader:
        gonderen = (row.get("Gönderen") or "").strip()
        konu = (row.get("Konu") or "").strip()
        teslim_tarihi_str = (row.get("Teslim Tarihi") or "").strip()
        
        if not konu:
            continue
            
        # Konu içerisinden mahkeme, esas no ve barkod yakala:
        # Örnek: "Ankara 73. Asliye Ceza Mahkemesi [2026/142] [Ankara 73. Asliye Ceza Mahkemesi-5003184040744-0-2026/142]"
        court = ""
        esas_no = ""
        barcode = ""
        
        m_esas = re.search(r"\[(\d{4}/\d+)\]", konu)
        if m_esas:
            esas_no = m_esas.group(1)
            
        m_bar = re.search(r"-(\d{11,15})-", konu) or re.search(r"(\d{11,15})", konu)
        if m_bar:
            barcode = m_bar.group(1)
            
        # Mahkeme adı: İlk köşeli paranteze kadar olan kısım
        if "[" in konu:
            court = konu.split("[")[0].strip()
        else:
            court = konu.strip()
            
        if is_excluded(court + " " + esas_no):
            continue
            
        # Tarih parse (08.10.2026 17:32)
        deadlines = None
        dt = None
        now_dt = datetime.now(TZ_TURKEY)
        if teslim_tarihi_str:
            try:
                dt = datetime.strptime(teslim_tarihi_str, "%d.%m.%Y %H:%M").replace(tzinfo=TZ_TURKEY)
                # 30 günden eski tebligatları işleme
                if (now_dt - dt).days > CONFIG["MAX_SCAN_DAYS"]:
                    continue
                deadlines = calculate_deadlines(dt, court=court)
            except Exception:
                pass
                
        if not deadlines:
            deadlines = calculate_deadlines(now_dt, court=court)
            
        tebligatlar.append({
            "source": "csv",
            "uets_no": (row.get("UETS No") or "").strip(),
            "csv_path": csv_path,
            "gonderen": gonderen,
            "konu_raw": konu,
            "court": court,
            "esas_no": esas_no,
            "barcode": barcode,
            "deadlines": deadlines,
            "parties": [],
            "documents": [],
            "extra_info": ""
        })
        
    return tebligatlar
