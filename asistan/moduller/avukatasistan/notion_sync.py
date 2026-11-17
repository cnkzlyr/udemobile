#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notion Entegrasyon ve Çift Yönlü Eşitleme Modülü
Notion veritabanındaki dosyaları tarar, eşleştirir ve tebligat notlarını günceller.
"""

import time
import json
import requests
import baglanti
from config import CONFIG
from utils import clean_text, resolve_client_tag, is_excluded

_NOTION_CACHE = None
_CACHE_TIME = 0

def get_notion_headers():
    return {
        "Authorization": f"Bearer {CONFIG['NOTION_TOKEN']}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

def fetch_notion_cases(force_refresh=False):
    """Notion Dosyalar veritabanındaki tüm aktif davaları çeker ve önbelleğe alır."""
    global _NOTION_CACHE, _CACHE_TIME
    
    if not force_refresh and _NOTION_CACHE and (time.time() - _CACHE_TIME < 600):
        return _NOTION_CACHE
        
    url = f"{CONFIG['NOTION_API_BASE']}/databases/{CONFIG['NOTION_DB_DOSYALAR']}/query"
    has_more = True
    cursor = None
    cases = []
    headers = get_notion_headers()
    
    while has_more:
        payload = {"page_size": 100, "sorts": [{"timestamp": "created_time", "direction": "descending"}]}
        if cursor:
            payload["start_cursor"] = cursor
            
        if True:
            # Yarım liste önbelleğe alınmaz: bağlantı koparsa bekleyip devam eder, olmazsa BaglantiHatasi.
            resp = baglanti.oku("POST", url, headers, json_body=payload, timeout=20, ne="Notion dosyaları",
                                kabul=(200,))
            data = resp.json()
            for page in data.get("results", []):
                props = page.get("properties", {})
                
                mahkeme = props.get("MAHKEME/BİRİM", {}).get("formula", {}).get("string") or ""
                esas_no = props.get("DOSYA NO", {}).get("formula", {}).get("string") or ""
                durum = (props.get("DURUM", {}).get("select") or {}).get("name") or ""
                
                if not mahkeme or not esas_no:
                    title_objs = props.get("NOTION DOSYA", {}).get("title", [])
                    raw_title = title_objs[0].get("plain_text", "") if title_objs else ""
                    if " - " in raw_title:
                        parts = raw_title.split(" - ")
                        mahkeme = parts[0].strip()
                        esas_no = parts[-1].strip()
                        
                if durum == "Arşivde" or is_excluded(mahkeme + " " + esas_no):
                    continue
                    
                muvekkil_adi = ""
                m_rollup = props.get("Müvekkil Adı", {}).get("rollup", {}).get("array", [])
                if m_rollup and m_rollup[0].get("title"):
                    muvekkil_adi = m_rollup[0]["title"][0].get("plain_text", "")
                    
                if is_excluded(muvekkil_adi):
                    continue
                    
                # CMK Kontrolü (Vekalet İlişkisi rollup alanından)
                vk_rollup = props.get("VEKALET İLİŞKİSİ", {}).get("rollup", {}).get("array", [])
                vk_names = [x.get("select", {}).get("name", "").upper() for x in vk_rollup if x.get("select")]
                is_cmk = "CMK" in vk_names
                    
                if mahkeme and esas_no:
                    cases.append({
                        "page_id": page["id"],
                        "url": page["url"],
                        "court": str(mahkeme),
                        "esas_no": str(esas_no),
                        "client_name": muvekkil_adi,
                        "client_tag": resolve_client_tag(muvekkil_adi, is_cmk=is_cmk),
                        "is_cmk": is_cmk,
                        "durum": durum,
                        "last_edited": page.get("last_edited_time")
                    })
                    
            has_more = data.get("has_more", False)
            cursor = data.get("next_cursor")
            
    _NOTION_CACHE = cases
    _CACHE_TIME = time.time()
    return cases

def find_notion_case(esas_no, court_context=""):
    """Esas numarası ve mahkeme adından ilgili Notion dosyasını bulur."""
    cases = fetch_notion_cases()
    matches = [c for c in cases if c["esas_no"] == esas_no]
    
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
        
    # Birden fazla dosya varsa mahkeme adı benzerliğine göre seç
    clean_ctx = clean_text(court_context)
    for c in matches:
        c_clean = clean_text(c["court"])
        if c_clean in clean_ctx or clean_ctx in c_clean:
            return c
            
    return matches[0]

def update_notion_tebligat_column(page_id, deadline_str, action_title="", ticktick_url=""):
    """Notion kartındaki '📨 Son Tebligat' sütununu günceller."""
    if not page_id:
        return False
        
    display_str = f"📨 Son Gün: {deadline_str}"
    if action_title and action_title != "Tebligat":
        display_str += f" ({action_title})"
        
    url = f"{CONFIG['NOTION_API_BASE']}/pages/{page_id}"
    payload = {
        "properties": {
            "📨 Son Tebligat": {
                "rich_text": [{"text": {"content": display_str}}]
            }
        }
    }
    
    try:
        resp = requests.patch(url, headers=get_notion_headers(), json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"⚠️ Notion Son Tebligat sütun güncelleme hatası: {e}")
        return False

def update_notion_durusma_column(page_id, hearing_date_str, hearing_time_str="", ticktick_url=""):
    """Notion kartındaki '📅 Sıradaki Duruşma' sütununu günceller."""
    if not page_id or not hearing_date_str:
        return False
        
    display_str = f"📅 {hearing_date_str}"
    if hearing_time_str:
        display_str += f" ({hearing_time_str})"
        
    url = f"{CONFIG['NOTION_API_BASE']}/pages/{page_id}"
    payload = {
        "properties": {
            "📅 Sıradaki Duruşma": {
                "rich_text": [{"text": {"content": display_str}}]
            }
        }
    }
    
    try:
        resp = requests.patch(url, headers=get_notion_headers(), json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"⚠️ Notion Sıradaki Duruşma sütun güncelleme hatası: {e}")
        return False

def update_notion_tebligat_callout(page_id, deadline_str, action_title, ticktick_url, new_note="", files=None):
    """
    Notion sayfasındaki '📨 AKTİF TEBLİGAT & CEVAP BİLGİSİ' Callout kutusunu günceller.
    Elle girilmiş notları ASLA ezmez!
    """
    if not page_id:
        return False
        
    headers = get_notion_headers()
    blocks_url = f"{CONFIG['NOTION_API_BASE']}/blocks/{page_id}/children?page_size=50"
    
    try:
        resp = requests.get(blocks_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return False
            
        blocks = resp.json().get("results", [])
        callout_block = None
        for b in blocks:
            if b.get("type") == "callout":
                txt = "".join([rt.get("plain_text", "") for rt in b.get("callout", {}).get("rich_text", [])])
                if "AKTİF TEBLİGAT" in txt or "TEBLİGAT & CEVAP" in txt:
                    callout_block = b
                    break
                    
        # Eğer Callout bloğu yoksa yenisini oluştur
        if not callout_block:
            sub_title = f"⏳ Son Gün: {deadline_str or 'Belirtilmedi'}"
            if action_title and action_title != "Tebligat":
                sub_title += f" | İşlem: {action_title}"
            sub_title += " | "
            
            callout_payload = {
                "children": [
                    {
                        "object": "block",
                        "type": "callout",
                        "callout": {
                            "rich_text": [
                                {"type": "text", "text": {"content": "📨 AKTİF TEBLİGAT & CEVAP BİLGİSİ\n"}, "annotations": {"bold": True}},
                                {"type": "text", "text": {"content": sub_title}},
                                {"type": "text", "text": {"content": "TickTick Görevi ↗", "link": {"url": ticktick_url} if ticktick_url else None}, "annotations": {"underline": True}}
                            ],
                            "icon": {"emoji": "📨"},
                            "color": "blue_background",
                            "children": [
                                {
                                    "object": "block",
                                    "type": "heading_3",
                                    "heading_3": {"rich_text": [{"type": "text", "text": {"content": "📝 YAPILACAK İŞLEM & CEVAP NOTU:"}}]}
                                },
                                {
                                    "object": "block",
                                    "type": "paragraph",
                                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": new_note or "(Yapılacak işlemi buraya yazabilirsiniz - TickTick ile eşitlenir)"}}]}
                                }
                            ]
                        }
                    }
                ]
            }
            create_resp = requests.patch(f"{CONFIG['NOTION_API_BASE']}/blocks/{page_id}/children", headers=headers, json=callout_payload, timeout=10)
            return create_resp.status_code == 200
            
        return True
    except Exception as e:
        print(f"⚠️ Notion Callout güncelleme hatası: {e}")
        return False
