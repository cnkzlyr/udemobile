#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kişisel ayarlar (PIN, TC, GSM, operatör, Telegram, Drive webhook) — TEK KAYNAK
================================================================================

TR: v4.10.0'a kadar e-imza PIN'i, TC kimlik numarası, GSM numarası ve Telegram bot anahtarı birçok betikte
    SABİT yazılıydı ve herkese açık depoya giriyordu. Artık hiçbir modül bu değerleri koda yazmaz; hepsi bu
    modülden okunur. Arama sırası (ilk bulunan kazanır):
      1. Ortam değişkenleri: EIMZA_PIN, UYAP_TC / MIMZA_TCKN, UYAP_GSM / MIMZA_GSM, UYAP_OPERATOR / MIMZA_OP,
         TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DRIVE_WEBHOOK
      2. ~/.caneditor/kisisel.json  (caneditor ayar komutu / Ayarlar penceresi yazar; izinler 600)
      3. UYAP evrak modülünün .uyap_config.json'u (tc, gsm, operator, pin, telegram_*)
      4. ~/.uki/mobileConfig, ~/.eimza/config.json (resmî Mobil İmza istemcisinin anahtar=değer dosyası)
    Değer yoksa boş döner; çağıran taraf "PIN ayarlanmamış" gibi açık bir hata verir. PIN HİÇBİR ZAMAN tahminle
    ya da yeniden denemeyle karta gönderilmez (kart bloke olmasın).

EN: single source for personal secrets; nothing is hard-coded in the repository any more.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ORTAM = {
    "pin": ("EIMZA_PIN", "CANEDITOR_PIN"),
    "tc": ("UYAP_TC", "MIMZA_TCKN"),
    "gsm": ("UYAP_GSM", "MIMZA_GSM"),
    "operator": ("UYAP_OPERATOR", "MIMZA_OP"),
    "telegram_token": ("TELEGRAM_BOT_TOKEN",),
    "telegram_chat": ("TELEGRAM_CHAT_ID",),
    "drive_webhook": ("DRIVE_WEBHOOK", "GOOGLE_DRIVE_WEBHOOK"),
}
# JSON/anahtar=değer dosyalarındaki eş anlamlı adlar
ESANLAM = {
    "pin": ("pin", "eimza_pin", "PIN"),
    "tc": ("tc", "tckn", "TCKNo", "tc_kimlik"),
    "gsm": ("gsm", "GSMNo", "telefon"),
    "operator": ("operator", "GSMType", "operatör"),
    "telegram_token": ("telegram_token", "telegram_bot_token", "TELEGRAM_BOT_TOKEN"),
    "telegram_chat": ("telegram_chat", "telegram_chat_id", "TELEGRAM_CHAT_ID"),
    "drive_webhook": ("drive_webhook", "google_drive_webhook", "webhook"),
}


def kisisel_dosya() -> Path:
    return Path.home() / ".caneditor" / "kisisel.json"


def _json_dosyalari() -> list[Path]:
    kok = Path(__file__).resolve().parent
    out = [kisisel_dosya()]
    for d in (os.environ.get("UYAP_VERI_DIZINI"), os.environ.get("CANASISTAN_VERI")):
        if d:
            out += [Path(d) / ".uyap_config.json", Path(d) / "moduller" / "evrak" / ".uyap_config.json"]
    out += [kok / "moduller" / "evrak" / ".uyap_config.json", Path.home() / ".uyap_evrak" / ".uyap_config.json",
            Path.home() / ".eimza" / "config.json"]
    return out


def _anahtar_deger(p: Path) -> dict:
    d = {}
    try:
        for satir in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            satir = satir.strip()
            if satir and not satir.startswith("#") and "=" in satir:
                k, v = satir.split("=", 1)
                d[k.strip()] = v.strip()
    except OSError:
        pass
    return d


def al(ad: str, varsayilan: str = "") -> str:
    """Kişisel ayarı döndürür (yoksa varsayilan). EN: returns a personal setting or the default."""
    for e in ORTAM.get(ad, ()):
        v = os.environ.get(e, "").strip()
        if v:
            return v
    adlar = ESANLAM.get(ad, (ad,))
    for p in _json_dosyalari():
        try:
            if not p.is_file():
                continue
            veri = json.loads(p.read_text(encoding="utf-8") or "{}")
        except (OSError, ValueError):
            veri = _anahtar_deger(p)
        if isinstance(veri, dict):
            for k in adlar:
                v = str(veri.get(k) or "").strip()
                if v:
                    return v
    for p in (Path.home() / ".uki" / "mobileConfig", Path.home() / "CanEditor" / "mobileConfig"):
        veri = _anahtar_deger(p)
        for k in adlar:
            if veri.get(k):
                return veri[k]
    return varsayilan


def operator_kodu(deger: str | None = None) -> int:
    """'turkcell'/'1' → 1, 'telekom'/'avea'/'2' → 2, 'vodafone'/'3' → 3 (bilinmiyorsa 2)."""
    s = (deger if deger is not None else al("operator")).lower()
    if "turkcell" in s or s == "1":
        return 1
    if "vodafone" in s or s == "3":
        return 3
    return 2


def kaydet(**degerler: str) -> Path:
    """~/.caneditor/kisisel.json'a yazar (yalnız sahibi okuyabilir). EN: persist with 0600 permissions."""
    p = kisisel_dosya()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        mevcut = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except (OSError, ValueError):
        mevcut = {}
    mevcut.update({k: v for k, v in degerler.items() if v is not None})
    p.write_text(json.dumps(mevcut, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return p
