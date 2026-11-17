#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UETS TANI (TEŞHİS) KAYDEDİCİSİ — "hangi anda ne oldu" sorusunu tek bir zip dosyasıyla yanıtlar.

Açmak:   UETS_TANI=1 python3 main.py          ya da   python3 uets_downloader.py --tani
Sonuç:   <UETS_Arsivi>/tani/uets_tani_YYYYMMDD_HHMMSS.zip   (bu dosyayı gönderin)

Her adımda kaydedilenler (NN_adim-adi.*):
  .png   ekran görüntüsü (görünmez/headless tarayıcıda da çalışır)
  .html  o anki DOM (document.documentElement.outerHTML, gizli bilgiler maskeli)
  .json  adres, başlık, sekmeler, readyState, önemli seçicilerin sayıları (tablo satırı, Görüntüle, EYP,
         İndir...), görünür düğme/bağlantı metinleri, localStorage/sessionStorage ANAHTAR adları, çerez adları
Tüm oturum boyunca:
  konsol.log     programın bütün ekran çıktısı (zaman damgalı)
  olaylar.log    adım/hata zaman çizelgesi, hata izleri (traceback)
  tarayici.log   tarayıcı konsolu (JS hataları)
  ag.jsonl       ağ trafiği özeti: yöntem, adres, durum, içerik türü, boyut (gövde ve kimlik başlıkları YOK)
  api.log        UETS API denemeleri (durum, başlıklar, ilk kaydın alan adları)
  kaynak/        portalın JavaScript dosyaları (herkese açık kod) — portalı tanımak için

Gizlilik: TCKN, şifre, SMS kodu, Bearer/JWT anahtarları, Gmail adresleri tüm metin dosyalarında maskelenir.
Ekran görüntüleri ve DOM tebligat listesini (mahkeme, esas no, gönderen) içerir: zip'i yalnızca güvendiğiniz
kişiyle paylaşın.
"""

import json
import os
import re
import sys
import time
import traceback
import zipfile
from datetime import datetime

_AKTIF = os.environ.get("UETS_TANI", "").strip().lower() in ("1", "true", "evet", "on")
_KLASOR = None
_SAYAC = 0
_GIZLILER = set()
_TEE = None
_AG_GORULEN = 0

SECICILER = {
    "tablo_satiri(mat-row)": "mat-table mat-row",
    "tablo_satiri(tr)": "table.mat-table tbody tr",
    "tum_tr": "tbody tr",
    "goruntule(a.view-btn)": "a.view-btn",
    "viewMessages_baglantisi": "a[href*='viewMessages'], a[href*='viewmessages']",
    "indir_menusu(dropdown-toggle)": "button.dropdown-toggle",
    "blob_baglantisi": "a[href^='blob:']",
    "sayfalayici(mat-paginator)": "mat-paginator",
    "sms_kodu(m-sms-code)": "m-sms-code",
    "sifre_alani": "input[type='password']",
    "acik_dialog(mat-dialog)": "mat-dialog-container, .modal.show",
    "yukleniyor(spinner)": "mat-spinner, mat-progress-spinner, .m-loader, .spinner",
}


def aktif():
    return _AKTIF


def etkinlestir():
    global _AKTIF
    _AKTIF = True
    os.environ["UETS_TANI"] = "1"


def gizle(deger):
    """Bu değer (TCKN, şifre, OTP...) hiçbir tanı dosyasına açık yazılmaz."""
    if deger and len(str(deger)) >= 4:
        _GIZLILER.add(str(deger))


def maskele(metin):
    if not metin:
        return metin
    s = str(metin)
    for g in sorted(_GIZLILER, key=len, reverse=True):
        s = s.replace(g, "«GİZLİ»")
    s = re.sub(r"(Bearer\s+)[A-Za-z0-9\-_.=:+/]{8,}", r"\1«GİZLİ»", s)
    s = re.sub(r"eyJ[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{5,}", "«JWT»", s)
    s = re.sub(r"(\"?(?:access_?token|refresh_?token|accessToken|refreshToken|password|sifre|token)\"?\s*[:=]\s*\"?)[^\"&,\s}]{4,}",
               r"\1«GİZLİ»", s, flags=re.I)
    s = re.sub(r"[A-Za-z0-9._%+-]+@(gmail|googlemail)\.com", "«e-posta»", s)
    return s


def _klasor():
    global _KLASOR
    if _KLASOR is None:
        try:
            from config import CONFIG
            kok = CONFIG.get("UETS_ARCHIVE_DIR") or os.path.expanduser("~")
        except Exception:
            kok = os.path.expanduser("~")
        _KLASOR = os.path.join(kok, "tani", datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(os.path.join(_KLASOR, "kaynak"), exist_ok=True)
    return _KLASOR


def _yaz(ad, metin, kip="a"):
    try:
        with open(os.path.join(_klasor(), ad), kip, encoding="utf-8") as f:
            f.write(maskele(metin))
    except Exception:
        pass


def _zaman():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


class _Tee:
    """Ekrana yazılan her şeyi konsol.log'a da (zaman damgalı, maskeli) yazar."""

    def __init__(self, asil):
        self.asil = asil
        self._satir_basi = True

    def write(self, s):
        try:
            self.asil.write(s)
        except Exception:
            pass
        if s:
            parca = []
            for ch in s.splitlines(keepends=True):
                parca.append((f"[{_zaman()}] " if self._satir_basi else "") + ch)
                self._satir_basi = ch.endswith("\n")
            _yaz("konsol.log", "".join(parca))
        return len(s) if s else 0

    def flush(self):
        try:
            self.asil.flush()
        except Exception:
            pass

    def __getattr__(self, ad):
        return getattr(self.asil, ad)


