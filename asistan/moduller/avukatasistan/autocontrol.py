#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️ AVUKAT ASİSTANI - OTOKONTROL VE ENTEGRASYON DOĞRULAMA MODÜLÜ
CSV, EYP Arşivi, TickTick (Aktif & Tamamlanmış) ve Notion arasındaki
tüm tebligatları çapraz denetler, eksik veya hatalı durumları tespit eder ve raporlar.
"""

import os
import sys
import time
from datetime import datetime

from config import CONFIG, PROJECT_IDS, TZ_TURKEY
from utils import clean_text, determine_list
from csv_parser import parse_csv_file, find_latest_tebligat_csv
from eyp_parser import scan_all_eyp_files, parse_eyp_file
from notion_sync import fetch_notion_cases, find_notion_case
from state_manager import load_state, get_barcode_state
from ticktick_sync import (
    get_completed_tasks_live,
    get_project_tasks_live,
    extract_barcode_from_text,
    extract_esas_from_text,
    find_existing_tebligat_in_completed,
    find_existing_tebligat_in_active,
    find_or_create_parent_task,
    create_or_update_uets_subtask
)

def inspect_all_tebligatlar(csv_path=None):
    """
    Tüm tebligatların uçtan uca durumunu inceler ve detaylı analiz listesi döner.
    """
    if not csv_path:
        csv_path = find_latest_tebligat_csv()
        
    csv_items = parse_csv_file(csv_path) if csv_path else []
    
    # 1. Yerel EYP Haritası
    eyp_paths = scan_all_eyp_files()
    eyp_map = {} # barcode -> path
    for ep in eyp_paths:
        try:
            info = parse_eyp_file(ep, extract_files=False)
            if info and info.get("barcode"):
                eyp_map[str(info["barcode"])] = ep
        except Exception:
            pass
            
    # 2. Notion Dosyaları
    try:
        notion_cases = fetch_notion_cases()
    except Exception:
        notion_cases = []

    # 3. TickTick Tamamlanmış Görevler
    comp_tasks = get_completed_tasks_live()
    comp_map = {} # barcode -> task
    for ct in comp_tasks:
        c = ct.get("content") or ""
        tit = ct.get("title") or ""
        b = extract_barcode_from_text(c) or extract_barcode_from_text(tit)
        if b:
            comp_map[str(b)] = ct

    # 4. State Dosyası
    app_state = load_state()
    barcodes_state = app_state.get("barcodes", {})

    inspections = []

    for idx, item in enumerate(csv_items):
        bar = str(item.get("barcode") or "")
        court = item.get("court") or ""
        esas = item.get("esas_no") or ""
        deadlines = item.get("deadlines") or {}
        target_str = deadlines.get("target_str") or deadlines.get("d14_str") or ""
        gelis_str = deadlines.get("gelis_str") or ""
        
        list_name = determine_list(court, gonderen=item.get("gonderen", ""))
        pid = PROJECT_IDS.get(list_name) or PROJECT_IDS["Inbox"]

        # A. EYP Durumu
        has_local_eyp = bool(bar and bar in eyp_map)
        local_eyp_path = eyp_map.get(bar)

        # B. TickTick Tamamlanmış Kontrolü
        comp_task = None
        b_st = barcodes_state.get(bar, {}) if bar else {}
        if bar and bar in comp_map:
            comp_task = comp_map[bar]
        else:
            comp_task = find_existing_tebligat_in_completed(bar, esas, court, deadlines=deadlines)

        # Eğer TickTick API'sinden düşmüşse ama state dosyasında kapatıldığı kayıtlıysa:
        if not comp_task and b_st and b_st.get("status") in ["completed", 2, "2"]:
            comp_task = {"status": 2, "id": b_st.get("task_id"), "title": f"Kapalı ({bar})"}

        # C. TickTick Aktif Görev Kontrolü
        act_task = None
        act_pid = pid
        if not comp_task:
            act_task, act_pid = find_existing_tebligat_in_active(bar, esas, court, pid, deadlines=deadlines)

        # D. Ek (Attachment) Durumu
        has_attachment = False
        has_state_eyp = bool(b_st.get("has_eyp"))
        if act_task:
            cnt = act_task.get("content") or ""
            has_attachment = ("![file]" in cnt or "EKLİ EVRAKLAR" in cnt or "Cihazdaki Dosya Yolu" in cnt or has_state_eyp)
        elif comp_task:
            cnt = comp_task.get("content") or ""
            has_attachment = ("![file]" in cnt or "EKLİ EVRAKLAR" in cnt or "Cihazdaki Dosya Yolu" in cnt or has_state_eyp)

        # E. Notion Eşleşmesi
        n_match = find_notion_case(esas, court) if esas else None

        # F. Durum Özeti
        status_code = "UNKNOWN"
        status_desc = ""
        status_color = "gray"

        if comp_task:
            c_st = comp_task.get("status")
            lbl = "Tamamlandı" if c_st == 2 else "Yapılmayacak"
            status_code = "COMPLETED"
            status_desc = f"TickTick'te {lbl}"
            status_color = "gray"
        elif act_task:
            if has_attachment:
                status_code = "SYNCED"
                status_desc = "Aktif (Eki Tam)"
                status_color = "green"
            else:
                status_code = "PENDING_ATTACHMENT"
                status_desc = "Aktif (Ek Bekliyor)"
                status_color = "yellow"
        else:
            if has_local_eyp:
                status_code = "MISSING_TASK_EYP_READY"
                status_desc = "TickTick'te Yok (EYP Hazır)"
                status_color = "orange"
            else:
                status_code = "MISSING_ALL"
                status_desc = "TickTick'te Yok (EYP İndirilecek)"
                status_color = "red"

        inspections.append({
            "idx": idx + 1,
            "barcode": bar,
            "court": court,
            "esas_no": esas,
            "gelis_str": gelis_str,
            "target_str": target_str,
            "deadlines": deadlines,
            "list_name": list_name,
            "project_id": act_pid,
            "has_local_eyp": has_local_eyp,
            "local_eyp_path": local_eyp_path,
            "act_task": act_task,
            "comp_task": comp_task,
            "has_attachment": has_attachment,
            "notion_case": n_match,
            "status_code": status_code,
            "status_desc": status_desc,
            "status_color": status_color,
            "raw_item": item
        })

    return inspections

def print_autocontrol_report(csv_path=None):
    """Konsola zengin formatta otokontrol raporu yazdırır."""
    print("\n" + "="*75)
    print("🛡️  AVUKAT ASİSTANI - OTOKONTROL VE ENTEGRASYON DOĞRULAMA RAPORU")
    print("="*75)
    
    inspections = inspect_all_tebligatlar(csv_path)
    if not inspections:
        print("ℹ️ İncelenecek tebligat kaydı bulunamadı.")
        return inspections
        
    counts = {
        "SYNCED": 0,
        "PENDING_ATTACHMENT": 0,
        "COMPLETED": 0,
        "MISSING_TASK_EYP_READY": 0,
        "MISSING_ALL": 0
    }
    
    for r in inspections:
        counts[r["status_code"]] = counts.get(r["status_code"], 0) + 1

    print(f"📊 Toplam İncelenen Tebligat: {len(inspections)} adet")
    print(f"   🟢 Tam Senkronize (Aktif & Eki Tam): {counts['SYNCED']}")
    print(f"   🟡 Aktif Görev (Ek Yükleme Bekliyor): {counts['PENDING_ATTACHMENT']}")
    print(f"   ⚪ Tamamlandı / Yapılmayacak Olarak Kapatılmış: {counts['COMPLETED']}")
    print(f"   🟠 TickTick'te Eksik (Arşivde EYP Mevcut): {counts['MISSING_TASK_EYP_READY']}")
    print(f"   🔴 TickTick'te Eksik (EYP İndirilmeli): {counts['MISSING_ALL']}")
    print("-" * 75)
    print(f"{'#':<3} {'Geliş':<10} {'Merci':<30} {'Esas':<10} {'Barkod':<14} {'Durum':<20}")
    print("-" * 75)
    
    for r in inspections:
        g_str = r["gelis_str"][:10] if r["gelis_str"] else "-"
        court_short = (r["court"][:28] + "..") if len(r["court"]) > 30 else r["court"]
        icon = "🟢" if r["status_color"] == "green" else ("🟡" if r["status_color"] == "yellow" else ("⚪" if r["status_color"] == "gray" else "🔴"))
        print(f"{r['idx']:<3} {g_str:<10} {court_short:<30} {r['esas_no']:<10} {r['barcode']:<14} {icon} {r['status_desc']}")
        
    print("=" * 75)
    return inspections

if __name__ == "__main__":
    print_autocontrol_report()
