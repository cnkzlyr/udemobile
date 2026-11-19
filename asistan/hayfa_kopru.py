#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HAYFA Hukuk & Danışmanlık (hayfahukuk.com) Canlı Veri & Çevrimdışı Rehber Köprüsü
=================================================================================
hayfahukuk.com'daki tüm içerik ve veritabanlarını CanEditor Hukuk Asistanı'na entegre eder:
  * Hukuk Haberleri          — hayfahukuk.com/haberler (+ tam metin okuma + SQLite önbellek)
  * Resmî Gazete Bülteni     — hayfahukuk.com/resmi-gazete (günlük sayı + bölümler + PDF)
  * Yargıtay İçtihat Arama   — hayfahukuk.com/karar-arama & /karar?id=... (dilekçeye 1 tıkla ekle)
  * Mevzuat & Kanun Arama    — hayfahukuk.com/mevzuat
  * Adliye & İcra Rehberi    — gömülü asistan/veri/adliye-veri.json (100% ÇEVRİMDIŞI çalışır;
                               doğrulanmış Vakıfbank IBAN'ları, telefonlar, adresler)
"""
from __future__ import annotations

import html as html_mod
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path

SITE = "https://hayfahukuk.com"
UA = "CanEditor-HukukAsistani/4.1 (+https://hayfahukuk.com)"
KOK = Path(__file__).resolve().parent

_FOLD = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c", "Â": "a", "â": "a",
})

CACHE_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS hayfa_cache (
    anahtar TEXT PRIMARY KEY,
    veri TEXT NOT NULL,
    zaman REAL NOT NULL
);
"""


def _fold(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").translate(_FOLD).lower()).strip()


def _temiz(parca: str) -> str:
    s = re.sub(r"<(?:script|style)[^>]*>.*?</(?:script|style)>", " ", parca or "", flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_mod.unescape(s)
    satirlar = [re.sub(r"[ \t]+", " ", x).strip() for x in s.splitlines()]
    return "\n".join(x for x in satirlar if x)


def _tek_satir(parca: str) -> str:
    return re.sub(r"\s+", " ", _temiz(parca)).strip()


def _cache_db(veri_dizini: Path):
    import contextlib
    @contextlib.contextmanager
    def _cm():
        veri_dizini.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(veri_dizini / "hayfa_cache.db"), timeout=10)
        try:
            c.executescript(CACHE_SCHEMA)
            yield c
            c.commit()
        finally:
            c.close()
    return _cm()


def _cache_oku(veri_dizini: Path, anahtar: str, ttl_s: int):
    try:
        with _cache_db(veri_dizini) as c:
            r = c.execute("SELECT veri, zaman FROM hayfa_cache WHERE anahtar=?", (anahtar,)).fetchone()
            if r and (time.time() - r[1] <= ttl_s):
                return json.loads(r[0])
    except Exception:
        pass
    return None


def _cache_oku_bayat(veri_dizini: Path, anahtar: str):
    """İnternet yoksa son önbelleği döner (çevrimdışı dayanıklılık)."""
    try:
        with _cache_db(veri_dizini) as c:
            r = c.execute("SELECT veri FROM hayfa_cache WHERE anahtar=?", (anahtar,)).fetchone()
            if r:
                return json.loads(r[0])
    except Exception:
        pass
    return None


def _cache_yaz(veri_dizini: Path, anahtar: str, veri) -> None:
    try:
        with _cache_db(veri_dizini) as c:
            c.execute(
                "INSERT OR REPLACE INTO hayfa_cache(anahtar, veri, zaman) VALUES (?,?,?)",
                (anahtar, json.dumps(veri, ensure_ascii=False), time.time()),
            )
    except Exception:
        pass


def _indir(yol: str, timeout: int = 12) -> str:
    url = yol if yol.startswith("http") else (SITE + yol)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# 1. HUKUK HABERLERİ
# ---------------------------------------------------------------------------

def haberler(veri_dizini: Path, kategori: str = "", q: str = "", limit: int = 30, yenile: bool = False) -> dict:
    anahtar = f"haberler:{kategori}:{q}"
    if not yenile:
        onb = _cache_oku(veri_dizini, anahtar, ttl_s=1800)
        if onb:
            return onb

    qs = {}
    if kategori:
        qs["kategori"] = kategori
    if q:
        qs["q"] = q
    yol = "/haberler" + ("?" + urllib.parse.urlencode(qs) if qs else "")
    try:
        sayfa = _indir(yol)
    except Exception as e:
        bayat = _cache_oku_bayat(veri_dizini, anahtar)
        if bayat:
            bayat["cevrimdisi"] = True
            return bayat
        return {"haberler": [], "hata": f"hayfahukuk.com'a ulaşılamadı: {e}"}

    ogeler: list[dict] = []
    gorulen: set[str] = set()
    # news-card ve news-lead bloklarını ayrıştır
    for m in re.finditer(r'<article[^>]+class="[^"]*news-(?:card|lead)[^"]*"[^>]*>(.*?)</article>', sayfa, re.S | re.I):
        blok = m.group(1)
        hm = re.search(r'href="(/haber\?id=([a-zA-Z0-9_-]+))"', blok)
        if not hm:
            continue
        hid = hm.group(2)
        if hid in gorulen:
            continue
        gorulen.add(hid)
        baslik_m = re.search(r'<h[23][^>]*>(.*?)</h[23]>', blok, re.S | re.I)
        ozet_m = re.search(r'<p[^>]*>(.*?)</p>', blok, re.S | re.I)
        img_m = re.search(r'<img[^>]+src="([^"]+)"', blok, re.I)
        tarih_m = re.search(r'<time[^>]*>(.*?)</time>', blok, re.S | re.I)
        kaynak_m = re.search(r'class="[^"]*(?:source|kaynak|badge|tag)[^"]*"[^>]*>(.*?)</', blok, re.S | re.I)
        ogeler.append({
            "id": hid,
            "baslik": _tek_satir(baslik_m.group(1)) if baslik_m else f"Haber #{hid}",
            "ozet": _tek_satir(ozet_m.group(1))[:260] if ozet_m else "",
            "tarih": _tek_satir(tarih_m.group(1)) if tarih_m else "",
            "kaynak": _tek_satir(kaynak_m.group(1)) if kaynak_m else "HAYFA Hukuk",
            "gorsel": img_m.group(1) if img_m else "",
            "url": SITE + hm.group(1),
        })
        if len(ogeler) >= limit:
            break

    sonuc = {"haberler": ogeler, "kaynak": SITE + yol, "guncelleme": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if ogeler:
        _cache_yaz(veri_dizini, anahtar, sonuc)
    return sonuc


def haber_detay(veri_dizini: Path, hid: str) -> dict:
    hid = re.sub(r"[^a-zA-Z0-9_-]", "", str(hid or ""))
    if not hid:
        raise ValueError("Geçersiz haber kimliği")
    anahtar = f"haber:{hid}"
    onb = _cache_oku(veri_dizini, anahtar, ttl_s=86400)
    if onb:
        return onb
    sayfa = _indir(f"/haber?id={hid}")
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", sayfa, re.S | re.I)
    main = re.search(r"<article[^>]*>(.*?)</article>", sayfa, re.S | re.I) or re.search(r"<main[^>]*>(.*?)</main>", sayfa, re.S | re.I)
    sonuc = {
        "id": hid,
        "baslik": _tek_satir(h1.group(1)) if h1 else f"Haber #{hid}",
        "metin": _temiz(main.group(1))[:8000] if main else "",
        "url": f"{SITE}/haber?id={hid}",
    }
    _cache_yaz(veri_dizini, anahtar, sonuc)
    return sonuc


# ---------------------------------------------------------------------------
# 2. RESMÎ GAZETE
# ---------------------------------------------------------------------------

def resmi_gazete(veri_dizini: Path, tarih: str = "", yenile: bool = False) -> dict:
    anahtar = f"rg:{tarih or 'bugun'}"
    if not yenile:
        onb = _cache_oku(veri_dizini, anahtar, ttl_s=3600)
        if onb:
            return onb

    yol = "/resmi-gazete" + (f"?tarih={urllib.parse.quote(tarih)}" if tarih else "")
    try:
        sayfa = _indir(yol)
    except Exception as e:
        bayat = _cache_oku_bayat(veri_dizini, anahtar)
        if bayat:
            bayat["cevrimdisi"] = True
            return bayat
        return {"maddeler": [], "hata": f"Resmî Gazete alınamadı: {e}"}

    tarih_m = re.search(r'class="rg-issue"[^>]*>.*?<strong>(.*?)</strong>\s*<span>(.*?)</span>', sayfa, re.S | re.I)
    pdf_m = re.search(r'href="(https://www\.resmigazete\.gov\.tr/[^"]+\.pdf)"', sayfa, re.I)
    maddeler: list[dict] = []
    for m in re.finditer(r'<a[^>]+class="[^"]*rg-item[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', sayfa, re.S | re.I):
        href = html_mod.unescape(m.group(1))
        ic = m.group(2)
        st = re.search(r"<strong>(.*?)</strong>", ic, re.S | re.I)
        baslik = _tek_satir(st.group(1)) if st else _tek_satir(ic)
        tam_url = href if href.startswith("http") else (SITE + href)
        if baslik:
            maddeler.append({"baslik": baslik, "url": tam_url})

    sonuc = {
        "tarih_etiket": _tek_satir(tarih_m.group(1)) if tarih_m else "",
        "sayi": _tek_satir(tarih_m.group(2)) if tarih_m else "",
        "pdf_url": pdf_m.group(1) if pdf_m else "",
        "maddeler": maddeler[:100],
        "url": SITE + yol,
    }
    if maddeler:
        _cache_yaz(veri_dizini, anahtar, sonuc)
    return sonuc


# ---------------------------------------------------------------------------
# 3. YARGITAY İÇTİHAT / KARAR ARAMA
# ---------------------------------------------------------------------------

# Daire kodu → karar başlığında aranacak düzenli ifade. Sitenin "alan" süzgeci bir kodu tanımazsa (0 sonuç)
# sonuçlar filtresiz alınıp başlık/özetteki daire adına göre burada süzülür; böylece listede olmayan
# daireler de (ör. 15. Hukuk, 8. Ceza, Danıştay 6. Daire) aranabilir.
def _daire_deseni(alan: str):
    a = str(alan or "").strip()
    m = re.fullmatch(r"(\d{1,2})(HD|CD)", a, re.I)
    if m:
        tur = "hukuk" if m.group(2).upper() == "HD" else "ceza"
        return re.compile(rf"(?<!\d){int(m.group(1))}\s*\.?\s*{tur}\s+daire", re.I)
    m = re.fullmatch(r"Danistay(\d{1,2})", a, re.I)
    if m:
        return re.compile(rf"dan[ıi]ştay\s+{int(m.group(1))}\s*\.?\s*daire", re.I)
    sabit = {
        "HGK": r"hukuk\s+genel\s+kurulu", "CGK": r"ceza\s+genel\s+kurulu", "BGK": r"b[üu]y[üu]k\s+genel\s+kurul",
        "IBK": r"i[çc]tihad[ıi]\s*birle[şs]tirme", "Danistay": r"dan[ıi]ştay", "IDDK": r"idari\s+dava\s+daireleri",
        "VDDK": r"vergi\s+dava\s+daireleri", "AYM": r"anayasa\s+mahkemesi", "BAM": r"b[öo]lge\s+adliye",
        "BIM": r"b[öo]lge\s+idare", "UYM": r"uyu[şs]mazl[ıi]k\s+mahkemesi", "SAYISTAY": r"say[ıi]ştay",
    }
    return re.compile(sabit[a.upper()] if a.upper() in sabit else re.escape(a), re.I) if a else None


def karar_ara(veri_dizini: Path, q: str, alan: str = "", sayfa: int = 1) -> dict:
    sonuc = _karar_ara_ham(veri_dizini, q, alan, sayfa)
    desen = _daire_deseni(alan)
    if alan and not sonuc.get("hata") and not sonuc.get("kararlar") and desen is not None:
        # Site bu daire kodunu tanımadı: filtresiz birkaç sayfa al, daire adına göre süz
        bulunan: list[dict] = []
        for s in range(1, 6):
            ham = _karar_ara_ham(veri_dizini, q, "", (int(sayfa or 1) - 1) * 5 + s)
            kararlar = ham.get("kararlar") or []
            bulunan += [k for k in kararlar if desen.search(f"{k.get('baslik', '')} {k.get('ozet', '')} {' '.join(k.get('etiketler') or [])}")]
            if not kararlar or len(bulunan) >= 20:
                break
        sonuc = {"toplam": str(len(bulunan)), "kararlar": bulunan, "sayfa": sayfa, "suzuldu": True,
                 "url": SITE + "/karar-arama?" + urllib.parse.urlencode({"q": q})}
    return sonuc


def _karar_ara_ham(veri_dizini: Path, q: str, alan: str = "", sayfa: int = 1) -> dict:
    q = str(q or "").strip()
    if len(q) < 2:
        return {"toplam": "0", "kararlar": [], "mesaj": "Aramak için en az 2 karakter girin."}
    anahtar = f"karar_ara:{_fold(q)}:{_fold(alan)}:{sayfa}"
    onb = _cache_oku(veri_dizini, anahtar, ttl_s=3600)
    if onb:
        return onb

    qs = {"q": q, "sayfa": str(max(1, int(sayfa or 1)))}
    if alan:
        qs["alan"] = alan
    yol = "/karar-arama?" + urllib.parse.urlencode(qs)
    try:
        html = _indir(yol, timeout=35)
    except Exception as e:
        bayat = _cache_oku_bayat(veri_dizini, anahtar)
        if bayat:
            bayat["cevrimdisi"] = True
            return bayat
        return {"toplam": "0", "kararlar": [], "hata": f"Karar araması zaman aşımına uğradı veya yapılamadı: {e}"}

    say_m = re.search(r'class="result-count"[^>]*>(.*?)</', html, re.S | re.I)
    kararlar: list[dict] = []
    for m in re.finditer(r'<article[^>]+class="[^"]*result-item[^"]*"[^>]*>(.*?)</article>', html, re.S | re.I):
        blok = m.group(1)
        km = re.search(r'href="(/karar\?id=(\d+)[^"]*)"[^>]*>(.*?)</a>', blok, re.S | re.I)
        if not km:
            continue
        kid = km.group(2)
        baslik = _tek_satir(km.group(3))
        ozet_m = re.search(r'<p[^>]*>(.*?)</p>', blok, re.S | re.I)
        etiketler = [_tek_satir(x) for x in re.findall(r'class="tag[^"]*"[^>]*>(.*?)</a>', blok, re.S | re.I)][:4]
        kararlar.append({
            "id": kid,
            "baslik": baslik,
            "ozet": _tek_satir(ozet_m.group(1))[:400] if ozet_m else "",
            "etiketler": etiketler,
            "url": SITE + html_mod.unescape(km.group(1)),
        })

    sonuc = {
        "toplam": _tek_satir(say_m.group(1)) if say_m else str(len(kararlar)),
        "kararlar": kararlar,
        "sayfa": sayfa,
        "url": SITE + yol,
    }
    if kararlar:
        _cache_yaz(veri_dizini, anahtar, sonuc)
    return sonuc


def karar_detay(veri_dizini: Path, kid: str) -> dict:
    kid = re.sub(r"\D", "", str(kid or ""))
    if not kid:
        raise ValueError("Geçersiz karar kimliği")
    anahtar = f"karar:{kid}"
    onb = _cache_oku(veri_dizini, anahtar, ttl_s=86400 * 7)
    if onb:
        return onb

    html = _indir(f"/karar?id={kid}", timeout=35)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    # Karar metni bloğunu bul (tam metin korunur, asla anonimleştirilmez veya kesilmez)
    metin_m = (
        re.search(r'class="[^"]*(?:karar-metin|karar-body|decision-text|prose)[^"]*"[^>]*>(.*?)</div>', html, re.S | re.I)
        or re.search(r"<article[^>]*>(.*?)</article>", html, re.S | re.I)
        or re.search(r"<main[^>]*>(.*?)</main>", html, re.S | re.I)
    )
    tam_metin = _temiz(metin_m.group(1)) if metin_m else ""
    sonuc = {
        "id": kid,
        "baslik": _tek_satir(h1.group(1)) if h1 else f"Yargıtay Kararı #{kid}",
        "metin": tam_metin,
        "url": f"{SITE}/karar?id={kid}",
    }
    _cache_yaz(veri_dizini, anahtar, sonuc)
    return sonuc


# ---------------------------------------------------------------------------
# 4. MEVZUAT
# ---------------------------------------------------------------------------

def mevzuat_ara(veri_dizini: Path, q: str = "", tur: str = "") -> dict:
    anahtar = f"mevzuat:{_fold(q)}:{_fold(tur)}"
    onb = _cache_oku(veri_dizini, anahtar, ttl_s=3600)
    if onb:
        return onb

    qs = {}
    if q:
        qs["q"] = q
    if tur:
        qs["tur"] = tur
    yol = "/mevzuat" + ("?" + urllib.parse.urlencode(qs) if qs else "")
    try:
        html = _indir(yol, timeout=15)
    except Exception as e:
        bayat = _cache_oku_bayat(veri_dizini, anahtar)
        if bayat:
            bayat["cevrimdisi"] = True
            return bayat
        return {"mevzuat": [], "hata": f"Mevzuat alınamadı: {e}"}

    main_m = re.search(r"<main[^>]*>(.*?)</main>", html, re.S | re.I)
    govde = main_m.group(1) if main_m else html
    ogeler: list[dict] = []
    gorulen: set[str] = set()
    for m in re.finditer(r'<a[^>]+href="(/mevzuat[^"]*(?:no=|id=)[^"]+|/kanun-maddesi[^"]+)"[^>]*>(.*?)</a>', govde, re.S | re.I):
        href = html_mod.unescape(m.group(1))
        baslik = _tek_satir(m.group(2))
        if not baslik or len(baslik) < 3 or href in gorulen:
            continue
        gorulen.add(href)
        ogeler.append({"baslik": baslik, "url": SITE + href})
        if len(ogeler) >= 60:
            break

    sonuc = {"mevzuat": ogeler, "url": SITE + yol}
    if ogeler:
        _cache_yaz(veri_dizini, anahtar, sonuc)
    return sonuc


def mevzuat_detay(veri_dizini: Path, url: str) -> dict:
    url = str(url or "").strip()
    if not url:
        raise ValueError("Mevzuat bağlantısı gerekli")
    anahtar = f"mevzuat_detay:{_fold(url)}"
    onb = _cache_oku(veri_dizini, anahtar, ttl_s=86400 * 30)
    if onb:
        return onb

    yol = url.replace(SITE, "") if url.startswith(SITE) else url
    html = _indir(yol, timeout=35)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    metin_m = (
        re.search(r'class="[^"]*(?:mevzuat-metin|kanun-metin|article-body|prose)[^"]*"[^>]*>(.*?)</div>', html, re.S | re.I)
        or re.search(r"<article[^>]*>(.*?)</article>", html, re.S | re.I)
        or re.search(r"<main[^>]*>(.*?)</main>", html, re.S | re.I)
    )
    tam_metin = _temiz(metin_m.group(1)) if metin_m else ""
    sonuc = {
        "baslik": _tek_satir(h1.group(1)) if h1 else "Mevzuat Maddesi",
        "metin": tam_metin,
        "url": url if url.startswith("http") else (SITE + url)
    }
    _cache_yaz(veri_dizini, anahtar, sonuc)
    return sonuc


# ---------------------------------------------------------------------------
# 5. ÇEVRİMDIŞI ADLİYE & İCRA REHBERİ (adliye-veri.json)
# ---------------------------------------------------------------------------

_ADLIYE_CACHE: dict | None = None


def _adliye_veri_yukle() -> dict:
    global _ADLIYE_CACHE
    if _ADLIYE_CACHE is not None:
        return _ADLIYE_CACHE
    for aday in (
        KOK / "veri" / "adliye-veri.json",
        Path(getattr(__import__("sys"), "_MEIPASS", KOK)) / "veri" / "adliye-veri.json",
    ):
        if aday.is_file():
            try:
                _ADLIYE_CACHE = json.loads(aday.read_text(encoding="utf-8-sig"))
                return _ADLIYE_CACHE
            except (OSError, ValueError):
                pass
    return {"binalar": {}, "birimler": []}


def adliye_ara(q: str = "", il: str = "", tur: str = "", limit: int = 80) -> dict:
    veri = _adliye_veri_yukle()
    binalar = veri.get("binalar") or {}
    birimler = veri.get("birimler") or []
    qf, ilf, turf = _fold(q), _fold(il), _fold(tur)

    iller = sorted({b.get("il", "") for b in binalar.values() if b.get("il")})
    sonuc_binalar = []
    for kod, b in binalar.items():
        if ilf and _fold(b.get("il", "")) != ilf:
            continue
        if qf and not all(w in _fold(f"{b.get('il')} {b.get('ilce')} {b.get('adliye')} {b.get('bina')} {b.get('adres')} {b.get('aciklama')}") for w in qf.split()):
            continue
        sonuc_binalar.append({"kod": kod, **b})

    sonuc_birimler = []
    for br in birimler:
        bina = binalar.get(br.get("bina", ""), {})
        if ilf and _fold(bina.get("il", "")) != ilf:
            continue
        if turf and turf not in _fold(br.get("tur", "")):
            continue
        iban_metin = " ".join(f"{x.get('tur','')} {x.get('iban','')}" for x in (br.get("ibanlar") or []))
        havuz = _fold(f"{br.get('ad')} {br.get('tur')} {bina.get('adliye')} {bina.get('il')} {br.get('notlar')} {iban_metin}")
        if qf and not all(w in havuz for w in qf.split()):
            continue
        sonuc_birimler.append({
            **br,
            "adliye": bina.get("adliye", ""),
            "il": bina.get("il", ""),
            "adres": bina.get("adres", ""),
            "bina_telefon": bina.get("telefon", ""),
        })
        if len(sonuc_birimler) >= limit:
            break

    return {
        "olusturma": veri.get("olusturma", ""),
        "iller": iller,
        "bina_sayisi": len(binalar),
        "birim_sayisi": len(birimler),
        "binalar": sonuc_binalar[:40],
        "birimler": sonuc_birimler,
    }