def basla():
    """Tanı oturumunu başlatır (klasör + ekran çıktısının kopyası)."""
    global _TEE
    if not _AKTIF:
        return None
    if _TEE is not None:          # zaten başlatıldı (main.py + indirici)
        return _KLASOR
    k = _klasor()
    if _TEE is None:
        _TEE = _Tee(sys.stdout)
        sys.stdout = _TEE
    olay(f"TANI BAŞLADI python={sys.version.split()[0]} platform={sys.platform} klasor={k}")
    try:
        import selenium
        olay(f"selenium={selenium.__version__}")
    except Exception:
        pass
    print(f"🩺 TANI MODU AÇIK: her adım {k} klasörüne kaydediliyor.")
    return k


def olay(mesaj):
    if _AKTIF:
        _yaz("olaylar.log", f"[{_zaman()}] {mesaj}\n")


def api_kaydi(mesaj):
    if _AKTIF:
        _yaz("api.log", f"[{_zaman()}] {mesaj}\n")


def chrome_secenekleri(options):
    """setup_driver içinden çağrılır: tarayıcı konsolu ve ağ (performance) kayıtlarını açar."""
    if not _AKTIF:
        return
    try:
        options.set_capability("goog:loggingPrefs", {"browser": "ALL", "performance": "ALL"})
    except Exception as e:
        olay(f"loggingPrefs ayarlanamadı: {e}")


def _js_durum(driver):
    js = """
    const sec = arguments[0]; const say = {};
    for (const [ad, css] of Object.entries(sec)) { try { say[ad] = document.querySelectorAll(css).length; } catch (e) { say[ad] = 'hata'; } }
    const gorunur = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const metin = (e) => (e.innerText || e.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 80);
    const dugmeler = [...document.querySelectorAll('button, [role=button], input[type=submit]')].filter(gorunur)
      .slice(0, 120).map(e => ({ t: metin(e) || e.getAttribute('aria-label') || e.value || '', c: (e.className || '').toString().slice(0, 80), d: !!e.disabled }));
    const baglantilar = [...document.querySelectorAll('a')].filter(gorunur).slice(0, 120)
      .map(e => ({ t: metin(e), h: (e.getAttribute('href') || '').slice(0, 160), c: (e.className || '').toString().slice(0, 60) }));
    let ls = [], ss = [];
    try { ls = Object.keys(localStorage); } catch (e) {}
    try { ss = Object.keys(sessionStorage); } catch (e) {}
    const satirlar = [...document.querySelectorAll('mat-row, tbody tr')].slice(0, 60).map(r => metin(r));
    return { url: location.href, baslik: document.title, readyState: document.readyState, sayilar: say,
             dugmeler, baglantilar, localStorage_anahtarlari: ls, sessionStorage_anahtarlari: ss,
             ilk_satirlar: satirlar, pencere: [innerWidth, innerHeight], kaydirma: [scrollX, scrollY],
             etkin_eleman: document.activeElement ? document.activeElement.tagName + '.' + (document.activeElement.className || '') : null };
    """
    return driver.execute_script(js, SECICILER)


