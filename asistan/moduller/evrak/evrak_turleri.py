#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır. / All rights reserved.
"""
UYAP evrak türü sınıflandırması.

Kurallar, gerçek bir UYAP kataloğundaki ~600 asıl evrak türü ve ~5.000 ek adı incelenerek
yazıldı (Kapalı Tebligat, Hazırlık Dosyası Gelen Evrak, Boş Genel Müzekkere Şablonu,
Reddiyat Makbuzu, Tutuklamanın Gözden Geçirilmesi Kararı, ...). Sıra önemlidir: ilk eşleşen
kategori kazanır (ör. "Tutukluluğa İtirazın Değerlendirilmesi Kararı" Karar değil Tutuklama,
"Bilirkişi Teslim Tutanağı" Tebligat değil Bilirkişi, "Talimat Duruşma Zaptı" Talimat değil Duruşma).

Hem evrak kataloğu (evrak_katalog.py) hem de CLI evrak türü filtresi (uyap_indirici.py) kullanır.
"""

from __future__ import annotations

import re
from functools import lru_cache

_FOLD = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c", "Â": "a", "â": "a",
    "Î": "i", "î": "i", "Û": "u", "û": "u",
})


def fold(text) -> str:
    """Türkçe harf ve büyük/küçük farkını yok sayan biçim: 'Tebliğ Mazbatası' -> 'teblig mazbatasi'."""
    if not text:
        return ""
    s = str(text).translate(_FOLD).lower().replace("_", " ")
    return re.sub(r"\s+", " ", s).strip()


