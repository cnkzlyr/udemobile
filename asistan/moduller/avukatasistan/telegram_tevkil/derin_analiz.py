#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tevkil Grubu Derinlemesine Mesaj Analiz Aracı
--------------------------------------------
Grubun geçmiş 2000 mesajını tarar:
- Ankara ve çevre adliyelerle ilgili tevkilleri bulur.
- Mesajların yazılış biçimlerini, anahtar kelimelerini inceler.
- Diğer avukatların nasıl ve ne kadar sürede "Ben", "Talibim" yazdığını analiz eder.
"""

import sys
import os
import json
import asyncio
from datetime import datetime
from telethon import TelegramClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tevkil_config import (
    load_config,
    SESSION_NAME,
    turkish_lower
)

async def run_analysis():
    config = load_config()
    api_id = config.get("api_id")
    api_hash = config.get("api_hash")
    target_groups = config.get("target_groups", [])

    if not target_groups:
        print("[X] Hedef grup bulunamadı!")
        return

    group_id = target_groups[0]
    ankara_keywords = config.get("ankara_keywords", [])
    exclude_keywords = config.get("exclude_keywords", [])

    client = TelegramClient(SESSION_NAME, api_id, api_hash)
    await client.start()

    print(f"[*] Gruba bağlanılıyor: {group_id}")
    entity = await client.get_entity(group_id)
    print(f"[+] Grup Adı: {entity.title}")
    
    limit = 1500
    print(f"[*] Son {limit} mesaj taranıyor (bu işlem 10-20 saniye sürebilir)...")

    all_messages = []
    ankara_messages = []
    total_count = 0

    async for msg in client.iter_messages(entity, limit=limit):
        total_count += 1
        if not msg.text:
            continue
        
        text_lower = turkish_lower(msg.text)
        
        # Ankara kelimelerini kontrol et
        matched_kw = None
        for kw in ankara_keywords:
            if kw in text_lower:
                matched_kw = kw
                break

        is_excluded = any(ex in text_lower for ex in exclude_keywords)

        sender = await msg.get_sender()
        sender_name = getattr(sender, "first_name", "") or ""
        sender_last = getattr(sender, "last_name", "") or ""
        full_name = f"{sender_name} {sender_last}".strip() or "Bilinmeyen"

        item = {
            "id": msg.id,
            "date": msg.date.strftime("%Y-%m-%d %H:%M:%S"),
            "sender": full_name,
            "sender_id": msg.sender_id,
            "text": msg.text,
            "reply_to_msg_id": msg.reply_to_msg_id if msg.reply_to else None,
            "matched_keyword": matched_kw if (matched_kw and not is_excluded) else None
        }
        all_messages.append(item)

        if matched_kw and not is_excluded:
            ankara_messages.append(item)

    print(f"\n[+] Toplam incelenen mesaj: {total_count}")
    print(f"[+] Ankara ile ilgili bulunan mesaj sayısı: {len(ankara_messages)}")

    # Ankara mesajlarını tarihe göre sırala (eskiden yeniye)
    ankara_messages.sort(key=lambda x: x["date"])

    # Raporu kaydet
    report_file = os.path.join(os.path.dirname(__file__), "ankara_tevkilleri.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(ankara_messages, f, ensure_ascii=False, indent=2)

    print(f"[+] Eşleşen mesajlar '{report_file}' dosyasına kaydedildi.")
    
    # Ekrana son 15 Ankara tevkilini yazdır
    print("\n" + "=" * 65)
    print("📋 ANKARA TEVKİL ÖRNEKLERİ (SON 15 MESAJ):")
    print("=" * 65)
    
    for idx, m in enumerate(ankara_messages[-15:], 1):
        print(f"\n--- Örnek #{idx} [{m['date']}] - Gönderen: {m['sender']} ---")
        print(f"Anahtar Kelime: [{m['matched_keyword']}]")
        print(f"Metin:\n{m['text']}")
        print("-" * 50)

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(run_analysis())
