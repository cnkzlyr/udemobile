# -*- coding: utf-8 -*-
"""
UYAP → NOTION SÜREKLİ EŞİTLEME

UYAP kataloğundaki (uyap_katalog.db, 'dosya' tablosu: birim, dosya no, tür, durum, açılış, taraflar, müvekkil)
bilgileri Notion'daki üç veritabanına işler:

  📁 Tüm Dosyalar Düzenli : eksik dosya sayfası açılır; boş AÇILIŞ TARİHİ doldurulur; DURUM Açık↔Kapalı
                            eşitlenir; MÜVEKKİLLER ve DİĞER TARAFLAR ilişkileri eklenir (var olan silinmez);
                            DOSYA KONUSU boşsa 5-10 cümlelik özet yazılır (dosya_ozet.py).
  👨🏻 Müvekkiller          : UYAP'ta vekili olduğumuz taraf Notion'da yoksa eklenir.
  🧟‍♂️ Diğer Taraflar       : karşı taraf / diğer taraflar yoksa eklenir.

İKONLAR: her sayfanın ikonu kendi veritabanının ikonuyla aynı yapılır (Dosyalar 📁, Müvekkiller 👨🏻,
Diğer Taraflar 🧟‍♂️) — kullanıcının istediği "üç veritabanında tutarlı ikon".

GÜVENLİK (hiçbir şey kaybolmasın, kopya açılmasın):
  - Notion dosya listesi okunamazsa (0 kayıt) HİÇBİR ŞEY yazılmaz.
  - Bir turda açılacak yeni dosya sayısı olağandışıysa (katalogun %20'sinden ve 30'dan fazla) --zorla olmadan açılmaz.
  - Kullanıcının elle yazdığı DOSYA KONUSU ezilmez: yalnızca boşsa ya da en son bu modülün yazdığı metinle
    birebir aynıysa (yerel 'konu' tablosu) güncellenir.
  - İlişkiler yalnızca EKLENİR; Notion'daki ilişki hiçbir zaman kaldırılmaz.

Kullanım:  python notion_uyap.py            (önizleme: ne yapacağını yazar, Notion'a dokunmaz)
           python notion_uyap.py --uygula   (yazar)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parent
# Sunucu, görevlere modüllerin YAZILABİLİR (eşitlenmiş) kopyasını bildirir; paketli kurulumda KOK salt-okunurdur
AVUKAT_DIR = Path(os.environ.get("CANASISTAN_AVUKAT_DIR") or KOK / "moduller" / "avukatasistan")
EVRAK_DIR = Path(os.environ.get("CANASISTAN_EVRAK_DIR") or KOK / "moduller" / "evrak")
sys.path.insert(0, str(KOK))

import dosya_ozet  # noqa: E402

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
_SON_ISTEK = [0.0]


def veri_dizini() -> Path:
    return Path(os.environ.get("UYAP_VERI_DIZINI") or EVRAK_DIR)


def katalog_yolu() -> Path:
    return veri_dizini() / "uyap_katalog.db"


def durum_db() -> sqlite3.Connection:
    """Yerel eşleme/konu kaydı: Notion'a en son ne yazıldığını tutar (kullanıcı metnini ezmemek için)."""
    c = sqlite3.connect(str(veri_dizini() / "notion_uyap.db"), timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS esleme(dkey TEXT PRIMARY KEY, page_id TEXT, url TEXT, baslik TEXT,
                 konu TEXT, konu_kaynak TEXT, guncelleme TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS konu(dkey TEXT PRIMARY KEY, yazilan TEXT, ozet_hash TEXT, kaynak TEXT, zaman TEXT)""")
    return c


def fold(s) -> str:
    s = str(s or "").translate(str.maketrans("İIıŞşĞğÜüÖöÇçÂâÎîÛû", "iiissgguuooccaaiiuu"))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def esas_norm(s) -> str:
    m = re.search(r"(\d{4})\s*/\s*(\d+)", str(s or ""))
    return f"{m.group(1)}/{int(m.group(2))}" if m else ""


def map_dosya_turu(birim: str) -> str:
    """Mahkeme adından Notion 'DOSYA TÜRÜ' seçeneği (sync_uyap_excel ile aynı kurallar)."""
    c = fold(birim)
    kurallar = [
        (("fikri ve sinai",), lambda: "Fikri ve Sınai Haklar Ceza" if "ceza" in c else "Fikri ve Sınai Haklar Hukuk"),
        (("bolge adliye",), lambda: "BAM Ceza" if "ceza" in c else "BAM Hukuk"),
        (("yargitay",), lambda: "Yargıtay Ceza" if "ceza" in c else "Yargıtay Hukuk"),
        (("danistay",), lambda: "Danıştay"),
        (("bolge idare",), lambda: "BİM Vergi" if "vergi" in c else "BİM İdare"),
        (("cocuk",), lambda: "Çocuk Mahkemesi"),
        (("agir ceza", "infaz"), lambda: "Ağır Ceza Mahkemesi"),
        (("asliye ceza", "sulh ceza"), lambda: "Asliye Ceza Mahkemesi"),
        (("asliye ticaret",), lambda: "Asliye Ticaret Mahkemesi"),
        (("asliye hukuk",), lambda: "Asliye Hukuk Mahkemesi"),
        (("is mahkemesi",), lambda: "İş Mahkemesi"),
        (("aile",), lambda: "Aile Mahkemesi"),
        (("tuketici",), lambda: "Tüketici Mahkemesi"),
        (("sulh hukuk",), lambda: "Sulh Hukuk Mahkemesi"),
        (("icra hukuk",), lambda: "İcra Hukuk Mahkemesi"),
        (("icra",), lambda: "İcra Takibi"),
        (("idare",), lambda: "İdare Mahkemesi"),
        (("vergi",), lambda: "Vergi Mahkemesi"),
        (("kadastro",), lambda: "Kadastro Mahkemesi"),
        (("arabulucu",), lambda: "Arabuluculuk"),
        (("bassavcilig", "savcilig", "sorusturma"), lambda: "Soruşturma"),
    ]
    for anahtarlar, f in kurallar:
        if any(a in c for a in anahtarlar):
            return f()
    return ""


# --------------------------------------------------------------------------- Notion HTTP
class Notion:
    def __init__(self, token: str):
        self.h = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION, "Content-Type": "application/json"}
        self.istek = 0

    def __call__(self, method: str, yol: str, govde: dict | None = None) -> dict:
        """Notion'a istek: saniyede ~3 istek sınırına uyar, 429/5xx'te bekleyip 4 kez dener."""
        for deneme in range(5):
            bekle = 0.36 - (time.time() - _SON_ISTEK[0])
            if bekle > 0:
                time.sleep(bekle)
            _SON_ISTEK[0] = time.time()
            veri = json.dumps(govde, ensure_ascii=False).encode("utf-8") if govde is not None else None
            req = urllib.request.Request(NOTION_API + yol, data=veri, headers=self.h, method=method)
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    self.istek += 1
                    ham = r.read().decode("utf-8", errors="replace")
                    return json.loads(ham) if ham.strip() else {}
            except urllib.error.HTTPError as e:
                detay = e.read().decode("utf-8", errors="replace")[:300]
                if e.code in (429, 500, 502, 503, 504) and deneme < 4:
                    time.sleep(float(e.headers.get("Retry-After") or 0) or 2 * (deneme + 1))
                    continue
                raise RuntimeError(f"Notion HTTP {e.code}: {detay}") from e
            except urllib.error.URLError as e:
                if deneme < 4:
                    time.sleep(3 * (deneme + 1))
                    continue
                raise RuntimeError(f"Notion bağlantı hatası: {e.reason}") from e
        raise RuntimeError("Notion yanıt vermedi")

    def tum_sayfalar(self, db_id: str) -> list:
        sayfalar, cursor = [], None
        for _ in range(400):  # 40.000 kayda kadar
            govde: dict = {"page_size": 100}
            if cursor:
                govde["start_cursor"] = cursor
            v = self("POST", f"/databases/{db_id}/query", govde)
            sayfalar += v.get("results") or []
            if not v.get("has_more"):
                return sayfalar
            cursor = v.get("next_cursor")
        return sayfalar


def _metin(prop: dict) -> str:
    if not isinstance(prop, dict):
        return ""
    t = prop.get("type")
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in prop.get(t) or [])
    if t == "formula":
        f = prop.get("formula") or {}
        return str(f.get("string") or f.get("number") or "")
    if t == "select":
        return (prop.get("select") or {}).get("name") or ""
    if t == "date":
        return (prop.get("date") or {}).get("start") or ""
    return ""


def _baslik_prop(props: dict) -> str:
    for ad, p in (props or {}).items():
        if isinstance(p, dict) and p.get("type") == "title":
            return ad
    return ""


def _ikon(sayfa: dict) -> str:
    i = sayfa.get("icon") or {}
    return i.get("emoji") or "" if i.get("type") == "emoji" else ""


# --------------------------------------------------------------------------- UYAP katalog
def katalog_dosyalari() -> list:
    p = katalog_yolu()
    if not p.is_file():
        return []
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=30)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(
            "SELECT dkey, birim, dosya_no, dosya_tur, durum, acilis, taraflar, muvekkil FROM dosya "
            "WHERE COALESCE(birim,'')!='' AND COALESCE(dosya_no,'')!='' ORDER BY durum='Açık' DESC, acilis DESC").fetchall()]
    except sqlite3.Error:
        return []
    finally:
        c.close()


def taraf_ayir(taraf_txt: str, muv_txt: str) -> tuple[list, list]:
    """(müvekkil adları, karşı/diğer taraf adları). Kurumlar ve kişiler aynı muamele görür; boş/anonim atlanır."""
    muv = {m.strip() for m in (muv_txt or "").split(";") if m.strip()}
    biz, karsi = [], []
    for p in (taraf_txt or "").split(";"):
        p = p.strip()
        m = re.match(r"^(.*?)\s*\(([^()]*)\)", p)
        if not m:
            continue
        ad = re.sub(r"\s+", " ", m.group(1)).strip()
        if len(ad) < 3 or fold(ad) in ("kamu", "k h", "mustenit"):
            continue
        hedef = biz if f"{m.group(1).strip()} ({m.group(2).strip()})" in muv else karsi
        if fold(ad) not in {fold(x) for x in hedef}:
            hedef.append(ad)
    return biz, karsi


# --------------------------------------------------------------------------- eşitleme
def esitle(uygula: bool = False, zorla: bool = False, konu_sinir: int = 60, ikon_sinir: int = 400, log=print) -> dict:
    sys.path.insert(0, str(KOK))
    import entegrasyon  # noqa: WPS433
    ayar = entegrasyon.env_oku(AVUKAT_DIR)
    token = (ayar.get("NOTION_TOKEN") or "").strip()
    if not token:
        raise SystemExit("Notion anahtarı yok (Entegrasyonlar sekmesinden girin).")
    db_dosya = (ayar.get("NOTION_DB_DOSYALAR") or entegrasyon.VARSAYILAN_NOTION_DB).strip()
    n = Notion(token)
    rapor = {"mod": "uygula" if uygula else "onizleme", "yeni_dosya": 0, "tarih": 0, "durum": 0, "muvekkil_bag": 0,
             "karsi_bag": 0, "yeni_muvekkil": 0, "yeni_karsi": 0, "konu": 0, "ikon": 0, "engel": None, "hatalar": []}

    # 1) Veritabanı şemaları: ilişkili veritabanları ve ikonları Dosyalar şemasından bulunur (sabit kimlik yok)
    sema = n("GET", f"/databases/{db_dosya}")
    props = sema.get("properties") or {}
    db_muv = ((props.get("MÜVEKKİLLER") or {}).get("relation") or {}).get("database_id")
    db_karsi = ((props.get("DİĞER TARAFLAR") or {}).get("relation") or {}).get("database_id")
    ikon_dosya = ((sema.get("icon") or {}).get("emoji")) or "📁"
    sema_m = n("GET", f"/databases/{db_muv}") if db_muv else {}
    sema_k = n("GET", f"/databases/{db_karsi}") if db_karsi else {}
    ikon_muv = ((sema_m.get("icon") or {}).get("emoji")) or "👨🏻"
    ikon_karsi = ((sema_k.get("icon") or {}).get("emoji")) or "🧟‍♂️"
    tprop_muv = _baslik_prop(sema_m.get("properties")) or "Name"
    tprop_karsi = _baslik_prop(sema_k.get("properties")) or "Diğer Taraflar"

    # 2) Notion'daki mevcut kayıtlar
    sayfalar = n.tum_sayfalar(db_dosya)
    log(f"[i] Notion: {len(sayfalar)} dosya sayfası okundu.")
    muv_sayfa = n.tum_sayfalar(db_muv) if db_muv else []
    karsi_sayfa = n.tum_sayfalar(db_karsi) if db_karsi else []
    log(f"[i] Notion: {len(muv_sayfa)} müvekkil, {len(karsi_sayfa)} diğer taraf okundu.")
    if not sayfalar:
        rapor["engel"] = "Notion dosya listesi okunamadı (0 kayıt): güvenlik için hiçbir şey yazılmadı."
        log("🛑 " + rapor["engel"])
        return rapor
    muv_ad = {fold(_metin((p.get("properties") or {}).get(tprop_muv))): p["id"] for p in muv_sayfa}
    karsi_ad = {fold(_metin((p.get("properties") or {}).get(tprop_karsi))): p["id"] for p in karsi_sayfa}
    muv_ad.pop("", None)
    karsi_ad.pop("", None)

    def notion_dosya(p: dict) -> dict:
        pr = p.get("properties") or {}
        baslik = _metin(pr.get("NOTION DOSYA"))
        mahkeme, esas = _metin(pr.get("MAHKEME/BİRİM")), _metin(pr.get("DOSYA NO"))
        if (not mahkeme or not esas) and " - " in baslik:
            parca = baslik.split(" - ")
            mahkeme, esas = mahkeme or parca[0], esas or parca[-1]
        return {"id": p["id"], "url": p.get("url", ""), "baslik": baslik, "mahkeme": mahkeme, "esas": esas_norm(esas or baslik),
                "durum": _metin(pr.get("DURUM")), "acilis": _metin(pr.get("AÇILIŞ TARİHİ")), "konu": _metin(pr.get("DOSYA KONUSU")),
                "muv": [x["id"] for x in (pr.get("MÜVEKKİLLER") or {}).get("relation") or []],
                "karsi": [x["id"] for x in (pr.get("DİĞER TARAFLAR") or {}).get("relation") or []],
                "ikon": _ikon(p)}
    nd = [notion_dosya(p) for p in sayfalar]
    esas_index: dict = {}
    for d in nd:
        if d["esas"]:
            esas_index.setdefault(d["esas"], []).append(d)

    def eslestir(k: dict) -> dict | None:
        adaylar = esas_index.get(esas_norm(k["dosya_no"])) or []
        fb = fold(k["birim"])
        for d in adaylar:
            fm = fold(d["mahkeme"] or d["baslik"])
            if fm and (fm == fb or fm in fb or fb in fm):
                return d
        return None

    katalog = katalog_dosyalari()
    log(f"[i] UYAP kataloğu: {len(katalog)} dosya.")
    if not katalog:
        rapor["engel"] = "UYAP kataloğu boş (önce Senkron ile UYAP taranmalı)."
        return rapor
    eksik = [k for k in katalog if not eslestir(k)]
    if eksik and not zorla and len(eksik) > max(30, len(katalog) // 5):
        rapor["engel"] = (f"{len(eksik)} dosya Notion'da yok (olağandışı çok): yeni sayfa açılmadı. "
                          "Kontrol edip 'Notion'a zorla aktar' ile onaylayın.")
        log("🛑 " + rapor["engel"])
        eksik_ac = []
    else:
        eksik_ac = eksik
    dur = durum_db()

    def bag_id(ad: str, tablo: dict, db_id: str, tprop: str, ikon: str, sayac: str) -> str | None:
        f = fold(ad)
        if f in tablo:
            return tablo[f]
        if not uygula or not db_id:
            gorulen = rapor.setdefault("_onizleme_" + sayac, set())
            if f not in gorulen:
                gorulen.add(f)
                rapor[sayac] += 1
            return None
        yeni = n("POST", "/pages", {"parent": {"database_id": db_id}, "icon": {"type": "emoji", "emoji": ikon},
                                     "properties": {tprop: {"title": [{"text": {"content": ad[:200]}}]}}})
        tablo[f] = yeni["id"]
        rapor[sayac] += 1
        return yeni["id"]

    # 3) Eksik dosya sayfaları
    for k in eksik_ac:
        tur = map_dosya_turu(k["birim"])
        pr: dict = {"NOTION DOSYA": {"title": [{"text": {"content": f"{k['birim']} - {k['dosya_no']}"}}]}}
        if tur:
            pr["DOSYA TÜRÜ"] = {"select": {"name": tur}}
        if k.get("durum") in ("Açık", "Kapalı"):
            pr["DURUM"] = {"select": {"name": k["durum"]}}
        if re.match(r"\d{4}-\d{2}-\d{2}", k.get("acilis") or ""):
            pr["AÇILIŞ TARİHİ"] = {"date": {"start": k["acilis"][:10]}}
        log(f"  ➕ Notion'a eklenecek: {k['birim']} - {k['dosya_no']}")
        rapor["yeni_dosya"] += 1
        if uygula:
            try:
                y = n("POST", "/pages", {"parent": {"database_id": db_dosya}, "icon": {"type": "emoji", "emoji": ikon_dosya},
                                         "properties": pr})
                d = notion_dosya(y)
                d["esas"] = esas_norm(k["dosya_no"])
                d["mahkeme"] = k["birim"]
                esas_index.setdefault(d["esas"], []).append(d)
                nd.append(d)
            except RuntimeError as e:
                rapor["hatalar"].append(f"{k['dosya_no']}: {e}")

    # 4) Mevcut sayfaların eksiklerini tamamla (tarih, durum, ilişkiler, konu)
    konu_yazilan = 0
    katalog_db = None
    for k in katalog:
        d = eslestir(k)
        if not d:
            continue
        guncel: dict = {}
        if not d["acilis"] and re.match(r"\d{4}-\d{2}-\d{2}", k.get("acilis") or ""):
            guncel["AÇILIŞ TARİHİ"] = {"date": {"start": k["acilis"][:10]}}
            rapor["tarih"] += 1
        nd_d, kd = d["durum"], k.get("durum") or ""
        if kd in ("Açık", "Kapalı") and (not nd_d or (nd_d == "Açık" and kd == "Kapalı") or (nd_d == "Kapalı" and kd == "Açık")) and nd_d != kd:
            guncel["DURUM"] = {"select": {"name": kd}}
            rapor["durum"] += 1
        biz, karsi = taraf_ayir(k.get("taraflar") or "", k.get("muvekkil") or "")
        yeni_muv = [i for i in (bag_id(a, muv_ad, db_muv, tprop_muv, ikon_muv, "yeni_muvekkil") for a in biz) if i and i not in d["muv"]]
        yeni_karsi = [i for i in (bag_id(a, karsi_ad, db_karsi, tprop_karsi, ikon_karsi, "yeni_karsi") for a in karsi[:12]) if i and i not in d["karsi"]]
        if yeni_muv and len(d["muv"]) < 25:   # Notion sorgu yanıtı ilişkileri 25'te keser: eksik okunmuş listeyi ezmemek için
            guncel["MÜVEKKİLLER"] = {"relation": [{"id": i} for i in d["muv"] + yeni_muv]}
            rapor["muvekkil_bag"] += 1
        if yeni_karsi and len(d["karsi"]) < 25:
            guncel["DİĞER TARAFLAR"] = {"relation": [{"id": i} for i in d["karsi"] + yeni_karsi]}
            rapor["karsi_bag"] += 1
        # Dosya konusu (özet)
        onceki = dur.execute("SELECT yazilan FROM konu WHERE dkey=?", (k["dkey"],)).fetchone()
        mevcut = (d["konu"] or "").strip()
        bizim = bool(onceki and onceki["yazilan"] and onceki["yazilan"].strip() == mevcut)
        ozet = None
        if (not mevcut or bizim) and konu_yazilan < konu_sinir:
            try:
                if katalog_db is None:
                    katalog_db = sqlite3.connect(f"file:{katalog_yolu()}?mode=ro", uri=True, timeout=30)
                ozet = dosya_ozet.ozetle(katalog_db, k["dkey"], ayar)
            except Exception as e:  # noqa: BLE001
                rapor["hatalar"].append(f"Özet {k['dosya_no']}: {e}")
            if ozet and ozet["metin"] and ozet["metin"].strip() != mevcut:
                guncel["DOSYA KONUSU"] = {"rich_text": [{"text": {"content": ozet["metin"][:1990]}}]}
                konu_yazilan += 1
                rapor["konu"] += 1
        if not d["ikon"] or d["ikon"] != ikon_dosya:
            rapor["ikon"] += 1
        if uygula and (guncel or (d["ikon"] != ikon_dosya and rapor["ikon"] <= ikon_sinir)):
            try:
                g = {"properties": guncel} if guncel else {}
                if d["ikon"] != ikon_dosya:
                    g["icon"] = {"type": "emoji", "emoji": ikon_dosya}
                n("PATCH", f"/pages/{d['id']}", g)
                if "DOSYA KONUSU" in guncel:
                    dur.execute("INSERT OR REPLACE INTO konu(dkey, yazilan, ozet_hash, kaynak, zaman) VALUES(?,?,?,?,datetime('now'))",
                                (k["dkey"], ozet["metin"][:1990], hashlib.sha1(ozet["metin"].encode()).hexdigest(), ozet["kaynak"]))
            except RuntimeError as e:
                rapor["hatalar"].append(f"{d['baslik'][:50]}: {e}")
        konu_son = (ozet["metin"][:1990] if ozet and "DOSYA KONUSU" in guncel else mevcut)
        kaynak = (ozet["kaynak"] if ozet and "DOSYA KONUSU" in guncel else ("Notion" if mevcut and not bizim else
                  (dur.execute("SELECT kaynak FROM konu WHERE dkey=?", (k["dkey"],)).fetchone() or {"kaynak": "Notion"})["kaynak"]))
        dur.execute("INSERT OR REPLACE INTO esleme(dkey, page_id, url, baslik, konu, konu_kaynak, guncelleme) VALUES(?,?,?,?,?,?,datetime('now'))",
                    (k["dkey"], d["id"], d["url"], d["baslik"], konu_son, kaynak))
    dur.commit()

    # 5) Müvekkiller / Diğer Taraflar ikonlarını veritabanı ikonuyla aynı yap
    for sayfalar_x, ikon in ((muv_sayfa, ikon_muv), (karsi_sayfa, ikon_karsi)):
        for p in sayfalar_x:
            if _ikon(p) != ikon:
                rapor["ikon"] += 1
                if uygula and rapor["ikon"] <= ikon_sinir:
                    try:
                        n("PATCH", f"/pages/{p['id']}", {"icon": {"type": "emoji", "emoji": ikon}})
                    except RuntimeError as e:
                        rapor["hatalar"].append(f"İkon: {e}")
    if katalog_db is not None:
        katalog_db.close()
    log(f"[✓] {'Uygulandı' if uygula else 'Önizleme'}: yeni dosya {rapor['yeni_dosya']}, açılış tarihi {rapor['tarih']}, "
        f"durum {rapor['durum']}, müvekkil bağı {rapor['muvekkil_bag']} (yeni müvekkil {rapor['yeni_muvekkil']}), "
        f"karşı taraf bağı {rapor['karsi_bag']} (yeni {rapor['yeni_karsi']}), konu {rapor['konu']}, ikon {rapor['ikon']}"
        + (f", {len(rapor['hatalar'])} hata" if rapor["hatalar"] else ""))
    for k in [x for x in rapor if x.startswith("_onizleme_")]:
        rapor.pop(k)
    for h in rapor["hatalar"][:15]:
        log("   ⚠️ " + h)
    return rapor


def konu_getir(dkey: str) -> dict | None:
    """Sunucu/TickTick için: bu dosyanın Notion'daki (ya da yazılan) konusu ve Notion bağlantısı."""
    p = veri_dizini() / "notion_uyap.db"
    if not p.is_file():
        return None
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        r = c.execute("SELECT konu, konu_kaynak, url, page_id FROM esleme WHERE dkey=?", (dkey,)).fetchone()
        return {"metin": r["konu"] or "", "kaynak": r["konu_kaynak"] or "", "url": r["url"] or "", "page_id": r["page_id"]} if r else None
    except sqlite3.Error:
        return None
    finally:
        c.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="UYAP kataloğu → Notion (Dosyalar, Müvekkiller, Diğer Taraflar)")
    ap.add_argument("--uygula", action="store_true", help="Notion'a yaz (yoksa önizleme)")
    ap.add_argument("--zorla", action="store_true", help="Olağandışı çok yeni dosya olsa da aç")
    ap.add_argument("--konu-sinir", type=int, default=60, help="Bir turda yazılacak en çok konu özeti")
    a = ap.parse_args()
    try:
        r = esitle(uygula=a.uygula, zorla=a.zorla, konu_sinir=a.konu_sinir, log=lambda m: print(m, flush=True))
    except RuntimeError as e:
        print(f"[!] {e}", flush=True)
        return 2
    print("@@SONUC@@" + json.dumps(r, ensure_ascii=False), flush=True)
    return 0 if not r.get("engel") else 1


if __name__ == "__main__":
    sys.exit(main())