# (kod, görünen ad, klasör adı, içermesi gereken kelimeler, içermemesi gereken kelimeler)
KATEGORI_KURALLARI: list[tuple[str, str, str, tuple, tuple]] = [
    ("kesinlesme", "Kesinleşme Şerhi", "KESINLESME",
     ("kesinlesme", "kesinlestirme", "kesinlesmis karar"), ()),
    ("durusma", "Duruşma / Ön İnceleme Zaptı", "DURUSMA_TUTANAKLARI",
     ("durusma zapt", "durusma tutanag", "celse zapt", "segbis", "on inceleme zapt", "son tutanak"),
     ("talep", "celb", "celp", "dilekce", "vazgecme", "mazeret", "davetiye")),
    ("tensip", "Tensip Zaptı", "TENSIP_ZAPITLARI", ("tensip",), ("itiraz",)),
    ("tutuklama", "Tutuklama / Adli Kontrol / Yakalama", "TUTUKLAMA_ADLI_KONTROL",
     ("tutuk", "adli kontrol", "yakalama", "tahliye", "zorla getirme", "yurt disi yasak",
      "yurt disi cikis", "denetimli serbestlik", "ulasim guclugu nedeniyle denetim", "denetim takip",
      "ihzar", "celbi", "celp", "arama el koyma", "arama ve el koyma", "el koyma", "gozden gecirme",
      "muhafaza karari", "muhafaza talebi", "c.i.k"), ("tahliye ve teslim",)),
    ("iddianame", "İddianame / Fezleke", "IDDIANAMELER", ("iddianame", "fezleke"), ()),
    ("bilirkisi", "Bilirkişi / Adli Tıp / Uzman Raporu", "BILIRKISI_RAPORLARI",
     ("bilirkisi", "adli tip", "kriminal", "uzman gorus", "uyusturucu inceleme", "adli rapor",
      "doktor rapor", "saglik kurulu", "olu muayene", "otopsi", "adli muayene", "cocuk izlem",
      "kesin rapor", "kesif ve bilirkisi", "uzlastirici rapor", "uzmanlik rapor"), ()),
    ("karar", "Karar / Hüküm / İlam", "KARARLAR",
     ("gerekceli karar", "ilam", "hukum ozeti", "ara karar", "ek karar", "tefrik karar",
      "birlestirme karar", "takipsizlik", "kyok", "yetkisizlik karar", "gorevsizlik karar",
      "yd karar", "yd itiraz karar", "danistay karar", "yargitay karar", "bolge idare mahkemesi karar",
      "degisik is karar", "karar evraki", "degerlendirme karar", "degerlendirilmesi karar",
      "kamu gorevlileri karar", "nihai karar", "kisa karar", "hukum", "tehiri icra karar",
      "tehir-i icra karar", "ihtiyati tedbir karar", "ihtiyati haciz karar", "yetkili savcilik tespiti karar",
      "uzlastirma burosuna gonderme karar", "hakimin cekilmesinin incelenmesi karar", "sabika silme karar",
      "yetkisizlik", "takipsizlig", "tashih"),
     ("dilekce", "talebi", "teblig", "sarf karar", "itiraz dilek", "gonderilmesi istemi")),
    ("tebligat", "Tebligat / Mazbata", "TEBLIGATLAR",
     ("teblig", "tebligat", "mazbata", "uets", "e-teblig", "posta alindi", "ptt", "cek-senet teslim"),
     ()),
    ("ifade", "İfade / Sorgu / Tutanak / Keşif", "IFADE_TUTANAK_KESIF",
     ("ifade", "sorgu tutanag", "sorgu zapt", "tutanak", "tutanag", "teshis", "olay yeri", "kesif", "zabit varaka"),
     ("tebligat", "teslim tesellum")),
    ("vekalet", "Vekaletname / Yetki Belgesi", "VEKALETNAME",
     ("vekaletname", "yetki belgesi", "vekalet pulu", "vekillik", "vekil bilgisi", "tevkil", "czm vekaletname"),
     ()),
    ("icra", "İcra / Haciz / Satış", "ICRA_HACIZ",
     ("haciz", "odeme emri", "icra emri", "takip talebi", "takibin", "takip dayanag", "satis",
      "kiymet takdir", "89/", "ihale", "sira cetveli", "takyidat", "mahrumiyet", "serh ekleme",
      "serh kaldirma", "temlik", "teminat", "yenileme emri", "icra dairesi", "icra daireleri",
      "haricen tahsil", "dosya alacag", "alacagina", "artirma sonuc", "ilan aski", "sahiplik",
      "dosya hesab", "ilani"),
     ()),
    ("mali", "Makbuz / Harç / Masraf / Reddiyat", "MAKBUZ_HARC_MASRAF",
     ("makbuz", "reddiyat", "harc", "masraf", "tahsilat", "dekont", "sayman", "vezne", "ceza fisi",
      "sarf karar", "fatura", "para isteme", "odeme yapilmasi", "iban", "mehil", "tahsil", "alindisi",
      "alindi belgesi", "posta cek"), ()),
    ("talimat", "Talimat Yazışmaları", "TALIMATLAR", ("talimat",), ()),
    ("muzekkere", "Müzekkere / Kurum Cevabı / Sorgu", "MUZEKKERE_KURUM_CEVAPLARI",
     ("muzekkere", "cevap yazi", "cevap yazilari", "kurum", "banka", "sgk", "ssk", "nufus", "adli sicil",
      "sabika", "gsm", "imei", "btk", "tib ", "iletisimin tes", "adres arastirma", "adres sorus",
      "sorgulamasi", "sorgulari", "web-servis", "mal varligi", "maas bilgisi", "tapu", "takbis", "egm",
      "emniyet", "jandarma", "kolluk", "asayis", "konsolosluk", "ticaret sicil", "belediye", "genel uyari",
      "bilgi evrak", "bilgisi evrak", "bilgisi raporu", "hizmet dokumu", "mernis", "imar durumu",
      "yazilan yazi", "bilgi yazisi", "abonelik", "dosyalari raporu"), ()),
    ("dilekce", "Dilekçe / Talep / Beyan", "DILEKCE_TALEP_BEYAN",
     ("dilekce", "layiha", "beyan", "talep", "talebi", "istegi", "itiraz", "mutalaa", "mazeret", "sikayet", "feragat",
      "islah", "dava acilis", "basvuru", "savunma", "e-durusma", "lahika", "istemi", "muvafakat",
      "dava dilekce", "karsi dava", "ihbar", "katilma", "yonlendirme", "kanun yararina", "iadei muhakeme",
      "yargilamanin yenilenmesi", "reddi hakim", "hakimin reddi", "eski hale getirme", "suret", "dava degeri",
      "kdv beyannamesi", "ihtarname", "kira sozlesmesi", "anayasaya aykirilik", "anayasa'ya aykirilik"),
     ()),
    ("form", "Form / Fiş / Cetvel", "FORM_FIS",
     ("form", "cetvel", "fisi", "fis ", "dizi pusulasi", "kontrol formu"), ()),
    ("yazisma", "Üst Yazı / Gelen-Giden Evrak", "YAZISMA_GELEN_GIDEN",
     ("ust yazi", "ustyazi", "ust muz", "gelen evrak", "giden", "gonderme", "gonderilmesi", "dosya isteme",
      "dosyanin", "dosyasinin", "dosya gonder", "tekit", "tekid", "derkenar", "goruldu", "muhabere",
      "e-posta", "eyazisma", "eyp", "kep gonderisi", "yazisi", "yazi", "iade", "ozel evrak", "taranmis",
      "evrak", "sablon", "teslim tesellum", "onerisi", "genel karar/muzekkere", "muhtira", "tercume", "istenmesi", "eksiklik"), ()),
]