def _loglari_bosalt(driver):
    global _AG_GORULEN
    try:
        for g in driver.get_log("browser"):
            _yaz("tarayici.log", f"[{g.get('timestamp')}] {g.get('level')} {g.get('message')}\n")
    except Exception:
        pass
    try:
        satirlar = []
        for g in driver.get_log("performance"):
            try:
                m = json.loads(g["message"])["message"]
            except Exception:
                continue
            yontem, p = m.get("method"), m.get("params", {})
            if yontem == "Network.requestWillBeSent":
                r = p.get("request", {})
                url = r.get("url", "")
                if url.startswith("data:"):
                    continue
                satirlar.append({"t": g.get("timestamp"), "olay": "istek", "id": p.get("requestId"), "yontem": r.get("method"),
                                 "url": url[:300], "tur": p.get("type")})
            elif yontem == "Network.responseReceived":
                r = p.get("response", {})
                bas = {k.lower(): v for k, v in (r.get("headers") or {}).items()}
                satirlar.append({"t": g.get("timestamp"), "olay": "yanit", "id": p.get("requestId"), "durum": r.get("status"),
                                 "url": r.get("url", "")[:300], "mime": r.get("mimeType"),
                                 "baslik": {k: bas[k] for k in ("content-type", "content-disposition", "x-total-count",
                                                                "x-unread-count", "content-length", "location") if k in bas}})
            elif yontem == "Network.loadingFailed":
                satirlar.append({"t": g.get("timestamp"), "olay": "HATA", "id": p.get("requestId"),
                                 "hata": p.get("errorText"), "iptal": p.get("canceled"), "tur": p.get("type")})
            elif yontem in ("Page.downloadWillBegin", "Page.downloadProgress", "Browser.downloadWillBegin", "Browser.downloadProgress"):
                satirlar.append({"t": g.get("timestamp"), "olay": yontem, "p": {k: p.get(k) for k in ("url", "suggestedFilename", "state", "receivedBytes", "totalBytes")}})
        if satirlar:
            _AG_GORULEN += len(satirlar)
            _yaz("ag.jsonl", "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in satirlar))
    except Exception:
        pass


def adim(driver, ad, ek=None):
    """Bir adımın tam fotoğrafını çeker: ekran görüntüsü + DOM + durum + loglar."""
    global _SAYAC
    if not _AKTIF or driver is None:
        return
    _SAYAC += 1
    try:  # oturum anahtarlarının DEĞERLERİ hiçbir dosyaya açık yazılmasın
        for v in driver.execute_script("""
            const d = []; for (const st of [localStorage, sessionStorage]) { try { for (const k of Object.keys(st))
              if (/token|auth|sifre|pass|jwt|session/i.test(k)) { const v = st.getItem(k) || '';
                d.push(v); try { const j = JSON.parse(v); if (j && typeof j === 'object') Object.values(j).forEach(x => typeof x === 'string' && d.push(x)); } catch (e) {} } } catch (e) {} }
            return d;""") or []:
            if v and len(str(v)) >= 8:   # "true"/"null" gibi kısa değerler maskelenmez
                gizle(v)
        for c in driver.get_cookies():
            if len(str(c.get("value") or "")) >= 8:
                gizle(c.get("value"))
    except Exception:
        pass
    on = f"{_SAYAC:03d}_{re.sub(r'[^A-Za-z0-9ğüşıöçĞÜŞİÖÇ_-]+', '-', ad)[:60]}"
    k = _klasor()
    try:
        driver.save_screenshot(os.path.join(k, on + ".png"))
    except Exception as e:
        olay(f"{on}: ekran görüntüsü alınamadı: {e}")
    durum = {}
    try:
        durum = _js_durum(driver)
    except Exception as e:
        durum = {"hata": str(e)}
    try:
        durum["pencereler"] = len(driver.window_handles)
        durum["cerez_adlari"] = sorted({c.get("name") for c in driver.get_cookies()})
    except Exception:
        pass
    if ek:
        durum["ek"] = ek
    _yaz(on + ".json", json.dumps(durum, ensure_ascii=False, indent=1), "w")
    try:
        html = driver.execute_script("return document.documentElement.outerHTML;")
        _yaz(on + ".html", html, "w")
    except Exception as e:
        olay(f"{on}: DOM alınamadı: {e}")
    _loglari_bosalt(driver)
    say = durum.get("sayilar", {}) if isinstance(durum, dict) else {}
    olay(f"ADIM {on} url={durum.get('url')} satir={say.get('tablo_satiri(mat-row)')}/{say.get('tum_tr')} "
         f"goruntule={say.get('goruntule(a.view-btn)')} spinner={say.get('yukleniyor(spinner)')} ek={ek}")


def hata(driver, ad, istisna=None):
    """Hata anını kaydeder (traceback + adım fotoğrafı)."""
    if not _AKTIF:
        return
    iz = traceback.format_exc() if istisna is not None else "".join(traceback.format_stack(limit=8))
    olay(f"HATA {ad}: {istisna!r}\n{iz}")
    adim(driver, "HATA-" + ad, ek=repr(istisna) if istisna is not None else None)


def kaynaklari_topla(driver):
    """Portalın yüklediği tüm JS/CSS dosyalarını ve satır içi betikleri kaynak/ klasörüne indirir (herkese açık kod)."""
    if not _AKTIF or driver is None:
        return
    try:
        adresler = driver.execute_script("""
            const s = new Set();
            document.querySelectorAll('script[src]').forEach(e => s.add(e.src));
            document.querySelectorAll('link[rel=stylesheet][href]').forEach(e => s.add(e.href));
            (performance.getEntriesByType('resource') || []).forEach(e => { if (/\\.(js|css)(\\?|$)/.test(e.name)) s.add(e.name); });
            return [...s];""") or []
        satir_ici = driver.execute_script(
            "return [...document.querySelectorAll('script:not([src])')].map(e => e.textContent);") or []
    except Exception as e:
        olay(f"kaynak listesi alınamadı: {e}")
        return
    import requests
    kdir = os.path.join(_klasor(), "kaynak")
    liste = []
    for u in adresler:
        if not u.startswith("http") or "etebligat" not in u:
            liste.append(f"ATLANDI {u}")
            continue
        ad = re.sub(r"[^A-Za-z0-9._-]+", "_", u.split("//", 1)[-1])[-150:]
        try:
            r = requests.get(u, timeout=30)
            with open(os.path.join(kdir, ad), "wb") as f:
                f.write(r.content)
            liste.append(f"{r.status_code} {len(r.content):>9} {u}")
        except Exception as e:
            liste.append(f"HATA {u}: {e}")
    for i, t in enumerate(satir_ici):
        _yaz(os.path.join("kaynak", f"satir_ici_{i}.js"), t or "", "w")
    _yaz(os.path.join("kaynak", "LISTE.txt"), "\n".join(liste) + "\n", "w")
    olay(f"KAYNAK: {len(adresler)} dosya, {len(satir_ici)} satır içi betik toplandı")


_DIS_YONETIM = False


def dis_yonetim():
    """main.py gibi bir üst program tanıyı kendisi kapatacaksa: indirici bitince zip'lenmez, sonraki adımlar
    (TickTick/Notion senkronizasyonu) da aynı kayda girer."""
    global _DIS_YONETIM
    _DIS_YONETIM = True


def bitir(driver=None, kesin=False):
    """Son durumu kaydeder ve her şeyi tek zip'e paketler. Döner: zip yolu."""
    global _TEE
    if not _AKTIF or _KLASOR is None:
        return None
    if driver is not None:
        try:
            _loglari_bosalt(driver)
        except Exception:
            pass
    if _DIS_YONETIM and not kesin:
        olay("indirici bitti (zip ana program sonunda)")
        return None
    olay(f"TANI BİTTİ adim={_SAYAC} ag_kaydi={_AG_GORULEN}")
    if _TEE is not None:
        sys.stdout = _TEE.asil
        _TEE = None
    zip_yol = os.path.join(os.path.dirname(_KLASOR), f"uets_tani_{os.path.basename(_KLASOR)}.zip")
    try:
        with zipfile.ZipFile(zip_yol, "w", zipfile.ZIP_DEFLATED) as z:
            for kok, _, dosyalar in os.walk(_KLASOR):
                for d in dosyalar:
                    tam = os.path.join(kok, d)
                    z.write(tam, os.path.relpath(tam, _KLASOR))
        boyut = os.path.getsize(zip_yol) / 1024 / 1024
        print(f"\n🩺 TANI DOSYASI HAZIR ({boyut:.1f} MB): {zip_yol}")
        print("   Bu zip'i gönderin. İçinde ekran görüntüleri ve tebligat listesi vardır; şifre/TCKN/kodlar maskelidir.")
        return zip_yol
    except Exception as e:
        print(f"⚠️ Tanı zip'i oluşturulamadı: {e} (klasör: {_KLASOR})")
        return None
