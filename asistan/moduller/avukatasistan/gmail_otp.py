# -*- coding: utf-8 -*-
"""
UETS GİRİŞ KODU (OTP) — Gmail'den sağlam okuma.

Eski okuyucunun neden kodu bulamadığı (v4.6.1 ve öncesi):
  * Her hata sessizce yutuluyordu: Gmail girişi reddedilse, IMAP kapalı olsa ya da SSL doğrulaması paketli
    uygulamada başarısız olsa bile kullanıcı yalnızca "kod henüz gelmedi" görüyordu.
  * Yalnızca seçilen klasörün SON 5 iletisine ve ileti SIRA numarasına (baseline) bakıyordu; etiket yoksa gelen
    kutusuna düşüyor, başka bir filtre iletiyi arşivlediyse hiç bulamıyordu.
  * HTML gövdede etiketler kodla "kodunu" sözcüğünün arasına girince desen tutmuyordu.

Bu sürüm:
  * SSL bağlamını sistem sertifika deposuyla (yoksa certifi) kurar.
  * Sırasıyla 'UETS Giriş Kodu' etiketine, Tüm Postalar'a (Gmail'in \\All klasörü, dili ne olursa olsun) ve
    Gelen Kutusu'na bakar; bugünden itibaren gelen iletileri UID ile tarar (son 25).
  * İletiyi ZAMANLA seçer: giriş düğmesine basıldıktan (en fazla 4 dk önce) sonra gelen ve daha önce
    kullanılmamış kod. HTML etiketleri temizlenir; birden çok desen denenir.
  * Hataları anlaşılır Türkçe uyarıyla bir kez yazar (uygulama şifresi yanlış, IMAP kapalı, ağ/SSL).
"""
from __future__ import annotations

import datetime as _dt
import email
import email.utils
import html
import imaplib
import os
import re
import ssl
import time
from email import policy

_SISTEM_CA = ("/etc/pki/tls/certs/ca-bundle.crt", "/etc/ssl/certs/ca-certificates.crt", "/etc/ssl/cert.pem",
              "/etc/ssl/ca-bundle.pem", "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem")
_KULLANILAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".uets_otp_kullanilan")
_SON_HATA = [""]
SON_DURUM: dict = {}


def ssl_baglami() -> ssl.SSLContext:
    cafile = os.environ.get("SSL_CERT_FILE")
    if not (cafile and os.path.isfile(cafile)):
        cafile = next((p for p in _SISTEM_CA if os.path.isfile(p)), None)
    if not cafile:
        try:
            import certifi
            cafile = certifi.where()
        except Exception:  # noqa: BLE001
            cafile = None
    ctx = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
    return ctx


def _uyar(m: str) -> None:
    if m != _SON_HATA[0]:
        _SON_HATA[0] = m
        print(m, flush=True)
    SON_DURUM["hata"] = m


def _imap_klasor(ad: str) -> str:
    """IMAP klasör adını UTF-7 (RFC 3501) biçimine çevirir ('UETS Giriş Kodu' -> "UETS Giri&AV8- Kodu")."""
    out, buf = [], ""

    def bosalt():
        nonlocal buf
        if buf:
            import base64
            b = base64.b64encode(buf.encode("utf-16-be")).decode().rstrip("=").replace("/", ",")
            out.append("&" + b + "-")
            buf = ""
    for ch in ad:
        if 0x20 <= ord(ch) <= 0x7e:
            bosalt()
            out.append("&-" if ch == "&" else ch)
        else:
            buf += ch
    bosalt()
    return '"' + "".join(out) + '"'


def kod_bul(metin: str) -> str | None:
    """İleti metninden 6 haneli UETS kodunu çıkarır (HTML temizlenir)."""
    t = html.unescape(re.sub(r"<[^>]+>", " ", metin or ""))
    t = re.sub(r"\s+", " ", t)
    for desen in (r"\b(\d{6})\b\s*(?:numaral[ıi]\s*)?kodunu", r"(?:do[gğ]rulama|giri[sş]|g[uü]venlik|onay)\s*kod[uü]?\s*[:：]?\s*(\d{6})\b",
                  r"\bkod(?:unuz|u)?\s*[:：]?\s*(\d{6})\b", r"\b(\d{6})\b"):
        m = re.search(desen, t, re.I)
        if m:
            return m.group(1)
    return None


def _uets_iletisi_mi(msg) -> bool:
    bas = f"{msg.get('from', '')} {msg.get('subject', '')}".lower()
    return any(k in bas for k in ("uets", "ptt", "tebligat", "doğrulama", "dogrulama", "giriş kodu", "giris kodu"))


def _kullanilanlar() -> set:
    try:
        return set(open(_KULLANILAN, encoding="utf-8").read().split())
    except OSError:
        return set()


def kullanildi_isaretle(kod: str) -> None:
    try:
        k = list(_kullanilanlar())[-30:] + [kod]
        with open(_KULLANILAN, "w", encoding="utf-8") as f:
            f.write("\n".join(k))
    except OSError:
        pass


