#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Durum ve Hafıza Yöneticisi (State Manager)
Hangi tebligatların işlendiğini ve EYP eklerinin yüklenip yüklenmediğini takip eder.
"""

import os
import json
import time

STATE_FILE = os.path.expanduser("~/.avukat_asistan_state.json")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"barcodes": {}}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ State kaydetme hatası: {e}")

def get_barcode_state(barcode):
    state = load_state()
    return state.get("barcodes", {}).get(str(barcode))

def update_barcode_state(barcode, task_id, has_eyp=False, project_id=None, status=None, ek_gonderildi=None, ek_gorevi=None):
    state = load_state()
    b_dict = state.setdefault("barcodes", {}).get(str(barcode), {})
    curr_status = status if status is not None else b_dict.get("status", "active")
    state["barcodes"][str(barcode)] = {
        "task_id": task_id,
        "has_eyp": has_eyp,
        "project_id": project_id,
        "status": curr_status,
        "updated_at": time.time(),
        # EYP eklerinin TickTick'e e-postayla en son gönderildiği an (tekrar tekrar göndermeyi önler)
        "ek_gonderildi": ek_gonderildi if ek_gonderildi is not None else b_dict.get("ek_gonderildi"),
        # Ekleri taşıyan "📎 EYP ekleri" alt görevinin kimliği (kullanıcının görevi silinmeden ek eklenir)
        "ek_gorevi": ek_gorevi if ek_gorevi is not None else b_dict.get("ek_gorevi"),
    }
    save_state(state)
