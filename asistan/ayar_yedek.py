# -*- coding: utf-8 -*-
"""
AYAR YEDEĞİ — anahtarları bir kez girin, her kurulumda tek adımda geri gelsin.

Kapsam: Entegrasyon anahtarları (.env: Notion, TickTick, Telegram, Gmail uygulama şifresi, UETS, yapay zekâ özeti…),
Drive ayarları (watcher_config.json: Apps Script webhook, klasör, aralık…), UYAP ayarları (T.C., GSM, operatör,
bağlı tut). e-İmza PIN'i yalnızca kullanıcı açıkça isterse eklenir.

Güvenlik: yedek her zaman ŞİFRELİDİR. Anahtar, kullanıcının yedek şifresinden PBKDF2-HMAC-SHA256 (300.000 tur,
rastgele tuz) ile türetilir; içerik SHA-256 sayaç kipiyle şifrelenir ve HMAC-SHA256 ile mühürlenir (önce şifrele,
sonra doğrula). Yalnızca Python standart kütüphanesi kullanılır: Android, Linux, Windows, macOS'ta aynı dosya açılır.
Yanlış şifre ya da bozulmuş dosya açıkça reddedilir.

Yedeğin durduğu yerler:
  1. Bulut: kullanıcının KENDİ Google Drive'ı, mevcut Apps Script webhook'u üzerinden
     UYAP_Arsiv/_CanEditor_Ayar/ayar-yedegi-<zaman>.cnayar  (betikte değişiklik gerekmez).
  2. Dosya: ".cnayar" olarak dışa aktarılır (USB, e-posta, telefon); masaüstünde ayrıca ~/CanEditor/ altına
     otomatik kopya (uygulama kaldırılsa bile kalır).
  3. Otomatik: yedek şifresi bir kez kaydedildiyse her ayar değişikliğinden sonra bulut + yerel yedek yenilenir.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.request
from pathlib import Path

BICIM = "CanEditor-ayar-1"
TUR = 300_000
BULUT_KLASOR = "_CanEditor_Ayar"
ENV_HARIC = {"AYAR_YEDEK_SIFRE"}   # yedek şifresi yedeğin içine girmez


# --------------------------------------------------------------------------- şifreleme (stdlib)
def _anahtarlar(sifre: str, tuz: bytes, tur: int) -> tuple[bytes, bytes]:
    k = hashlib.pbkdf2_hmac("sha256", sifre.encode("utf-8"), tuz, tur, dklen=64)
    return k[:32], k[32:]


def _akis(anahtar: bytes, nonce: bytes, n: int) -> bytes:
    out = bytearray()
    sayac = 0
    while len(out) < n:
        out += hashlib.sha256(anahtar + nonce + sayac.to_bytes(8, "big")).digest()
        sayac += 1
    return bytes(out[:n])


def sifrele(veri: dict, sifre: str) -> bytes:
    if not sifre or len(sifre) < 6:
        raise ValueError("Yedek şifresi en az 6 karakter olmalı.")
    duz = json.dumps(veri, ensure_ascii=False).encode("utf-8")
    tuz, nonce = secrets.token_bytes(16), secrets.token_bytes(16)
    k_enc, k_mac = _anahtarlar(sifre, tuz, TUR)
    ct = bytes(a ^ b for a, b in zip(duz, _akis(k_enc, nonce, len(duz))))
    mac = hmac.new(k_mac, BICIM.encode() + tuz + nonce + ct, hashlib.sha256).digest()
    zarf = {"bicim": BICIM, "kdf": "pbkdf2-sha256", "tur": TUR, "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tuz": base64.b64encode(tuz).decode(), "nonce": base64.b64encode(nonce).decode(),
            "ct": base64.b64encode(ct).decode(), "mac": base64.b64encode(mac).decode()}
    return json.dumps(zarf, indent=1).encode("utf-8")


def coz(ham: bytes, sifre: str) -> dict:
    try:
        z = json.loads(ham.decode("utf-8") if isinstance(ham, (bytes, bytearray)) else ham)
        assert z.get("bicim") == BICIM
        tuz, nonce = base64.b64decode(z["tuz"]), base64.b64decode(z["nonce"])
        ct, mac = base64.b64decode(z["ct"]), base64.b64decode(z["mac"])
    except Exception as e:  # noqa: BLE001
        raise ValueError("Bu dosya bir CanEditor ayar yedeği değil ya da bozulmuş.") from e
    k_enc, k_mac = _anahtarlar(sifre or "", tuz, int(z.get("tur") or TUR))
    if not hmac.compare_digest(mac, hmac.new(k_mac, BICIM.encode() + tuz + nonce + ct, hashlib.sha256).digest()):
        raise ValueError("Yedek şifresi yanlış (ya da dosya değiştirilmiş).")
    return json.loads(bytes(a ^ b for a, b in zip(ct, _akis(k_enc, nonce, len(ct)))).decode("utf-8"))


# --------------------------------------------------------------------------- topla / uygula
def _env_oku(p: Path) -> dict:
    d = {}
    if p.is_file():
        for s in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = s.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                v = v.strip().strip('"').strip("'")
                if v:
                    d[k.strip()] = v
    return d


def _env_yaz(p: Path, yeni: dict) -> None:
    mevcut = _env_oku(p)
    mevcut.update({k: str(v) for k, v in yeni.items() if v not in (None, "") and k not in ENV_HARIC})
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".env.tmp")
    tmp.write_text("\n".join(f"{k}={v}" for k, v in mevcut.items()) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def _json_oku(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _json_yaz(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def topla(env_yolu: Path, evrak_veri: Path, uyap_cfg_yolu: Path, pin_dahil: bool = False) -> dict:
    env = {k: v for k, v in _env_oku(env_yolu).items() if k not in ENV_HARIC}
    uy = _json_oku(uyap_cfg_yolu)
    uyap = {k: uy[k] for k in ("tc", "gsm", "operator", "canasistan_bagli_tut", "canasistan_aralik_dk") if k in uy}
    veri = {"surum": 1, "env": env, "watcher_config": _json_oku(evrak_veri / "watcher_config.json"), "uyap": uyap}
    pin = evrak_veri / "pin.txt"
    if pin_dahil and pin.is_file():
        veri["pin"] = pin.read_text(encoding="utf-8").strip()
    return veri


def uygula(veri: dict, env_yolu: Path, evrak_veri: Path, uyap_cfg_yolu: Path) -> dict:
    """Yedeği bu cihaza yazar. Var olan, yedekte olmayan ayarlar korunur."""
    sayi = {"anahtar": 0, "drive": 0, "uyap": 0, "pin": False}
    if veri.get("env"):
        _env_yaz(env_yolu, veri["env"])
        sayi["anahtar"] = len(veri["env"])
    if veri.get("watcher_config"):
        wc = _json_oku(evrak_veri / "watcher_config.json")
        wc.update({k: v for k, v in veri["watcher_config"].items() if v not in (None, "")})
        _json_yaz(evrak_veri / "watcher_config.json", wc)
        sayi["drive"] = len(veri["watcher_config"])
    if veri.get("uyap"):
        uy = _json_oku(uyap_cfg_yolu)
        uy.update(veri["uyap"])
        _json_yaz(uyap_cfg_yolu, uy)
        sayi["uyap"] = len(veri["uyap"])
    if veri.get("pin"):
        p = evrak_veri / "pin.txt"
        p.write_text(str(veri["pin"]), encoding="utf-8")
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
        sayi["pin"] = True
    return sayi


# --------------------------------------------------------------------------- bulut (kullanıcının Drive'ı)
def _post(webhook: str, govde: dict, zaman: int = 60) -> dict:
    req = urllib.request.Request(webhook, data=json.dumps(govde).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=zaman) as r:
        v = json.loads(r.read().decode("utf-8", "replace") or "{}")
    if isinstance(v, dict) and v.get("status") == "error":
        raise RuntimeError(v.get("message") or "Drive betiği hata döndürdü")
    return v


def bulut_yedekle(webhook: str, blob: bytes) -> dict:
    if not webhook:
        raise ValueError("Drive webhook adresi yok (Drive Ayarları).")
    ad = f"ayar-yedegi-{time.strftime('%Y%m%d-%H%M%S')}.cnayar"
    v = _post(webhook, {"action": "upload", "folder_path": BULUT_KLASOR, "filename": ad,
                        "content": base64.b64encode(blob).decode()})
    return {"ad": ad, "url": v.get("url", "")}


def bulut_son_yedek(webhook: str) -> bytes:
    if not webhook:
        raise ValueError("Drive webhook adresini girin (Apps Script /exec bağlantısı).")
    dosyalar, state = [], None
    for _ in range(10):
        v = _post(webhook, {"action": "list", "kok": BULUT_KLASOR, **({"state": state} if state else {})})
        if v.get("status") == "error":
            raise ValueError("Drive'da yedek klasörü yok: daha önce buluta yedek alınmamış.")
        dosyalar += v.get("dosyalar") or []
        state = v.get("state")
        if not state:
            break
    adaylar = [d for d in dosyalar if str(d.get("ad", "")).startswith("ayar-yedegi-")]
    if not adaylar:
        raise ValueError("Drive'da ayar yedeği bulunamadı.")
    son = max(adaylar, key=lambda d: (d.get("mtime") or 0, d.get("ad")))
    v = _post(webhook, {"action": "get", "id": son["id"]})
    return base64.b64decode(v.get("content") or "")


def yerel_yedek_yolu() -> Path | None:
    """Masaüstünde uygulama kaldırılsa bile kalan konum: ~/CanEditor/ayar-yedegi.cnayar (Android'de yok)."""
    if os.environ.get("CANASISTAN_ANDROID") == "1":
        return None
    return Path.home() / "CanEditor" / "ayar-yedegi.cnayar"
