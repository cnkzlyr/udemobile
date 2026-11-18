#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Android / Glibc Ortamları İçin Bağımsız DNS Çözücü ve socket.getaddrinfo Yaması
=============================================================================
Android'de Termux-glibc ile çalışan CPython, /etc/resolv.conf bulunamadığında
[Errno -3] Temporary failure in name resolution hatası verir.

Bu modül:
1. Öncelikli olarak standart sistem DNS'ini (getaddrinfo) dener.
2. Hata (errno -2 veya -3 / gaierror) durumunda doğrudan 8.8.8.8, 1.1.1.1,
   8.8.4.4 veya 1.0.0.1 DNS sunucularına UDP sorgusu (port 53) gönderir.
3. UDP portu operatör/ağ tarafından engellenmişse doğrudan IP üzerinden
   Cloudflare/Google DNS-over-HTTPS (DoH) API'sine başvurur.
4. Çözülen IP adreslerini 5 dakika boyunca yerel bellekte önbelleğe alır.
5. socket.getaddrinfo'yu şeffaf biçimde yamalayarak requests, urllib, http.client
   ve tüm üçüncü taraf kütüphanelerin sorunsuz çalışmasını sağlar.
"""
from __future__ import annotations

import json
import logging
import re
import socket
import ssl
import struct
import time
import urllib.request

logger = logging.getLogger("dns_cozucu")

_IP_RX = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
_CACHE: dict[str, tuple[str, float]] = {}
_DNS_SUNUCULARI = ("8.8.8.8", "1.1.1.1", "8.8.4.4", "1.0.0.1")
_YAMALANDI = False
_ORIJINAL_GETADDRINFO = socket.getaddrinfo


def _coz_udp(host: str, sunucu: str, zaman_asimi: float = 2.0) -> str | None:
    """Doğrudan DNS sunucusuna UDP A-kaydı sorgusu gönderir."""
    try:
        qid = 0x5a1f
        flags = 0x0100
        packet = struct.pack("!HHHHHH", qid, flags, 1, 0, 0, 0)
        for part in host.split("."):
            b = part.encode("ascii")
            packet += bytes([len(b)]) + b
        packet += b"\x00\x00\x01\x00\x01"

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(zaman_asimi)
        s.sendto(packet, (sunucu, 53))
        yanit, _ = s.recvfrom(1024)
        s.close()

        if len(yanit) < 12:
            return None
        ancount = struct.unpack("!H", yanit[6:8])[0]
        if ancount == 0:
            return None

        idx = 12
        while idx < len(yanit) and yanit[idx] != 0:
            idx += 1 + yanit[idx]
        idx += 5

        for _ in range(ancount):
            if idx >= len(yanit):
                break
            if (yanit[idx] & 0xC0) == 0xC0:
                idx += 2
            else:
                while idx < len(yanit) and yanit[idx] != 0:
                    idx += 1 + yanit[idx]
                idx += 1
            if idx + 10 > len(yanit):
                break
            rtype, rclass, ttl, rdlen = struct.unpack("!HHIH", yanit[idx:idx + 10])
            idx += 10
            if rtype == 1 and rdlen == 4:
                return socket.inet_ntoa(yanit[idx:idx + 4])
            idx += rdlen
    except Exception:
        pass
    return None


def _coz_doh(host: str, zaman_asimi: float = 3.0) -> str | None:
    """UDP 53 kapalıysa doğrudan IP üzerinden DNS-over-HTTPS (DoH) sorgular."""
    doh_linkleri = (
        f"https://1.1.1.1/dns-query?name={host}&type=A",
        f"https://8.8.8.8/resolve?name={host}&type=1",
    )
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for u in doh_linkleri:
        try:
            req = urllib.request.Request(
                u,
                headers={"Accept": "application/dns-json", "User-Agent": "CanEditor/4.1"},
            )
            with urllib.request.urlopen(req, context=ctx, timeout=zaman_asimi) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    for ans in data.get("Answer", []):
                        if ans.get("type") == 1 and _IP_RX.match(ans.get("data", "")):
                            return ans["data"]
        except Exception:
            continue
    return None


def coz(host: str) -> str | None:
    """Verilen alan adını IPv4 adresine dönüştürür."""
    if not host or _IP_RX.match(host) or host in ("localhost", "127.0.0.1", "::1"):
        return host

    simdi = time.time()
    if host in _CACHE:
        ip, exp = _CACHE[host]
        if simdi < exp:
            return ip

    for s in _DNS_SUNUCULARI:
        ip = _coz_udp(host, s)
        if ip:
            _CACHE[host] = (ip, simdi + 300)
            return ip

    ip = _coz_doh(host)
    if ip:
        _CACHE[host] = (ip, simdi + 300)
        return ip

    return None


def _guvenli_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        return _ORIJINAL_GETADDRINFO(host, port, family, type, proto, flags)
    except socket.gaierror as e:
        if host and isinstance(host, str) and not _IP_RX.match(host):
            ip = coz(host)
            if ip and ip != host:
                try:
                    return _ORIJINAL_GETADDRINFO(ip, port, family, type, proto, flags)
                except Exception:
                    pass
        raise e


def yama_kur():
    """socket.getaddrinfo'yu sistem genelinde yamalar."""
    global _YAMALANDI
    if not _YAMALANDI:
        socket.getaddrinfo = _guvenli_getaddrinfo
        _YAMALANDI = True
        logger.info("[DNS Çözücü] Android/Glibc bağımsız DNS çözücü devrede.")
