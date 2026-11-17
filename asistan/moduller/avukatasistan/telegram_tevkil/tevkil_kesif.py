#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Tevkil Keşif ve Sohbet Geçmişi İnceleme Aracı
-----------------------------------------------------
Bu araç:
1. Telegram hesabınıza güvenli şekilde bağlanır (session dosyasını yerel olarak oluşturur).
2. Katıldığınız grupları listeler ve Tevkil gruplarını tespit eder.
3. Seçtiğiniz grubun geçmiş mesajlarını çeker ve Ankara ile ilgili mesaj formatlarını analiz eder.
4. Hedef grubu yapılandırma dosyasına (telegram_config.json) otomatik kaydeder.
"""

import sys
import os
import json
import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat

# Bulunulan dizini path'e ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tevkil_config import (
    load_config,
    save_config,
    SESSION_NAME,
    turkish_lower
)

async def main():
    print("=" * 65)
    print("🔍 TELEGRAM TEVKİL GEÇMİŞİ VE GRUP ANALİZ ARACI")
    print("=" * 65)
    
    config = load_config()
    
    api_id = config.get("api_id")
    api_hash = config.get("api_hash")
    
    if not api_id or not api_hash:
        print("\n[!] Telegram API kimlik bilgileri bulunamadı!")
        print("    my.telegram.org adresinden aldığınız bilgileri giriniz:\n")
        try:
            api_id_input = input("👉 API ID (sayı): ").strip()
            api_hash_input = input("👉 API HASH: ").strip()
            if not api_id_input or not api_hash_input:
                print("[X] API ID ve API HASH boş bırakılamaz.")
                return
            api_id = int(api_id_input)
            api_hash = api_hash_input
            config["api_id"] = api_id
            config["api_hash"] = api_hash
            save_config(config)
            print("[+] API bilgileri 'telegram_config.json' dosyasına kaydedildi.\n")
        except ValueError:
            print("[X] Hata: API ID bir tam sayı olmalıdır.")
            return

    client = TelegramClient(SESSION_NAME, api_id, api_hash)
    
    print("[*] Telegram'a bağlanılıyor...")
    print("[*] (İlk girişinizde telefon numaranızı ve Telegram'a gelen kodu soracaktır)")
    await client.start()
    
    me = await client.get_me()
    print(f"\n[+] Başarıyla giriş yapıldı: {me.first_name} {me.last_name or ''} (@{me.username or 'kullanıcı_adı_yok'})")
    print(f"[+] Kullanıcı ID: {me.id}\n")

    print("[*] Gruplarınız taranıyor...")
    dialogs = await client.get_dialogs()
    
    groups = []
    tevkil_groups = []
    
    for d in dialogs:
        if d.is_group or d.is_channel:
            entity = d.entity
            title = d.name
            groups.append(d)
            lower_title = turkish_lower(title)
            if any(k in lower_title for k in ["tevkil", "durusma", "duruşma", "avukat", "meslektas", "meslektaş", "baro", "hukuk"]):
                tevkil_groups.append(d)

    print(f"\nToplam {len(groups)} grup/kanal bulundu.")
    
    display_list = tevkil_groups if tevkil_groups else groups
    
    print("\n--- Olası Tevkil Grupları ---")
    for i, g in enumerate(display_list, 1):
        print(f"[{i}] {g.name} (ID: {g.id})")
    
    if tevkil_groups and len(tevkil_groups) < len(groups):
        print(f"[0] Diğer tüm grupları listele ({len(groups)} grup)")
    
    choice = input("\n👉 İncelemek istediğiniz grubun numarasını girin: ").strip()
    
    selected_group = None
    if choice == "0" and tevkil_groups:
        print("\n--- Tüm Gruplar ---")
        for i, g in enumerate(groups, 1):
            print(f"[{i}] {g.name} (ID: {g.id})")
        choice = input("\n👉 İncelemek istediğiniz grubun numarasını girin: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(groups):
                selected_group = groups[idx]
        except ValueError:
            pass
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(display_list):
                selected_group = display_list[idx]
        except ValueError:
            pass

    if not selected_group:
        print("[X] Geçersiz seçim yapıldı. Çıkılıyor.")
        await client.disconnect()
        return

    print(f"\n[+] Seçilen Grup: {selected_group.name} (ID: {selected_group.id})")
    
    # Hedef grubu config'e ekle/güncelle
    if selected_group.id not in config.get("target_groups", []):
        config["target_groups"] = [selected_group.id]
        save_config(config)
        print(f"[+] '{selected_group.name}' hedef grup olarak config'e kaydedildi.")

    # Mesaj geçmişini çek
    limit_input = input("\n👉 Taranacak geçmiş mesaj sayısı (Varsayılan 500): ").strip()
    limit = int(limit_input) if limit_input.isdigit() else 500
    print(f"\n[*] Son {limit} mesaj taranıyor ve analiz ediliyor...\n")
    
    messages_data = []
    ankara_matches = []
    
    ankara_keywords = config.get("ankara_keywords", [])
    exclude_keywords = config.get("exclude_keywords", [])

    async for msg in client.iter_messages(selected_group, limit=limit):
        if not msg.text:
            continue
        
        text_lower = turkish_lower(msg.text)
        
        # Ankara filtresi kontrolü
        has_ankara = any(kw in text_lower for kw in ankara_keywords)
        is_excluded = any(ex in text_lower for ex in exclude_keywords)
        
        sender = await msg.get_sender()
        sender_name = getattr(sender, "first_name", "Bilinmeyen") if sender else "Bilinmeyen"
        
        item = {
            "id": msg.id,
            "date": msg.date.strftime("%Y-%m-%d %H:%M:%S"),
            "sender": sender_name,
            "text": msg.text,
            "matches_ankara": has_ankara and not is_excluded
        }
        messages_data.append(item)
        
        if has_ankara and not is_excluded:
            ankara_matches.append(item)

    # Sonuçları ekrana yazdır
    print(f"=== TARAMA SONUÇLARI ===")
    print(f"Toplam incelenen metinli mesaj: {len(messages_data)}")
    print(f"🎯 ANKARA İLE EŞLEŞEN MESAJ SAYISI: {len(ankara_matches)}\n")
    
    if ankara_matches:
        print("--- 🎯 TESPİT EDİLEN ANKARA TEVKİL MESAJLARI (ÖRNEKLER) ---")
        for m in reversed(ankara_matches[-10:]):
            print(f"[{m['date']}] Gönderen: {m['sender']}")
            print(f"Mesaj:\n{m['text']}")
            print("-" * 50)
    else:
        print("[-] Son 40 mesajda Ankara anahtar kelimesi içeren tevkil bulunamadı.")
        print("Örnek olarak gruptaki son 5 mesaj:")
        for m in reversed(messages_data[:5]):
            print(f"[{m['date']}] {m['sender']}: {m['text'][:100]}...")
            print("-" * 30)

    # Dosyaya kaydet
    out_file = os.path.join(os.path.dirname(__file__), "gecmis_mesajlar.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(messages_data, f, ensure_ascii=False, indent=2)
    print(f"\n[+] Tüm incelenen mesajlar '{out_file}' dosyasına kaydedildi.")
    print("\n[+] Keşif tamamlandı! Artık 'tevkil_bot.py' scriptini çalıştırarak otomatik 'ben' yanıtlamayı başlatabilirsiniz.")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
