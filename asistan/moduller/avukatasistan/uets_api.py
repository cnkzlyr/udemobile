#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UETS (ptt.etebligat.gov.tr) doğrudan API istemcisi.

Neden: Portalın "İNDİR > CSV İndir" düğmesi CSV'yi TARAYICIDA üretir (Angular5Csv) ve yalnızca o an
ekrandaki sayfanın satırlarını (varsayılan 10) içerir; dosyayı geçici bir blob bağlantısıyla indirip
bağlantıyı hemen siler. Selenium'un "a[href^='blob:']" araması bu yüzden hiçbir şey bulamıyor, görünmez
(headless) Chrome'da indirme çoğu zaman diske hiç düşmüyordu -> "CSV indirilemedi". EYP için de satırdaki
"Görüntüle" bağlantısından kimlik tahmin etmek kırılgandı.

Portalın kendi kullandığı uç noktalar (main.js, Kasım 2026):
  GET  {api}/messages?sort=-inserttime&folders_id=1&count=N&start=S   -> JSON dizi, X-Total-Count başlığı
  GET  {api}/messages/{id}/_download                                   -> EYP paketi (zip)
  Kimlik: tarayıcı oturumundaki localStorage["accessToken"] -> "Authorization: Bearer ..."
Böylece giriş (TCKN/şifre/SMS) için yine tarayıcı kullanılır, liste ve EYP'ler doğrudan, eksiksiz alınır.
"""

import csv
import io
import json
import os
import re
from datetime import datetime

import requests

from config import TZ_TURKEY

API_URL = os.environ.get("UETS_API_URL", "https://api.etebligat.gov.tr/v1").rstrip("/")
GELEN_KLASOR = 1
# Portaldaki durum etiketleri (translationLet)
DURUM_ETIKETI = {
    "sent": "Gönderildi", "delivered": "İletildi", "notdelivered": "İletilmedi",
    "read": "Okundu", "readtimeout": "Okundu Kabul Edildi", "deleted": "Silindi",
}
# Son sütun portalın CSV'sinde yok: UETS mesaj numarası (barkodu/esas nosu olmayan tebligatları — ör. noter
# AZİLNAME — tekil tanımak için). csv_parser başlıkla okuduğu için eski CSV'ler de okunmaya devam eder.
CSV_BASLIKLAR = ["Gönderen", "Konu", "Durumu", "Teslim Tarihi", "Silineceği Tarih", "Boyut", "UETS No"]
BARKOD_RE = re.compile(r"-(\d{11,15})-")
BARKOD_GENIS_RE = re.compile(r"(\d{11,15})")


class UetsApiHatasi(Exception):
    pass


def tarayicidan_token(driver):
    """Giriş yapılmış Selenium oturumundan erişim anahtarını alır (portalın kendisi de buradan okur)."""
    try:
        return driver.execute_script(
            'return localStorage.getItem("accessToken") || sessionStorage.getItem("accessToken");') or None
    except Exception:
        return None


def _oturum(token, user_agent=None):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})
    if user_agent:
        s.headers["User-Agent"] = user_agent
    return s


class _TarayiciYaniti:
    def __init__(self, d):
        import base64
        self.status_code = int(d.get("status") or 0)
        self.headers = {k: v for k, v in (d.get("headers") or {}).items()}
        self.content = base64.b64decode(d.get("b64") or "")
        self.text = self.content.decode("utf-8", "replace")

    def json(self):
        return json.loads(self.text)


class TarayiciOturumu:
    """İstekleri Python'dan değil, giriş yapılmış TARAYICININ İÇİNDEN (fetch) atar: portalın kendi çerezleri,
    kökeni ve anahtarıyla. requests ile yapılan çağrı (çerez/köken/vekil sunucu farkı yüzünden) reddedilirse
    kullanılır. requests.Session ile aynı .get() arayüzü."""

    def __init__(self, driver, token):
        self.driver = driver
        self.token = token

    def get(self, url, timeout=60):
        js = """
        const [url, token, done] = [arguments[0], arguments[1], arguments[arguments.length - 1]];
        fetch(url, { headers: { 'Authorization': 'Bearer ' + token, 'Accept': 'application/json, */*' }, credentials: 'include' })
          .then(async r => {
            const h = {}; r.headers.forEach((v, k) => h[k] = v);
            const buf = new Uint8Array(await r.arrayBuffer());
            let bin = ''; for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
            done({ status: r.status, headers: h, b64: btoa(bin) });
          }).catch(e => done({ status: 0, headers: {}, b64: btoa(unescape(encodeURIComponent(String(e)))) }));
        """
        try:
            self.driver.set_script_timeout(timeout)
        except Exception:
            pass
        return _TarayiciYaniti(self.driver.execute_async_script(js, url, self.token) or {})


def _kayit(mesaj):
    try:
        import uets_tani
        uets_tani.api_kaydi(mesaj)
    except Exception:
        pass


def barkod_bul(konu):
    """Konu satırından barkodu çıkarır (csv_parser ile aynı kural)."""
    m = BARKOD_RE.search(konu or "") or BARKOD_GENIS_RE.search(konu or "")
    return m.group(1) if m else ""


def mesajlari_listele(session, en_fazla=200, sayfa_boyu=100, klasor=GELEN_KLASOR, api_url=API_URL, en_eski_gun=None):
    """Gelen kutusundaki tebligatları YENİDEN ESKİYE, sayfa sayfa döndürür (en fazla `en_fazla`).

    Sıralama: portalın kendisi `sort=inserttime` gönderir ve en yeniyi önce gösterir (gerçek UETS kaydıyla
    doğrulandı, 10.11.2026). `-inserttime` en ESKİYİ önce getiriyor: ilk sürüm bu yüzden 534 tebligatın en eski
    200'ünü aldı, hepsi 30 günden eski olduğu için CSV'den 0 kayıt çıktı. Yine de ilk sayfanın sırası kontrol
    edilir; eskiden yeniye geliyorsa ters sıralamayla baştan istenir.
    en_eski_gun: bu kadar günden eski kayda ulaşınca sayfalamayı bırakır (gereksiz istek atılmaz)."""
    import time as _t
    sinir_ts = (_t.time() - en_eski_gun * 86400) if en_eski_gun else None
    for siralama in ("inserttime", "-inserttime"):
        sonuc, start, toplam = [], 0, None
        ters = False
        while len(sonuc) < en_fazla:
            adet = min(sayfa_boyu, en_fazla - len(sonuc))
            url = f"{api_url}/messages?sort={siralama}&folders_id={klasor}&count={adet}"
            if start:
                url += f"&start={start}"
            r = session.get(url, timeout=30)
            _kayit(f"LISTE {type(session).__name__} GET {url} -> {r.status_code} "
                   f"X-Total-Count={r.headers.get('X-Total-Count') or r.headers.get('x-total-count')} "
                   f"tur={r.headers.get('Content-Type') or r.headers.get('content-type')} boyut={len(r.content)}")
            if r.status_code != 200:
                _kayit(f"   govde: {r.text[:500]}")
            if r.status_code in (401, 403):
                raise UetsApiHatasi(f"UETS oturumu geçersiz ({r.status_code}); yeniden giriş gerekli")
            if r.status_code != 200:
                raise UetsApiHatasi(f"UETS mesaj listesi alınamadı: HTTP {r.status_code} {r.text[:200]}")
            try:
                sayfa = r.json()
            except ValueError:
                raise UetsApiHatasi("UETS mesaj listesi JSON değil")
            if not isinstance(sayfa, list):
                raise UetsApiHatasi(f"Beklenmeyen UETS yanıtı: {type(sayfa).__name__}")
            if start == 0:
                if sayfa:
                    _kayit(f"   ilk kaydin alanlari: {sorted(sayfa[0].keys())}")
                zamanlar = [m.get("inserttime") or 0 for m in sayfa]
                if len(zamanlar) > 1 and zamanlar[0] < zamanlar[-1]:
                    _kayit(f"   sort={siralama} ESKIDEN YENIYE geldi; ters siralama deneniyor")
                    ters = True
                    break
                if zamanlar:
                    _kayit(f"   sort={siralama} ilk={zamanlar[0]} son={zamanlar[-1]} (yeniden eskiye)")
            if toplam is None:
                try:
                    toplam = int(r.headers.get("X-Total-Count") or r.headers.get("x-total-count") or "")
                except ValueError:
                    toplam = None
            sonuc.extend(sayfa)
            start += len(sayfa)
            if not sayfa or len(sayfa) < adet or (toplam is not None and start >= toplam):
                break
            if sinir_ts and (sayfa[-1].get("inserttime") or 0) < sinir_ts:
                break
        if not ters:
            break
    sonuc.sort(key=lambda m: m.get("inserttime") or 0, reverse=True)
    return sonuc


def _boyut(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    if n < 1024:
        return f"{n} Byte"
    for birim in ("KB", "MB", "GB"):
        n /= 1024.0
        if n < 1024:
            return f"{n:.2f} {birim}"
    return f"{n:.2f} TB"


def csv_yaz(mesajlar, hedef, baslik="Gelen Tebligatlar"):
    """Portalın 'CSV İndir' çıktısıyla AYNI biçimde (başlık satırı + ';' ayraç + BOM) CSV yazar."""
    tampon = io.StringIO()
    tampon.write(f'"{baslik}"\r\n')
    w = csv.writer(tampon, delimiter=";", quotechar='"', quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(CSV_BASLIKLAR)
    for m in mesajlar:
        ts = m.get("inserttime") or 0
        teslim = datetime.fromtimestamp(int(ts), TZ_TURKEY) if ts else None
        silinecek = ""
        if teslim:
            ay = teslim.month + 6
            yil = teslim.year + (ay - 1) // 12
            ay = (ay - 1) % 12 + 1
            try:
                silinecek = teslim.replace(year=yil, month=ay).strftime("%d.%m.%Y %H:%M")
            except ValueError:  # 31 Ağustos + 6 ay gibi
                silinecek = teslim.replace(year=yil, month=ay, day=28).strftime("%d.%m.%Y %H:%M")
        w.writerow([
            m.get("sender_name") or "",
            m.get("subject") or "",
            DURUM_ETIKETI.get(m.get("status"), m.get("status") or ""),
            teslim.strftime("%d.%m.%Y %H:%M") if teslim else "",
            silinecek,
            _boyut(m.get("size")),
            m.get("id") or "",
        ])
    gecici = hedef + ".yaziliyor"
    with open(gecici, "w", encoding="utf-8-sig", newline="") as f:
        f.write(tampon.getvalue())
    os.replace(gecici, hedef)
    return hedef


def eyp_indir(session, mesaj_id, hedef_klasor, dosya_adi=None, api_url=API_URL):
    """Tek bir tebligatın EYP paketini indirir. EYP bir zip'tir: 'PK' ile başlamayan yanıt (hata sayfası/JSON)
    diske EYP diye YAZILMAZ. Döner: dosya yolu."""
    r = session.get(f"{api_url}/messages/{mesaj_id}/_download", timeout=60)
    _kayit(f"EYP {type(session).__name__} {mesaj_id} -> {r.status_code} tur={r.headers.get('Content-Type') or r.headers.get('content-type')} "
           f"ad={r.headers.get('Content-Disposition') or r.headers.get('content-disposition')} boyut={len(r.content)} ilk={r.content[:8]!r}")
    if r.status_code in (401, 403):
        raise UetsApiHatasi(f"UETS oturumu geçersiz ({r.status_code})")
    if r.status_code != 200:
        raise UetsApiHatasi(f"EYP indirilemedi ({mesaj_id}): HTTP {r.status_code}")
    veri = r.content
    if not veri.startswith(b"PK"):
        raise UetsApiHatasi(f"EYP yanıtı zip değil ({mesaj_id}, {len(veri)} bayt)")
    if not dosya_adi:
        cd = r.headers.get("Content-Disposition") or r.headers.get("content-disposition") or ""
        m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
        dosya_adi = os.path.basename(m.group(1)) if m else f"{mesaj_id}.eyp"
    if not dosya_adi.lower().endswith(".eyp"):
        dosya_adi += ".eyp"
    os.makedirs(hedef_klasor, exist_ok=True)
    hedef = os.path.join(hedef_klasor, dosya_adi)
    gecici = hedef + ".yaziliyor"
    with open(gecici, "wb") as f:
        f.write(veri)
    os.replace(gecici, hedef)
    return hedef
