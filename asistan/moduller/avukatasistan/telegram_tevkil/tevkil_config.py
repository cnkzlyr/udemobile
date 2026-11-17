#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Tevkil Botu - Yapılandırma Dosyası
"""

import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "telegram_config.json"
SESSION_NAME = str(BASE_DIR / "tevkil_session")

DEFAULT_CONFIG = {
    "api_id": None,
    "api_hash": "",
    "target_groups": [],  # Grup ID'leri veya grup isimleri (Örn: ["Tevkil Grubu", -1001234567890])
    "reply_text": "Ben",
    "ankara_keywords": [
        "ankara",
        "sıhhiye",
        "sihhiye",
        "söğütözü",
        "sogutozu",
        "dışkapı",
        "diskapı",
        "diskapi",
        "ankara batı",
        "ankara bati",
        "batı adliyesi",
        "bati adliyesi",
        "etimesgut",
        "sincan",
        "gölbaşı",
        "golbasi",
        "kahramankazan",
        "kazan adliyesi",
        "keçiören",
        "kecioren",
        "altındağ",
        "altindag",
        "akyurt",
        "çubuk",
        "cubuk",
        "polatlı",
        "polatli",
        "elmadağ",
        "elmadag",
        "beypazarı",
        "beypazari"
    ],
    "exclude_keywords": [
        "tevkil değildir",
        "tevkil degildir",
        "adıyaman",
        "ankara hariç",
        "ankara haric",
        "ankara dışı",
        "ankara disi",
        "ankara değil",
        "ankara degil",
        "dahili",
        "dahilisini",
        "dönüş yapılmadı",
        "donus yapilmadi",
        "otoyolu",
        "kan gerekiyor",
        "telefon numarası",
        "telefon numarasi"
    ],
    "cooldown_seconds": 3,  # Peş peşe mükerrer mesaj atmaması için bekleme süresi
    "reply_mode": "reply"   # "reply" (mesajı yanıtla) veya "send" (gruba düz gönder)
}

def load_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_conf = json.load(f)
                config.update(user_conf)
        except Exception as e:
            print(f"[!] Yapılandırma yüklenirken hata: {e}")
    return config

def save_config(config_data: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)

def turkish_lower(text: str) -> str:
    """Türkçe karakterleri gözeterek küçük harfe dönüştürür."""
    if not text:
        return ""
    mapping = {
        'İ': 'i', 'I': 'ı', 'Ş': 'ş', 'Ğ': 'ğ', 'Ü': 'ü', 'Ö': 'ö', 'Ç': 'ç'
    }
    for upper, lower in mapping.items():
        text = text.replace(upper, lower)
    return text.lower()
