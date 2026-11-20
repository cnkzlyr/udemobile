# -*- coding: utf-8 -*-
"""
İCRA DOSYASI ANALİZİ — kesinleşme ve takipsizlik (işlemsizlik) uyarıları.

Kaynaklar (hepsi yerel katalogda; UYAP'a ek istek atılmaz):
  * icra_hesap.kesinlesme_durumu / borclular_json  (UYAP borçlu listesi)
  * dosya_safahat  (UYAP safahatı: ödeme/icra emri tebliği, itiraz, haciz, sorgu, kesinleşme işlemleri)
  * evrak          (tensip/karar/talep/müzekkere evrakı: "takibin kesinleştirilmesi talebinin kabulüne" vb.)
  * tebligat       (indirilen mazbatalardan: muhatap, tebliğ tarihi, sonuç)

Çıktı her dosya için:
  kesinlesme: {durum: kesin | kesinlestirilebilir | sure_isliyor | itiraz | teblig_bekleniyor | bilinmiyor,
               baslik, aciklama (somut: hangi tarihli emir kime ne zaman tebliğ edildi, süre ne zaman doldu)}
  takipsizlik: {son_islem_tarihi, son_islem, gun, seviye: kirmizi | turuncu | sari | yesil, aciklama}

Hukuki notlar (bilgi amaçlı; somut dosyada mutlaka kontrol edilmelidir):
  * İtiraz süreleri: genel haciz yoluyla ilamsız takip 7 gün (İİK m.62), kambiyo senetlerine dayalı takip 5 gün
    (İİK m.168/5), ilamlı takipte icra emri 7 gün (İİK m.33).
  * Elektronik tebligat, muhatabın adresine ulaştığı tarihi izleyen 5. günün sonunda yapılmış sayılır (TK m.7/a).
  * Uzun süre işlem yapılmayan icra dosyası işlemden kaldırılır; yenileme talebi ve harç gerekir. Haciz ve satış
    istem süreleri (İİK m.78, m.106-110) ayrıca takip edilmelidir.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3

_FOLD = str.maketrans({"İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g", "Ü": "u", "ü": "u",
                       "Ö": "o", "ö": "o", "Ç": "c", "ç": "c"})


def fold(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").translate(_FOLD).lower()).strip()


def _tarih(s) -> dt.date | None:
    s = str(s or "").strip()
    for desen, bic in ((r"(\d{4})-(\d{2})-(\d{2})", "ymd"), (r"(\d{2})[./](\d{2})[./](\d{4})", "dmy")):
        m = re.search(desen, s)
        if m:
            try:
                return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if bic == "ymd" else \
                    dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                return None
    return None


def _tr(d: dt.date | None) -> str:
    return d.strftime("%d.%m.%Y") if d else "—"


def _tablo(c, ad) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name=?", (ad,)).fetchone() is not None


def _olaylar(c, dkey: str, dosya_no: str, birim: str) -> list:
    """Evrak + safahat + tebligat kayıtlarını tek zaman çizelgesinde birleştirir: (tarih, kaynak, metin, ham)."""
    out = []
    for r in c.execute("SELECT tur, aciklama, tarih FROM evrak WHERE dkey=? AND COALESCE(is_ek,0)=0", (dkey,)):
        d = _tarih(r[2])
        if d:
            out.append((d, "evrak", f"{r[0] or ''} {r[1] or ''}".strip(), {}))
    if _tablo(c, "dosya_safahat"):
        for r in c.execute("SELECT safahat_tarihi_str, safahat_tarihi, safahat_turu, aciklama FROM dosya_safahat WHERE dkey=?", (dkey,)):
            d = _tarih(r[0]) or _tarih(r[1])
            if d:
                out.append((d, "safahat", f"{r[2] or ''} {r[3] or ''}".strip(), {}))
    if _tablo(c, "tebligat"):
        for r in c.execute("SELECT tebligat_turu, evrak_adi, muhatap, gonderim_tarihi, teblig_tarihi, sonuc FROM tebligat "
                           "WHERE dkey=? OR (dosya_no=? AND birim=?)", (dkey, dosya_no, birim)):
            d = _tarih(r[4]) or _tarih(r[3])
            if d:
                out.append((d, "tebligat", f"{r[0] or ''} {r[1] or ''}".strip(),
                            {"muhatap": r[2] or "", "teblig": _tarih(r[4]), "gonderim": _tarih(r[3]), "sonuc": r[5] or ""}))
    out.sort(key=lambda x: x[0])
    return out


def takip_turu(olaylar: list) -> tuple[str, int]:
    metin = " ".join(fold(o[2]) for o in olaylar)
    if "kambiyo" in metin or "ornek 10" in metin or "cek " in metin or "bono" in metin:
        return "Kambiyo senedine dayalı", 5
    if "icra emri" in metin or "ilamli" in metin or "ornek 4" in metin or "ornek 5" in metin:
        return "İlamlı", 7
    return "İlamsız (genel haciz)", 7


_ITIRAZ = re.compile(r"(borclu|borca|imzaya|takibe|odeme emrine)\s*(itiraz)|itiraz dilekce|itiraz edildi|takip durdu")
_ITIRAZ_SONU = re.compile(r"itiraz(in|ın)? (iptal|kaldir)")
_KESIN = re.compile(r"kesinles(ti|mis|mesine|tirilme|tirilmesi talebinin kabul)|takip kesinles")
_EMIR = re.compile(r"odeme emri|icra emri|tahliye emri")
_TALEP = re.compile(r"haciz|sorgu|muzekkere|talep|yakalama|satis|kiymet takdir|maas|sgk|tapu|arac|banka|89/1|89-1|ihbarname")


def analiz(c: sqlite3.Connection, dkey: str, bugun: dt.date | None = None) -> dict | None:
    bugun = bugun or dt.date.today()
    d = c.execute("SELECT dkey, birim, dosya_no, durum, acilis FROM dosya WHERE dkey=?", (dkey,)).fetchone()
    if not d:
        return None
    dkey, birim, dosya_no, durum, acilis = d[0], d[1] or "", d[2] or "", d[3] or "", d[4] or ""
    olaylar = _olaylar(c, dkey, dosya_no, birim)
    tur, sure = takip_turu(olaylar)
    uyap_kesin, borclular = "", []
    if _tablo(c, "icra_hesap"):
        r = c.execute("SELECT kesinlesme_durumu, borclular_json FROM icra_hesap WHERE dkey=?", (dkey,)).fetchone()
        if r:
            uyap_kesin = r[0] or ""
            try:
                borclular = [b.get("ad_soyad") or "" for b in json.loads(r[1] or "[]") if isinstance(b, dict)]
            except ValueError:
                borclular = []

    # ---- KESİNLEŞME
    kes = {"durum": "bilinmiyor", "baslik": "Kesinleşme bilgisi yok", "aciklama": "", "takip_turu": tur, "itiraz_suresi": sure}
    kesin_olay = next((o for o in reversed(olaylar) if _KESIN.search(fold(o[2]))), None)
    itiraz_olay = next((o for o in reversed(olaylar) if _ITIRAZ.search(fold(o[2])) and not _ITIRAZ_SONU.search(fold(o[2]))), None)
    emirler = [o for o in olaylar if _EMIR.search(fold(o[2]))]
    teblig = [o for o in olaylar if o[1] == "tebligat" and o[3].get("teblig") and
              (_EMIR.search(fold(o[2])) or not emirler)]
    if "kesinles" in fold(uyap_kesin) and "kesinlesmedi" not in fold(uyap_kesin):
        kes.update(durum="kesin", baslik="Takip kesinleşmiş (UYAP)", aciklama=f"UYAP borçlu bilgisi: {uyap_kesin}.")
    elif kesin_olay:
        kes.update(durum="kesin", baslik=f"Takip kesinleşmiş ({_tr(kesin_olay[0])})",
                   aciklama=f"{_tr(kesin_olay[0])} tarihli kayıt: \"{kesin_olay[2][:160]}\".")
    elif itiraz_olay and (not emirler or itiraz_olay[0] >= emirler[0][0]):
        kes.update(durum="itiraz", baslik=f"Borçlu itirazı ({_tr(itiraz_olay[0])}) — takip durmuş olabilir",
                   aciklama=f"{_tr(itiraz_olay[0])} tarihli kayıt: \"{itiraz_olay[2][:160]}\". İtirazın iptali/kaldırılması yoluna "
                            "gidilmediyse takip ilerlemez.")
    elif teblig:
        son = max(teblig, key=lambda o: o[3]["teblig"])
        t = son[3]["teblig"]
        bitis = t + dt.timedelta(days=sure)
        emir = emirler[-1] if emirler else None
        emir_m = f"{_tr(emir[0])} tarihli {emir[2][:60].strip()}" if emir else "Ödeme/icra emri"
        muh = son[3].get("muhatap") or (", ".join(b for b in borclular if b) or "borçlu")
        sonuc = f" ({son[3]['sonuc']})" if son[3].get("sonuc") else ""
        if bugun > bitis:
            kes.update(durum="kesinlestirilebilir", baslik="Kesinleştirme talep edilebilir",
                       aciklama=f"{emir_m} {muh} adına {_tr(t)} tarihinde tebliğ edilmiş{sonuc}. {tur.lower()} takipte {sure} günlük "
                                f"itiraz süresi {_tr(bitis)} tarihinde doldu ve dosyada itiraz kaydı yok → takibin kesinleştirilmesi "
                                "talep edilebilir.", son_gun=bitis.isoformat())
        else:
            kes.update(durum="sure_isliyor", baslik=f"İtiraz süresi işliyor (son gün {_tr(bitis)})",
                       aciklama=f"{emir_m} {muh} adına {_tr(t)} tarihinde tebliğ edildi{sonuc}; {sure} günlük süre {_tr(bitis)} "
                                f"günü doluyor ({(bitis - bugun).days} gün kaldı).", son_gun=bitis.isoformat())
    elif emirler:
        e = emirler[-1]
        kes.update(durum="teblig_bekleniyor", baslik="Emir gönderilmiş, tebliğ sonucu yok",
                   aciklama=f"{_tr(e[0])} tarihli \"{e[2][:80]}\" kaydı var; tebliğ mazbatası/sonucu katalogda görünmüyor. "
                            "Tebligat sonucunu sorgulayın (iade ise adres araştırması / Mernis 21-2).")

    # ---- TAKİPSİZLİK (işlemsizlik)
    talepler = [o for o in olaylar if _TALEP.search(fold(o[2]))]
    son = (talepler or olaylar or [None])[-1]
    tk = {"son_islem_tarihi": None, "son_islem": "", "gun": None, "seviye": "bilinmiyor", "aciklama": "Dosyada tarihli işlem kaydı yok."}
    if son:
        gun = (bugun - son[0]).days
        seviye = "kirmizi" if gun >= 365 else "turuncu" if gun >= 270 else "sari" if gun >= 180 else "yesil"
        acik = {
            "kirmizi": "1 yılı aştı: dosya işlemden kaldırılmış olabilir; yenileme talebi ve harç gerekebilir.",
            "turuncu": f"{365 - gun} gün içinde işlem yapılmazsa 1 yıl dolacak: haciz/sorgu talebi verin.",
            "sari": "6 aydır yeni talep yok: mal varlığı sorgusu / haciz talebi planlayın.",
            "yesil": "Dosya hareketli.",
        }[seviye]
        tk = {"son_islem_tarihi": son[0].isoformat(), "son_islem": son[2][:120], "gun": gun, "seviye": seviye,
              "aciklama": f"Son {'talep/işlem' if talepler else 'kayıt'}: {_tr(son[0])} · {son[2][:80]} — {gun} gün önce. {acik}"}
    if durum and durum != "Açık":
        tk["seviye"] = "kapali"
        tk["aciklama"] = "Dosya kapalı."
    return {"dkey": dkey, "birim": birim, "dosya_no": dosya_no, "durum": durum, "acilis": acilis, "borclular": borclular,
            "kesinlesme": kes, "takipsizlik": tk, "olay_sayisi": len(olaylar),
            "zaman_cizelgesi": [{"tarih": o[0].isoformat(), "kaynak": o[1], "metin": o[2][:200]} for o in olaylar[-60:]]}


def tum_icra(c: sqlite3.Connection, bugun: dt.date | None = None) -> dict:
    """Tüm açık icra dosyaları: kesinleşme ve takipsizlik özetleri, en acil olan üstte."""
    rows = c.execute("SELECT dkey, birim, dosya_tur FROM dosya WHERE (birim LIKE '%İcra Dairesi%' OR birim LIKE '%icra dairesi%' "
                     "OR birim LIKE '%İcra Müdürlüğü%' OR dosya_tur LIKE '%İcra%') AND COALESCE(durum,'Açık')='Açık'").fetchall()
    sonuc = []
    for r in rows:
        if "mahkeme" in fold(r[1]):
            continue
        a = analiz(c, r[0], bugun)
        if a:
            a.pop("zaman_cizelgesi", None)
            sonuc.append(a)
    sira = {"kirmizi": 0, "turuncu": 1, "sari": 2, "bilinmiyor": 3, "yesil": 4, "kapali": 5}
    ks = {"kesinlestirilebilir": 0, "sure_isliyor": 1, "teblig_bekleniyor": 2, "itiraz": 3, "bilinmiyor": 4, "kesin": 5}
    sonuc.sort(key=lambda a: (0 if a["kesinlesme"]["durum"] == "kesinlestirilebilir" else 1,
                              sira.get(a["takipsizlik"]["seviye"], 9), ks.get(a["kesinlesme"]["durum"], 9),
                              -(a["takipsizlik"]["gun"] or 0)))
    ozet = {"toplam": len(sonuc),
            "kesinlestirilebilir": sum(1 for a in sonuc if a["kesinlesme"]["durum"] == "kesinlestirilebilir"),
            "kesin": sum(1 for a in sonuc if a["kesinlesme"]["durum"] == "kesin"),
            "itiraz": sum(1 for a in sonuc if a["kesinlesme"]["durum"] == "itiraz"),
            "sure_isliyor": sum(1 for a in sonuc if a["kesinlesme"]["durum"] == "sure_isliyor"),
            "kirmizi": sum(1 for a in sonuc if a["takipsizlik"]["seviye"] == "kirmizi"),
            "turuncu": sum(1 for a in sonuc if a["takipsizlik"]["seviye"] == "turuncu"),
            "sari": sum(1 for a in sonuc if a["takipsizlik"]["seviye"] == "sari")}
    return {"ozet": ozet, "dosyalar": sonuc}