KATEGORILER = [(k, ad) for k, ad, *_ in KATEGORI_KURALLARI]
KATEGORI_ADI = {k: ad for k, ad in KATEGORILER}
KATEGORI_ADI["diger"] = "Diğer"
KLASOR_ADI = {k: kl for k, _ad, kl, *_ in KATEGORI_KURALLARI}
KLASOR_ADI["diger"] = "DIGER_EVRAKLAR"

# Eski kod adları (uyap_indirici CLI filtreleri) -> yeni kodlar
ESKI_KOD = {"layihalar": "dilekce", "dilekceler": "dilekce", "tebligatlar": "tebligat", "mazbata": "tebligat",
            "muzekkereler": "muzekkere", "kurum_cevaplari": "muzekkere"}

_DOSYA_ADI_RX = re.compile(r"(\.[a-z0-9]{2,4}$)|(^[\d_#\-\s.()]+$)|(^ek[\s\-_]*\d+)", re.I)


@lru_cache(maxsize=50000)
def kategori_of(tur: str) -> str:
    """Bir evrak/ek türü adının kategori kodu ('diger' = eşleşme yok)."""
    t = fold(tur)
    if not t:
        return "diger"
    if t in ("karar", "kararlar"):
        return "karar"
    for kod, _ad, _kl, inc, exc in KATEGORI_KURALLARI:
        if any(k in t for k in inc) and not any(k in t for k in exc):
            return kod
    return "diger"


@lru_cache(maxsize=200000)
def ek_kategori_of(ek_adi: str, ust_tur: str) -> str:
    """Ek için kategori: ek adı anlamlıysa kendi kategorisi, dosya adı / 'Diğer Evrak' gibi
    anlamsızsa ait olduğu asıl evrakın kategorisi."""
    k = kategori_of(ek_adi)
    if k in ("diger", "yazisma") or _DOSYA_ADI_RX.search(fold(ek_adi) or ""):
        u = kategori_of(ust_tur)
        if u != "diger":
            return u
    return k


def tur_eslesir(tur: str, filtre: str) -> bool:
    """CLI için: filtre bir kategori kodu ise kategoriye, değilse ad içinde aramaya göre eşleştirir."""
    f = ESKI_KOD.get(fold(filtre), fold(filtre))
    if f in ("tumu", "all", "*", ""):
        return True
    if f in KATEGORI_ADI:
        return kategori_of(tur) == f
    return f in fold(tur)
