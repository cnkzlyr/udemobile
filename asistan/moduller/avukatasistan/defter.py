#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📚 DOSYA DEFTERİ — tüm dosyaların, tarafların, tebligatların ve duruşmaların kalıcı kaydı.

Bugün tablette tek bir dosyada (SQLite) durur; ileride Plesk hostingdeki MySQL/MariaDB (ya da PostgreSQL)
veritabanına TEK AYAR değiştirerek taşınır. Kod iki ortamda da aynıdır.

    Tablet (varsayılan):  DEFTER_URL yok  ->  <proje>/veri/defter.db
    Plesk (MySQL):        DEFTER_URL=mysql+pymysql://KULLANICI:SIFRE@SUNUCU:3306/VERITABANI?charset=utf8mb4
    PostgreSQL:           DEFTER_URL=postgresql+psycopg2://KULLANICI:SIFRE@SUNUCU:5432/VERITABANI

Taşıma:  python3 asistan.py defter tasi "mysql+pymysql://..."   (tablolar orada oluşturulur, kayıtlar kopyalanır)

Tablolar:
  dosyalar      her UYAP dosyası (birim + esas tekil): tür, durum, açılış, ilk/son görüldüğü liste, müvekkil
  taraflar      dosyadaki her taraf: sıra, rol (Davacı, Sanık...), ad, müvekkilimiz mi
  durum_gecmisi durum değişiklikleri (Açık -> Kapalı ...), hangi listede görüldüğü
  aktarimlar    işlenen her UYAP listesi: dosya adı, özeti (aynı liste iki kez işlenmez), sayılar
  tebligatlar   UETS'den gelen her tebligat: barkod/UETS no, dosya, geliş, son gün, TickTick görevi
  durusmalar    AJANDA takviminden gelen duruşmalar: takvim kimliği, dosya, tarih-saat, TickTick görevi
  uyarilar      gönderilmiş uyarılar (aynı uyarı tekrar tekrar gönderilmesin)
