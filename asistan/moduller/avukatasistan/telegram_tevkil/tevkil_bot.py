#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚡ ULTRA HIZLI TELEGRAM ANKARA TEVKİL YANITLAYICI (USERBOT)
-----------------------------------------------------------
Bu bot:
- Belirlenen Tevkil grubunda paylaşılan mesajları anlık (milisaniye düzeyinde) dinler.
- Mesajda Ankara ve Ankara adliyeleri (Sıhhiye, Söğütözü, Dışkapı, Batı vb.) geçtiğinde
  anında herkesten önce "Ben" (veya belirlenen yanıtı) yazar/alıntılar.
- Çift mesaj atmayı engelleyici ve kendini koruyucu kontrollere sahiptir.
"""

import sys
import os
import time
import asyncio
from datetime import datetime
from telethon import TelegramClient, events

# Bulunulan dizini path'e ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tevkil_config import (
    load_config,
    save_config,
    SESSION_NAME,
    turkish_lower
)

# Son cevaplanan mesaj ID'leri ve son cevap zamanı
replied_message_ids = set()
last_reply_time = 0

def send_phone_alert(title: str, content: str):
    """Termux üzerinden titreşim ve Android bildirimi gönderir."""
    try:
        import subprocess
        # 500 ms titreşim
        subprocess.run(["termux-vibrate", "-d", "500"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Android bildirimi
        subprocess.run([
            "termux-notification",
            "--title", title,
            "--content", content[:150],
            "--priority", "high",
            "--vibrate", "500,200,500"
        ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

async def main():
    print("=" * 65)
    print("⚡ ANKARA TEVKİL YILDIRIM BOTU (ULTRA FAST SNIPER)")
    print("=" * 65)

    config = load_config()
    api_id = config.get("api_id")
    api_hash = config.get("api_hash")
    target_groups = config.get("target_groups", [])
    reply_text = config.get("reply_text", "Ben")
    ankara_keywords = config.get("ankara_keywords", [])
    exclude_keywords = config.get("exclude_keywords", [])
    cooldown = config.get("cooldown_seconds", 3)
    reply_mode = config.get("reply_mode", "reply")

    if not api_id or not api_hash:
        print("[X] Hata: API ID ve API HASH yapılandırılmamış!")
        print("    Lütfen önce 'python3 tevkil_kesif.py' çalıştırarak kurulum yapın.")
        return

    if not target_groups:
        print("[!] Uyarı: Hedef grup tanımlanmamış!")
        print("    Lütfen önce 'python3 tevkil_kesif.py' ile hedef Tevkil grubunu seçin.")
        return

    client = TelegramClient(SESSION_NAME, api_id, api_hash)
    await client.start()
    
    me = await client.get_me()
    print(f"\n[+] Oturum Aktif: {me.first_name} {me.last_name or ''} (ID: {me.id})")
    print(f"[+] İzlenen Grup ID'leri: {target_groups}")
    print(f"[+] Yanıt Metni: '{reply_text}'")
    print(f"[+] Yanıt Modu: {'Mesajı Alıntıla (Reply)' if reply_mode == 'reply' else 'Düz Mesaj Gönder'}")
    print(f"[+] Ankara Kelimeleri: {len(ankara_keywords)} adet anahtar kelime aktif.")
    print("\n🚀 [AKTİF] Grup dinleniyor... Ankara ile ilgili yeni bir tevkil geldiğinde anında 'Ben' yazılacak.")
    print("   Durdurmak için Ctrl+C tuşlarına basabilirsiniz.\n" + "-" * 65)

    @client.on(events.NewMessage(chats=target_groups))
    async def handler(event):
        global last_reply_time
        
        # Kendi gönderdiğimiz mesajlara cevap verme
        if event.sender_id == me.id:
            return

        text = event.raw_text
        if not text:
            return

        now = time.time()
        msg_id = event.id

        # Mükerrer cevap engeli
        if msg_id in replied_message_ids:
            return

        # Cooldown kontrolü
        if (now - last_reply_time) < cooldown:
            return

        text_lower = turkish_lower(text)

        # Başka bir avukatın "ben", "ben ankara", "ben alabilirim" gibi yanıt mesajı mı?
        words = text_lower.split()
        if len(words) <= 4 and words and words[0] in ["ben", "benim", "talibim", "alabilirim"]:
            return
        if text_lower in ["benankara", "ben ankara"]:
            return

        # 1. Hariç tutulan kelime var mı?
        for ex in exclude_keywords:
            if ex in text_lower:
                return

        # 2. Ankara ile ilgili anahtar kelime var mı?
        matched_kw = None
        for kw in ankara_keywords:
            if kw in text_lower:
                matched_kw = kw
                break

        if not matched_kw:
            return

        # Eşleşme bulundu! Hemen cevap ver!
        t_start = time.perf_counter()
        
        try:
            replied_message_ids.add(msg_id)
            last_reply_time = now

            if reply_mode == "reply":
                sent = await event.reply(reply_text)
            else:
                sent = await event.respond(reply_text)

            t_elapsed = (time.perf_counter() - t_start) * 1000  # ms cinsinden

            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"\n⚡ [{timestamp}] TEVKİL YAKALANDI!")
            print(f"📌 Tetikleyen Kelime: '{matched_kw}'")
            print(f"⏱️ Tepki / Gönderme Süresi: {t_elapsed:.1f} ms")
            print(f"💬 Gelen Mesaj: {text.strip().replace(chr(10), ' ')[:120]}...")
            print(f"✅ Gönderilen Cevap: '{reply_text}' (ID: {sent.id})")
            print("-" * 65)

            # Telefon bildirimi ve titreşim tetikle
            send_phone_alert("⚡ Ankara Tevkili Yakalandı!", f"'{matched_kw}' tespit edildi -> 'Ben' yazıldı: {text.strip()}")

            # Log dosyasına yaz
            log_line = f"[{timestamp}] YAKALANDI ({t_elapsed:.1f}ms) | Kelime: {matched_kw} | Gelen: {text.strip().replace(chr(10), ' ')} | Yanıt: {reply_text}\n"
            log_path = os.path.join(os.path.dirname(__file__), "tevkil_log.txt")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_line)

        except Exception as e:
            print(f"[X] Mesaj gönderilirken hata oluştu: {e}")

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Bot kullanıcı tarafından durduruldu. Görüşmek üzere!")
