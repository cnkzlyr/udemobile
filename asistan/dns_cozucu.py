#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Android / Glibc Ortamları İçin Bağımsız DNS Çözücü ve socket.getaddrinfo Yaması
=============================================================================
Android'de Termux-glibc ile çalışan CPython, resolv.conf'u bulamadığında
[Errno -3] Temporary failure in name resolution hatası verir (Termux kurulu olmayan telefonda
Notion, TickTick, Telegram, UETS, Gmail ve Drive webhook'u bu yüzden çalışmıyordu).

Bu modül:
1. Önce sistem çözücüsünü (getaddrinfo) dener.
2. Hata (gaierror) durumunda BÜTÜN DNS sunucularına (telefonun kendi DNS'i — CANASISTAN_DNS — ve
   1.1.1.1 / 8.8.8.8 / 9.9.9.9 / 1.0.0.1 / 8.8.4.4) AYNI ANDA UDP sorgusu gönderir, ilk yanıtı alır
   (v4.4.0'da sırayla denendiği için tek çözümleme 3 sn sürüyordu).
3. UDP engelliyse TCP/53, o da olmazsa IP üzerinden DNS-over-HTTPS (Cloudflare / Google) dener.
4. Başarılı sonuçları TTL kadar (en az 60 sn), başarısızları 20 sn önbellekte tutar.
5. socket.getaddrinfo'yu şeffaf biçimde yamalar (requests, urllib, websocket, imaplib, smtplib…).

Independent resolver used as a getaddrinfo fallback on Android where the embedded glibc cannot read resolv.conf.
"""
from __future__ import annotations

import concurrent.futures as _cf
import json
import logging
import os
import random
import re
import socket
import ssl
import struct
import threading
import time
import urllib.request

logger = logging.getLogger("dns_cozucu")

_IP_RX = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
_CACHE: dict[str, tuple[list[str], float]] = {}
_OLUMSUZ: dict[str, float] = {}
_KILIT = threading.Lock()
_DNS_SUNUCULARI = ("1.1.1.1", "8.8.8.8", "9.9.9.9", "1.0.0.1", "8.8.4.4")
_YAMALANDI = False
_ORIJINAL_GETADDRINFO = socket.getaddrinfo
SON_YONTEM = ""  # tanı için: en son başarılı yöntem (udp:1.1.1.1, tcp:8.8.8.8, doh:…)
DNS_PORT = 53


def _sunucular() -> list[str]:
    yerel = [x.strip() for x in os.environ.get("CANASISTAN_DNS", "").replace(";", ",").split(",") if _IP_RX.match(x.strip())]
    out: list[str] = []
    for s in (*yerel, *_DNS_SUNUCULARI):
        if s not in out:
            out.append(s)
    return out


def _paket(host: str) -> tuple[int, bytes]:
    qid = random.randint(1, 0xFFFF)
    p = struct.pack("!HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    for part in host.rstrip(".").split("."):
        b = part.encode("idna")
        p += bytes([len(b)]) + b
    return qid, p + b"\x00\x00\x01\x00\x01"


def _ad_atla(v: bytes, i: int) -> int:
    """DNS adını atlar; sıkıştırma işaretçisi adın sonunda da olabilir (eski sürüm bunu yanlış okuyordu)."""
    while i < len(v):
        n = v[i]
        if n == 0:
            return i + 1
        if n & 0xC0 == 0xC0:
            return i + 2
        i += n + 1
    return i


def _ayristir(v: bytes, qid: int) -> tuple[list[str], int, bool]:
    if len(v) < 12 or struct.unpack("!H", v[:2])[0] != qid:
        return [], 0, False
    bayrak, qd, an = struct.unpack("!HHH", v[2:8])
    kesik = bool(bayrak & 0x0200)
    i = 12
    for _ in range(qd):
        i = _ad_atla(v, i) + 4
    ipler, ttl_min = [], 3600
    for _ in range(an):
        i = _ad_atla(v, i)
        if i + 10 > len(v):
            break
        tur, _sinif, ttl, uz = struct.unpack("!HHIH", v[i:i + 10])
        i += 10
        if tur == 1 and uz == 4:
            ipler.append(socket.inet_ntoa(v[i:i + 4]))
            ttl_min = min(ttl_min, ttl)
        i += uz
    return ipler, max(60, ttl_min), kesik


def _coz_udp(host: str, sunucu: str, zaman_asimi: float = 2.0) -> tuple[list[str], int] | None:
    qid, paket = _paket(host)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(zaman_asimi)
            s.sendto(paket, (sunucu, DNS_PORT))
            bitis = time.time() + zaman_asimi
            while time.time() < bitis:
                v, _ = s.recvfrom(4096)
                ipler, ttl, kesik = _ayristir(v, qid)
                if kesik:
                    return _coz_tcp(host, sunucu, zaman_asimi)
                if ipler:
                    return ipler, ttl
                if len(v) >= 12 and struct.unpack("!H", v[:2])[0] == qid:
                    return None  # geçerli ama boş yanıt (NXDOMAIN vb.)
    except (OSError, struct.error, IndexError):
        return None
    return None


def _coz_tcp(host: str, sunucu: str, zaman_asimi: float = 3.0) -> tuple[list[str], int] | None:
    qid, paket = _paket(host)
    try:
        with _ORIJINAL_CONNECT((sunucu, DNS_PORT), zaman_asimi) as t:
            t.sendall(struct.pack("!H", len(paket)) + paket)
            n = struct.unpack("!H", t.recv(2))[0]
            v = b""
            while len(v) < n:
                parca = t.recv(n - len(v))
                if not parca:
                    break
                v += parca
        ipler, ttl, _ = _ayristir(v, qid)
        return (ipler, ttl) if ipler else None
    except (OSError, struct.error, IndexError):
        return None


def _ORIJINAL_CONNECT(adres, zaman_asimi):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(zaman_asimi)
    s.connect(adres)
    return s


def _coz_doh(host: str, zaman_asimi: float = 4.0) -> tuple[list[str], int, str] | None:
    """UDP/TCP 53 kapalıysa doğrudan IP üzerinden DNS-over-HTTPS (yalnız IP'ye bağlanır, ad çözümü gerekmez)."""
    adresler = (
        f"https://1.1.1.1/dns-query?name={host}&type=A",
        f"https://8.8.8.8/resolve?name={host}&type=1",
        f"https://1.0.0.1/dns-query?name={host}&type=A",
        f"https://8.8.4.4/resolve?name={host}&type=1",
    )
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for u in adresler:
        try:
            req = urllib.request.Request(u, headers={"Accept": "application/dns-json", "User-Agent": "CanEditor/4.4"})
            with urllib.request.urlopen(req, context=ctx, timeout=zaman_asimi) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            ipler = [a["data"] for a in data.get("Answer", []) if a.get("type") == 1 and _IP_RX.match(a.get("data", ""))]
            if ipler:
                ttl = min(int(a.get("TTL") or 300) for a in data.get("Answer", []) if a.get("type") == 1)
                return ipler, max(60, ttl), u.split("/")[2]
        except Exception:  # noqa: BLE001
            continue
    return None


def coz_hepsi(host: str) -> list[str]:
    """Alan adını IPv4 adreslerine çözer (önbellekli). Bulamazsa boş liste."""
    global SON_YONTEM
    host = (host or "").rstrip(".").lower()
    if not host:
        return []
    if _IP_RX.match(host) or host in ("localhost",):
        return [host if host != "localhost" else "127.0.0.1"]
    simdi = time.time()
    with _KILIT:
        k = _CACHE.get(host)
        if k and simdi < k[1]:
            return k[0]
        if _OLUMSUZ.get(host, 0) > simdi:
            return []
    sunucular = _sunucular()
    sonuc, yontem = None, ""
    # 1) Bütün sunuculara aynı anda UDP — ilk gelen kazanır
    ex = _cf.ThreadPoolExecutor(max_workers=len(sunucular))
    try:
        isler = {ex.submit(_coz_udp, host, s): s for s in sunucular}
        for f in _cf.as_completed(isler, timeout=6):
            try:
                r = f.result()
            except Exception:  # noqa: BLE001
                r = None
            if r:
                sonuc, yontem = r, "udp:" + isler[f]
                break
    except _cf.TimeoutError:
        pass
    finally:
        ex.shutdown(wait=False, cancel_futures=True)  # yavaş sunucuları bekleme
    # 2) TCP/53
    if not sonuc:
        for s in sunucular[:3]:
            r = _coz_tcp(host, s)
            if r:
                sonuc, yontem = r, "tcp:" + s
                break
    # 3) DoH
    if not sonuc:
        r = _coz_doh(host)
        if r:
            sonuc, yontem = (r[0], r[1]), "doh:" + r[2]
    with _KILIT:
        if sonuc:
            _CACHE[host] = (sonuc[0], simdi + sonuc[1])
            SON_YONTEM = yontem
            return sonuc[0]
        _OLUMSUZ[host] = simdi + 20
    return []


def coz(host: str) -> str | None:
    """Geriye uyumluluk: ilk IPv4 adresi."""
    l = coz_hepsi(host)
    return l[0] if l else None


def _guvenli_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):  # noqa: A002 — socket API imzası
    try:
        return _ORIJINAL_GETADDRINFO(host, port, family, type, proto, flags)
    except socket.gaierror as e:
        h = host.decode() if isinstance(host, bytes) else host
        if not h or not isinstance(h, str) or _IP_RX.match(h) or family == socket.AF_INET6:
            raise
        sonuc = []
        for ip in coz_hepsi(h):
            try:
                sonuc.extend(_ORIJINAL_GETADDRINFO(ip, port, socket.AF_INET, type, proto, flags | socket.AI_NUMERICHOST))
            except socket.gaierror:
                continue
        if sonuc:
            return sonuc
        raise e


def yama_kur():
    """socket.getaddrinfo'yu süreç genelinde yamalar (birden çok çağrı güvenlidir)."""
    global _YAMALANDI
    if not _YAMALANDI:
        socket.getaddrinfo = _guvenli_getaddrinfo
        _YAMALANDI = True
        logger.info("[DNS Çözücü] Android/Glibc bağımsız DNS çözücü devrede.")


def android_ise_kur(dosya: str | None = None) -> bool:
    """Görev betiklerinin başında çağrılır: Android'deyse yamayı kurar (sitecustomize yüklenmese bile)."""
    if os.environ.get("CANASISTAN_ANDROID") != "1":
        return False
    yama_kur()
    return True


def tani(host: str = "api.telegram.org") -> dict:
    """Tanı: sistem çözücüsü mü, yedek mi çalışıyor, hangi yöntemle, ne kadar sürede."""
    t0 = time.time()
    sonuc = {"host": host, "yama": socket.getaddrinfo is _guvenli_getaddrinfo, "sistem": None, "yedek": None,
             "yontem": "", "ms": 0, "sunucular": _sunucular()}
    try:
        _ORIJINAL_GETADDRINFO(host, 443)
        sonuc["sistem"] = True
    except OSError as e:
        sonuc["sistem"] = f"hata: {e}"
    ipler = coz_hepsi(host)
    sonuc["yedek"] = ipler[:2] or "çözülemedi"
    sonuc["yontem"] = SON_YONTEM
    sonuc["ms"] = round((time.time() - t0) * 1000)
    return sonuc
