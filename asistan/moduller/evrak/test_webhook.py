#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import base64
import requests
from pathlib import Path

# watcher_config.json'dan webhook URL'sini oku
config_path = Path("watcher_config.json")
if not config_path.exists():
    print("[!] watcher_config.json bulunamadı!")
    exit(1)

with open(config_path, "r", encoding="utf-8") as f:
    cfg = json.load(f)

url = cfg.get("google_drive_webhook", "").strip()
if not url:
    print("[!] Webhook URL'si yapılandırılmamış!")
    exit(1)

print(f"[*] Webhook test ediliyor: {url[:50]}...")

# Örnek test PDF verisi
test_content = base64.b64encode(b"%PDF-1.4 UYAP Google Drive Baglanti Testi").decode("utf-8")
payload = {
    "filename": "uyap_bulut_test.pdf",
    "folder_path": "TEST_KLASORU",
    "content": test_content
}

try:
    resp = requests.post(url, json=payload, timeout=30)
    print(f"[*] Yanıt Kodu: {resp.status_code}")
    if resp.status_code == 200:
        print("[✓] BAŞARILI! Google Drive doğrudan yükleme aktif.")
        print(f"    Dönen Veri: {resp.text}")
    elif resp.status_code == 403:
        print("[!] 403 FORBIDDEN: Google Apps Script 'Erişimi olanlar' ayarı 'Herkes' (Anyone) yapılmalıdır!")
    else:
        print(f"[!] Hata oluştu: {resp.text[:200]}")
except Exception as e:
    print(f"[!] İstek hatası: {e}")