def _klasorler(mail) -> list:
    """Bakılacak klasörler: UETS etiketi, Tüm Postalar (\\All), Gelen Kutusu."""
    sonuc = []
    etiket = os.environ.get("GMAIL_UETS_ETIKET") or "UETS Giriş Kodu"
    # Etiket adı bazen ayrışık Unicode ile (ş = s + birleşik çengel) oluşturulmuş: iki biçim de denenir
    import unicodedata
    for bicim in ('"UETS Giris&Ayc- Kodu"', _imap_klasor(unicodedata.normalize("NFC", etiket)),
                  _imap_klasor(unicodedata.normalize("NFD", etiket))):
        if bicim not in sonuc:
            sonuc.append(bicim)
    try:
        typ, kutular = mail.list()
        for k in kutular or []:
            s = k.decode("utf-8", "replace") if isinstance(k, bytes) else str(k)
            if "\\All" in s:
                m = re.search(r'"([^"]+)"\s*$', s) or re.search(r"\s(\S+)$", s)
                if m:
                    sonuc.append('"' + m.group(1).strip('"') + '"')
    except Exception:  # noqa: BLE001
        pass
    sonuc.append("INBOX")
    return sonuc


def otp_oku(sonra_ts: float, kullanici: str, sifre: str, en_fazla_yas_sn: int = 240) -> tuple | None:
    """sonra_ts'den (en fazla en_fazla_yas_sn önce) sonra gelen, kullanılmamış UETS kodunu döndürür: (kod, kaynak)."""
    if not kullanici or not sifre:
        _uyar("⚠️ Gmail adresi / uygulama şifresi girilmemiş: kod e-postadan okunamaz. Kodu CanEditor → Tebligatlar'dan elle girin.")
        return None
    sifre = re.sub(r"\s+", "", str(sifre))
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ssl_baglami(), timeout=15)
    except ssl.SSLError as e:
        _uyar(f"⚠️ Gmail SSL doğrulaması başarısız ({str(e)[:90]}). Sistem sertifikaları okunamıyor.")
        return None
    except OSError as e:
        _uyar(f"⚠️ Gmail'e (imap.gmail.com:993) bağlanılamadı: {str(e)[:120]}. İnternet/güvenlik duvarını kontrol edin.")
        return None
    try:
        try:
            mail.login(kullanici, sifre)
        except imaplib.IMAP4.error as e:
            m = str(e)
            if "AUTHENTICATIONFAILED" in m or "Invalid credentials" in m:
                _uyar("⚠️ Gmail girişi reddedildi: uygulama şifresi yanlış ya da iptal edilmiş. Google Hesabı → Güvenlik → "
                      "Uygulama şifreleri'nden yeni bir şifre oluşturup Entegrasyonlar'a girin (normal Gmail şifresi çalışmaz).")
            else:
                _uyar(f"⚠️ Gmail girişi başarısız: {m[:150]} (Gmail ayarlarında IMAP açık olmalı).")
            return None
        alt_sinir = sonra_ts - en_fazla_yas_sn
        bugun = (_dt.datetime.now() - _dt.timedelta(days=1)).strftime("%d-%b-%Y")
        kullanilan = _kullanilanlar()
        en_iyi = None
        for kutu in _klasorler(mail):
            try:
                typ, _ = mail.select(kutu, readonly=True)
            except Exception:  # noqa: BLE001
                continue
            if typ != "OK":
                continue
            typ, data = mail.uid("search", None, f"(SINCE {bugun})")
            uids = (data[0].split() if typ == "OK" and data and data[0] else [])[-25:]
            for uid in reversed(uids):
                typ, md = mail.uid("fetch", uid, "(RFC822)")
                if typ != "OK" or not md or not isinstance(md[0], tuple):
                    continue
                msg = email.message_from_bytes(md[0][1], policy=policy.default)
                try:
                    ts = email.utils.parsedate_to_datetime(msg.get("date")).timestamp()
                except Exception:  # noqa: BLE001
                    ts = 0
                if ts and ts < alt_sinir:
                    break  # UID'ler yeniden eskiye: daha eskisine bakmaya gerek yok
                if not _uets_iletisi_mi(msg):
                    continue
                parcalar = []
                for p in msg.walk():
                    if p.get_content_type() in ("text/plain", "text/html"):
                        try:
                            parcalar.append(p.get_content())
                        except Exception:  # noqa: BLE001
                            pass
                kod = kod_bul(" ".join(parcalar) + " " + str(msg.get("subject", "")))
                if kod and kod not in kullanilan and (en_iyi is None or ts > en_iyi[2]):
                    en_iyi = (kod, f"Gmail ({kutu.strip(chr(34))}) · {msg.get('date', '')}", ts)
            if en_iyi:
                break
        SON_DURUM.update({"hata": "", "son_kontrol": time.strftime("%H:%M:%S")})
        _SON_HATA[0] = ""
        return (en_iyi[0], en_iyi[1]) if en_iyi else None
    except Exception as e:  # noqa: BLE001
        _uyar(f"⚠️ Gmail okunurken hata: {str(e)[:150]}")
        return None
    finally:
        try:
            mail.logout()
        except Exception:  # noqa: BLE001
            pass


def baglanti_testi(kullanici: str, sifre: str) -> dict:
    """Entegrasyonlar 'Bağlantıları test et' için: giriş + klasör listesi."""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ssl_baglami(), timeout=15)
        mail.login(kullanici, re.sub(r"\s+", "", str(sifre)))
        kl = _klasorler(mail)
        mail.logout()
        return {"ok": True, "mesaj": f"Gmail bağlı · {len(kl)} klasör taranacak"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "mesaj": str(e)[:200]}