"""

import hashlib
import os
import re
from datetime import datetime

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, MetaData, String, Table, Text,
                        UniqueConstraint, create_engine, func, insert, select, update, delete)

HERE = os.path.dirname(os.path.abspath(__file__))
meta = MetaData()

dosyalar = Table(
    "dosyalar", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("anahtar", String(190), nullable=False, unique=True),   # birim|esas (sadeleştirilmiş)
    Column("birim", String(255), nullable=False),
    Column("esas", String(64), nullable=False, index=True),
    Column("tur", String(120)),
    Column("durum", String(120)),          # sadeleştirilmiş: Açık, Kapalı, İstinafta ...
    Column("ham_durum", String(255)),      # UYAP'taki metin: "Kapalı (Haricen Tahsil)(10/12/2024)"
    Column("acilis", String(10)),          # YYYY-MM-DD
    Column("muvekkil", String(255)),       # Notion Müvekkiller eşleşmesi (ad)
    Column("muvekkil_etiket", String(120)),
    Column("notion_id", String(64)),
    Column("ilk_gorulme", DateTime),
    Column("son_gorulme", DateTime),
    Column("listede", Boolean, default=True),  # son işlenen listede var mı
)

taraflar = Table(
    "taraflar", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("dosya_id", Integer, ForeignKey("dosyalar.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("sira", Integer),
    Column("rol", String(120)),
    Column("ad", String(255), nullable=False),
    Column("ad_norm", String(255), nullable=False, index=True),
    Column("muvekkil_mi", Boolean),        # None: bilinmiyor
)

durum_gecmisi = Table(
    "durum_gecmisi", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("dosya_id", Integer, ForeignKey("dosyalar.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("eski", String(255)),
    Column("yeni", String(255)),
    Column("tarih", DateTime, nullable=False),
    Column("kaynak", String(255)),
)

aktarimlar = Table(
    "aktarimlar", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("dosya_adi", String(255)),
    Column("ozet", String(64), unique=True),   # içeriğin SHA-256'sı
    Column("tarih", DateTime, nullable=False),
    Column("dosya_sayisi", Integer),
    Column("yeni", Integer),
    Column("degisen", Integer),
    Column("listeden_cikan", Integer),
)

tebligatlar = Table(
    "tebligatlar", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("anahtar", String(190), nullable=False, unique=True),   # barkod ya da UETS:<no>
    Column("barkod", String(32), index=True),
    Column("uets_no", String(64)),
    Column("birim", String(255)),
    Column("esas", String(64), index=True),
    Column("konu", Text),
    Column("gelis", DateTime),
    Column("son_gun", String(10)),
    Column("ticktick_id", String(64)),
    Column("eyp_yolu", Text),
    Column("kayit", DateTime),
)

durusmalar = Table(
    "durusmalar", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("takvim_uid", String(190), unique=True),
    Column("birim", String(255)),
    Column("esas", String(64), index=True),
    Column("baslangic", DateTime),
    Column("baslik", Text),
    Column("yer", Text),
    Column("ticktick_id", String(64)),
    Column("guncelleme", DateTime),
    Column("iptal", Boolean, default=False),
)

uyarilar = Table(
    "uyarilar", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("anahtar", String(190), unique=True),
    Column("metin", Text),
    Column("tarih", DateTime),
)

_ENGINE = None


def varsayilan_url():
    yol = os.path.join(HERE, "veri", "defter.db")
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    return "sqlite:///" + yol


def motor(url=None):
    """Veritabanı bağlantısı (ilk çağrıda tablolar yoksa oluşturulur)."""
    global _ENGINE
    if url:
        e = create_engine(url, future=True, pool_pre_ping=True)
        meta.create_all(e)
        return e
    if _ENGINE is None:
        u = os.environ.get("DEFTER_URL") or varsayilan_url()
        _ENGINE = create_engine(u, future=True, pool_pre_ping=True)
        meta.create_all(_ENGINE)
    return _ENGINE


def sifirla_baglanti():
    global _ENGINE
    if _ENGINE is not None:
        try:
            _ENGINE.dispose()
        except Exception:
            pass
    _ENGINE = None


# ---------------------------------------------------------------- yardımcılar
_TR = str.maketrans("çğıöşüÇĞİÖŞÜâÂîÎûÛ", "cgiosuCGIOSUaAiIuU")


def norm(metin):
    """Karşılaştırma için: Türkçe harfler sadeleşir, büyük harf, noktalama ve fazla boşluk atılır."""
    s = str(metin or "").translate(_TR).upper()
    s = re.sub(r"[^A-Z0-9/ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def dosya_anahtari(birim, esas):
    return f"{norm(birim)}|{str(esas or '').strip()}"[:190]


def _rol_ad(satir):
    """'2. Davalı:TÜRKİYE ZİRAAT ODALARI BİRLİĞİ' -> (2, 'Davalı', 'TÜRKİYE ZİRAAT ODALARI BİRLİĞİ')"""
    s = str(satir or "").strip()
    m = re.match(r"^\s*(\d+)\.\s*([^:]+):\s*(.+)$", s)
    if m:
        return int(m.group(1)), m.group(2).strip(), m.group(3).strip()
    return None, "", re.sub(r"^\d+\.\s*", "", s)


def dosya_ozeti(yol):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(65536), b""):
            h.update(parca)
    return h.hexdigest()


# ---------------------------------------------------------------- UYAP listesi
def _muvekkil_mi(ad_norm, muv_kume, muv_uzun):
    """Taraf müvekkilimiz mi? Birebir eşleşme; uzun (şirket) adlarda içerme. Kısa kişi adlarında içerme YOK
    ("MURAT GÜL" ≠ "MURAT GÜLER")."""
    if ad_norm in muv_kume:
        return True
    if len(ad_norm) >= 15:
        return any(m in ad_norm or ad_norm in m for m in muv_uzun)
    return False


def liste_aktar(dosya_listesi, dosya_adi="", ozet=None, muvekkil_bul=None, tekrar=False, muvekkil_adlari=None):
    """UYAP dosya listesini (sync_uyap_excel.parse_uyap_excel çıktısı) deftere işler.

    muvekkil_bul(taraf_satirlari) -> {"name":..., "tag":...} | None  (Notion Müvekkiller eşleşmesi; yoksa atlanır)
    muvekkil_adlari: tüm müvekkil adları; verilirse her taraf için "müvekkilimiz mi" ayrı ayrı belirlenir
                     (bir dosyada birden çok müvekkil olabilir). Verilmezse bilinmiyor (None) kalır.
    Döner: {"yeni": [...], "durum_degisen": [(dosya, eski, yeni)], "listeden_cikan": [...], "toplam": n,
            "atlandi": bool}
    """
    e = motor()
    muv_kume = {norm(a) for a in (muvekkil_adlari or []) if norm(a)}
    muv_uzun = [m for m in muv_kume if len(m) >= 15]
    simdi = datetime.now().replace(microsecond=0)
    sonuc = {"yeni": [], "durum_degisen": [], "listeden_cikan": [], "toplam": len(dosya_listesi), "atlandi": False}
    with e.begin() as c:
        if ozet and not tekrar and c.execute(select(aktarimlar.c.id).where(aktarimlar.c.ozet == ozet)).first():
            sonuc["atlandi"] = True      # aynı liste daha önce işlendi
            return sonuc
        mevcut = {r.anahtar: r for r in c.execute(select(dosyalar)).all()}
        gorulen = set()
        for d in dosya_listesi:
            birim, esas = (d.get("birim") or "").strip(), (d.get("dosya_no") or "").strip()
            if not birim or not esas:
                continue
            an = dosya_anahtari(birim, esas)
            if an in gorulen:
                continue
            gorulen.add(an)
            alanlar = {"birim": birim, "esas": esas, "tur": d.get("tur") or None, "durum": d.get("durum") or None,
                       "ham_durum": d.get("raw_durum") or None, "acilis": d.get("acilis_iso"),
                       "son_gorulme": simdi, "listede": True}
            m = muvekkil_bul(d.get("taraflar") or []) if muvekkil_bul else None
            if m:
                alanlar["muvekkil"] = m.get("name")
                alanlar["muvekkil_etiket"] = m.get("tag")
            eski = mevcut.get(an)
            if eski is None:
                did = c.execute(insert(dosyalar).values(anahtar=an, ilk_gorulme=simdi, **alanlar)).inserted_primary_key[0]
                sonuc["yeni"].append(f"{birim} {esas}")
            else:
                did = eski.id
                if (eski.durum or "") != (alanlar["durum"] or ""):
                    c.execute(insert(durum_gecmisi).values(dosya_id=did, eski=eski.ham_durum or eski.durum,
                                                          yeni=alanlar["ham_durum"] or alanlar["durum"],
                                                          tarih=simdi, kaynak=dosya_adi))
                    sonuc["durum_degisen"].append((f"{birim} {esas}", eski.durum, alanlar["durum"]))
                c.execute(update(dosyalar).where(dosyalar.c.id == did).values(**alanlar))
            # Taraflar: listedeki hâliyle yenilenir
            c.execute(delete(taraflar).where(taraflar.c.dosya_id == did))
            muv_norm = norm(m.get("name")) if m else ""
            satirlar = [(_rol_ad(x)) for x in (d.get("taraflar") or [])]
            bayraklar = [(_muvekkil_mi(norm(ad), muv_kume, muv_uzun) if muv_kume else None) for _, _, ad in satirlar]
            dosyada_muvekkil_var = any(bayraklar) or bool(muv_norm)
            for (sira, rol, ad), bayrak in zip(satirlar, bayraklar):
                if not ad:
                    continue
                an_ad = norm(ad)
                if muv_kume:
                    # Müvekkili belli olan dosyada diğer taraflar "müvekkil değil"; hiç müvekkil bulunamayan
                    # dosyada bilinmiyor (None) kalır.
                    muv = True if bayrak else (False if dosyada_muvekkil_var else None)
                elif muv_norm:
                    muv = an_ad == muv_norm or (len(muv_norm) >= 15 and (muv_norm in an_ad or an_ad in muv_norm))
                else:
                    muv = None
                c.execute(insert(taraflar).values(dosya_id=did, sira=sira, rol=rol, ad=ad, ad_norm=an_ad, muvekkil_mi=muv))
        for an, r in mevcut.items():
            if an not in gorulen and r.listede:
                c.execute(update(dosyalar).where(dosyalar.c.id == r.id).values(listede=False))
                sonuc["listeden_cikan"].append(f"{r.birim} {r.esas}")
        if ozet:
            c.execute(insert(aktarimlar).values(dosya_adi=dosya_adi, ozet=ozet, tarih=simdi, dosya_sayisi=len(gorulen),
                                                yeni=len(sonuc["yeni"]), degisen=len(sonuc["durum_degisen"]),
                                                listeden_cikan=len(sonuc["listeden_cikan"])))
    return sonuc


def aktarim_sil(ozet):
    """Yarıda kalan bir UYAP listesi işlemesinin kaydını siler: liste bir sonraki turda yeniden işlenir.
    (Dosya/taraf kayıtları kalır; yeniden işleme aynı sonucu yazar.)"""
    if not ozet:
        return 0
    with motor().begin() as c:
        return c.execute(aktarimlar.delete().where(aktarimlar.c.ozet == ozet)).rowcount


def ozet_metni(sonuc, en_cok=12):
    """Aktarım sonucunun okunur özeti (Telegram/konsol)."""
    if sonuc.get("atlandi"):
        return "📄 Bu UYAP listesi daha önce işlenmiş; değişiklik yok."
    satir = [f"📄 UYAP listesi işlendi: {sonuc['toplam']} dosya"]
    if sonuc["yeni"]:
        satir.append(f"➕ Yeni dosya ({len(sonuc['yeni'])}): " + ", ".join(sonuc["yeni"][:en_cok]) +
                     (" …" if len(sonuc["yeni"]) > en_cok else ""))
    if sonuc["durum_degisen"]:
        satir.append(f"🔄 Durumu değişen ({len(sonuc['durum_degisen'])}):")
        satir += [f"   • {d}: {e or '—'} → {y or '—'}" for d, e, y in sonuc["durum_degisen"][:en_cok]]
        if len(sonuc["durum_degisen"]) > en_cok:
            satir.append("   …")
    if sonuc["listeden_cikan"]:
        satir.append(f"➖ Listede artık görünmeyen ({len(sonuc['listeden_cikan'])}): " +
                     ", ".join(sonuc["listeden_cikan"][:en_cok]))
    if len(satir) == 1:
        satir.append("Değişiklik yok.")
    return "\n".join(satir)


# ---------------------------------------------------------------- sorgular
def dosya_bul(esas, birim=""):
    """Esas no (+ varsa birim) ile dosya kaydı ve tarafları. Birden çok varsa birim benzerliğine göre seçer."""
    e = motor()
    with e.connect() as c:
        adaylar = c.execute(select(dosyalar).where(dosyalar.c.esas == str(esas).strip())).all()
        if not adaylar:
            return None
        sec = adaylar[0]
        if len(adaylar) > 1 and birim:
            b = norm(birim)
            for a in adaylar:
                na = norm(a.birim)
                if na == b or na in b or b in na:
                    sec = a
                    break
        tr = c.execute(select(taraflar).where(taraflar.c.dosya_id == sec.id).order_by(taraflar.c.sira)).all()
        d = dict(sec._mapping)
        d["taraflar"] = [dict(t._mapping) for t in tr]
        return d


def kapali_mi(durum):
    return bool(durum) and str(durum).startswith("Kapalı")


def ad_ara(ad):
    """Bir kişinin/kurumun geçtiği TÜM dosyalar ve rolü (çıkar çatışması kontrolü için)."""
    n = norm(ad)
    if len(n) < 3:
        return []
    e = motor()
    with e.connect() as c:
        rows = c.execute(
            select(dosyalar.c.birim, dosyalar.c.esas, dosyalar.c.durum, dosyalar.c.muvekkil, taraflar.c.rol,
                   taraflar.c.ad, taraflar.c.muvekkil_mi)
            .join(taraflar, taraflar.c.dosya_id == dosyalar.c.id)
            .where(taraflar.c.ad_norm.like(f"%{n}%"))
            .order_by(dosyalar.c.esas)).all()
    return [dict(r._mapping) for r in rows]


# Rolün davadaki yönü: "A" (talep eden / zarar gören taraf) ya da "B" (aleyhine olan taraf). Karma ya da
# tarafsız roller (Müşteki Sanık, Katılan Sanık, Veli, Mirasçı, Üçüncü Şahıs...) çatışma hesabına katılmaz.
_YON_A = ("davacı", "alacaklı", "müşteki", "katılan", "mağdur", "suçtan zarar gören", "talep eden", "başvurucu",
          "itiraz eden (davacı)", "ihbar eden", "şikayetçi", "tedbir talep eden", "temyiz eden", "istinaf eden")
_YON_B = ("davalı", "borçlu", "sanık", "şüpheli", "suça sürüklenen çocuk", "karşı taraf", "dahili davalı",
          "aleyhine tedbir talep edilen", "aleyhine", "hakkında")


def taraf_yonu(rol):
    # Not: "İ".lower() Python'da noktalı bileşik harf üretir; karşılaştırma norm() ile (ASCII büyük harf) yapılır.
    r = norm(rol)
    if not r or ("SANIK" in r and any(k in r for k in ("MUSTEKI", "KATILAN"))):
        return None
    if r.endswith(" DAVALI"):      # "İtiraz Eden (Davalı)", "Müdahil(Davalı)" (parantez norm()'da boşluk olur)
        return "B"
    if r.endswith(" DAVACI"):
        return "A"
    for k in _YON_B:
        if r.startswith(norm(k)):
            return "B"
    for k in _YON_A:
        if r.startswith(norm(k)):
            return "A"
    if "KARSI TARAF" in r:
        return "B"
    return None


def catismalar():
    """OLASI ÇIKAR ÇATIŞMASI: aynı dosyada iki (ya da daha çok) müvekkilimiz KARŞI KARŞIYA taraflarda
    (Davacı ↔ Davalı, Alacaklı ↔ Borçlu, Katılan/Müşteki/Mağdur ↔ Sanık...). Bir kişi bir dosyada müvekkilimizken
    başka bir dosyada başka müvekkilimizin karşısındaysa da bu kurala girer.
    Döner: [{"dosya", "durum", "a_taraf": [ad (rol)], "b_taraf": [ad (rol)]}]"""
    e = motor()
    with e.connect() as c:
        rows = c.execute(select(dosyalar.c.id, dosyalar.c.birim, dosyalar.c.esas, dosyalar.c.durum, taraflar.c.ad,
                                taraflar.c.rol)
                         .join(taraflar, taraflar.c.dosya_id == dosyalar.c.id)
                         .where(taraflar.c.muvekkil_mi.is_(True))).all()
    gruplar = {}
    for r in rows:
        g = gruplar.setdefault(r.id, {"dosya": f"{r.birim} {r.esas}", "durum": r.durum, "A": [], "B": []})
        y = taraf_yonu(r.rol)
        if y:
            g[y].append(f"{r.ad} ({r.rol})")
    return [{"dosya": g["dosya"], "durum": g["durum"], "a_taraf": g["A"], "b_taraf": g["B"]}
            for g in gruplar.values() if g["A"] and g["B"]]


def uyari_yeni_mi(anahtar, metin=""):
    """Bu uyarı daha önce gönderilmediyse kaydeder ve True döner (aynı uyarı tekrar gönderilmez)."""
    e = motor()
    with e.begin() as c:
        if c.execute(select(uyarilar.c.id).where(uyarilar.c.anahtar == anahtar[:190])).first():
            return False
        c.execute(insert(uyarilar).values(anahtar=anahtar[:190], metin=metin, tarih=datetime.now().replace(microsecond=0)))
        return True


# ---------------------------------------------------------------- tebligat / duruşma kayıtları
def tebligat_kaydet(item, ticktick_id=None):
    """İşlenen tebligatı deftere yazar/günceller (ileride görev ve dilekçe üretimi için geçmiş)."""
    barkod = (item.get("barcode") or "").strip()
    uets_no = (item.get("uets_no") or "").strip()
    an = barkod or (f"UETS:{uets_no}" if uets_no else "")
    if not an:
        return
    dl = item.get("deadlines") or {}
    gelis = dl.get("gelis_dt")
    if gelis is not None and getattr(gelis, "tzinfo", None) is not None:
        gelis = gelis.replace(tzinfo=None)
    alanlar = {"barkod": barkod or None, "uets_no": uets_no or None, "birim": item.get("court"),
               "esas": item.get("esas_no") or None, "konu": item.get("konu_raw"), "gelis": gelis,
               "son_gun": dl.get("target_str") or dl.get("d14_str"), "eyp_yolu": item.get("eyp_path")}
    if ticktick_id and not str(ticktick_id).startswith("pending"):
        alanlar["ticktick_id"] = ticktick_id
    e = motor()
    with e.begin() as c:
        var = c.execute(select(tebligatlar.c.id).where(tebligatlar.c.anahtar == an[:190])).first()
        if var:
            c.execute(update(tebligatlar).where(tebligatlar.c.id == var.id).values(**{k: v for k, v in alanlar.items() if v}))
        else:
            c.execute(insert(tebligatlar).values(anahtar=an[:190], kayit=datetime.now().replace(microsecond=0), **alanlar))


def durusma_kaydet(uid, birim, esas, baslangic, baslik="", yer="", ticktick_id=None, iptal=False):
    e = motor()
    if baslangic is not None and getattr(baslangic, "tzinfo", None) is not None:
        baslangic = baslangic.replace(tzinfo=None)
    alanlar = {"birim": birim, "esas": esas, "baslangic": baslangic, "baslik": baslik, "yer": yer,
               "guncelleme": datetime.now().replace(microsecond=0), "iptal": iptal}
    if ticktick_id:
        alanlar["ticktick_id"] = ticktick_id
    with e.begin() as c:
        var = c.execute(select(durusmalar).where(durusmalar.c.takvim_uid == uid[:190])).first()
        if var:
            c.execute(update(durusmalar).where(durusmalar.c.id == var.id).values(**alanlar))
            return dict(var._mapping)
        c.execute(insert(durusmalar).values(takvim_uid=uid[:190], **alanlar))
        return None


def durusma_getir(uid):
    with motor().connect() as c:
        r = c.execute(select(durusmalar).where(durusmalar.c.takvim_uid == uid[:190])).first()
        return dict(r._mapping) if r else None


def istatistik():
    e = motor()
    with e.connect() as c:
        d = {"dosya": c.execute(select(func.count()).select_from(dosyalar)).scalar(),
             "listede": c.execute(select(func.count()).select_from(dosyalar).where(dosyalar.c.listede.is_(True))).scalar(),
             "taraf": c.execute(select(func.count()).select_from(taraflar)).scalar(),
             "muvekkilli_dosya": c.execute(select(func.count()).select_from(dosyalar).where(dosyalar.c.muvekkil.isnot(None))).scalar(),
             "tebligat": c.execute(select(func.count()).select_from(tebligatlar)).scalar(),
             "durusma": c.execute(select(func.count()).select_from(durusmalar)).scalar(),
             "aktarim": c.execute(select(func.count()).select_from(aktarimlar)).scalar()}
        d["durumlar"] = [(r[0] or "—", r[1]) for r in c.execute(
            select(dosyalar.c.durum, func.count()).where(dosyalar.c.listede.is_(True))
            .group_by(dosyalar.c.durum).order_by(func.count().desc())).all()]
    return d


def tasi(hedef_url):
    """Bütün defteri başka bir veritabanına (ör. Plesk MySQL) kopyalar. Hedefteki tablolar boş olmalı."""
    kaynak = motor()
    hedef = motor(hedef_url)
    sayilar = {}
    try:
        with kaynak.connect() as k, hedef.begin() as h:
            for tablo in meta.sorted_tables:
                if h.execute(select(func.count()).select_from(tablo)).scalar():
                    raise RuntimeError(f"Hedefte '{tablo.name}' tablosu boş değil; taşıma durduruldu (veri ezilmesin).")
                satirlar = [dict(r._mapping) for r in k.execute(select(tablo)).all()]
                if satirlar:
                    h.execute(insert(tablo), satirlar)
                sayilar[tablo.name] = len(satirlar)
    finally:
        hedef.dispose()
    return sayilar
