#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GÖREV KİMLİĞİ: TickTick görevinin "hangi tebligat / duruşma / dava dosyası" olduğunu BAŞLIKTAN BAĞIMSIZ
olarak taşıyan satır. Görev notunun (content) en üstünde durur:

    🔖 KİMLİK · TEBLİGAT · Mahkeme: Oltu 3. Asliye Hukuk Mahkemesi · Esas: 2026/24 · Barkod: 5003283066058

Neden: Kullanıcı görev başlığını istediği gibi değiştirir ("Cevap dilekçesi yazılacak", "... Yapılacak" vb.).
Eşleştirme, mükerrer temizliği ve denetim eskiden başlıktan mahkeme/esas okuyordu: yeniden adlandırılan görev
tanınmıyor, aynı tebligat için ikinci görev açılıyor ya da birleştirmede kullanıcının başlığı kayboluyordu.
Artık hepsi bu satırı okur; başlığa hiç dokunulmaz. Satırı silmeyin (silinirse denetim yeniden ekler).

TickTick notlarda bazı işaretleri ters bölüyle kaçırır (\\( \\) \\- ...): okurken temizlenir. Ayraç olarak
kaçırılmayan " · " kullanılır.
"""

import re

ONEK = "🔖 KİMLİK"
AYRAC = " · "
TURLER = ("TEBLİGAT", "DURUŞMA", "DOSYA", "EK")  # EK: tebligatın EYP dosyalarını taşıyan alt görev
_ALANLAR = ("Mahkeme", "Esas", "Barkod", "UETS No", "Duruşma", "Gönderen", "Konu")


def satir(tur, mahkeme="", esas="", barkod="", uets_no="", durusma="", gonderen="", konu=""):
    """Kimlik satırını üretir. Boş alanlar yazılmaz."""
    tur = (tur or "").upper()
    parcalar = [ONEK, tur]
    for ad, deger in (("Mahkeme", mahkeme), ("Esas", esas), ("Barkod", barkod), ("UETS No", uets_no),
                      ("Duruşma", durusma), ("Gönderen", gonderen), ("Konu", konu)):
        deger = re.sub(r"\s+", " ", str(deger or "")).replace("·", "-").strip()
        if deger:
            parcalar.append(f"{ad}: {deger[:160]}")
    return AYRAC.join(parcalar)


def _temiz(metin):
    return re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>~])", r"\1", metin or "")


def oku(content):
    """Notun içindeki kimlik satırını sözlüğe çevirir: {"tur", "mahkeme", "esas", "barkod", "uets_no", ...}.
    Satır yoksa {} döner."""
    for ham in _temiz(content).splitlines():
        s = ham.strip()
        if not s.startswith(ONEK):
            continue
        parcalar = [p.strip() for p in s.split("·")]
        d = {"tur": parcalar[1].upper() if len(parcalar) > 1 else ""}
        for p in parcalar[2:]:
            if ":" in p:
                ad, deger = p.split(":", 1)
                anahtar = {"Mahkeme": "mahkeme", "Esas": "esas", "Barkod": "barkod", "UETS No": "uets_no",
                           "Duruşma": "durusma", "Gönderen": "gonderen", "Konu": "konu"}.get(ad.strip())
                if anahtar:
                    d[anahtar] = deger.strip()
        return d
    return {}


def ekle(content, kimlik_satiri):
    """Kimlik satırını notun EN ÜSTÜNE koyar; varsa yenisiyle değiştirir. Kullanıcının notlarına dokunmaz."""
    satirlar = (content or "").splitlines()
    kalan = [s for s in satirlar if not _temiz(s).strip().startswith(ONEK)]
    while kalan and not kalan[0].strip():
        kalan.pop(0)
    return kimlik_satiri + ("\n\n" + "\n".join(kalan) if kalan else "")


def var_mi(content):
    return bool(oku(content))


# Başlığın sistemin kendi standart biçiminde olup olmadığı (değilse kullanıcı değiştirmiştir)
_STANDART_BASLIK = re.compile(r"^\s*(📨\s*|#)?\s*TEBLİGAT\b|^\s*(⚖️\s*|#)?\s*DURUŞMA\b|^.+ - \d{4}/\d+ Esas\s*$", re.I)


def kullanici_basligi_mi(baslik):
    """Başlık sistemin ürettiği standart biçimden farklıysa True (kullanıcı yeniden adlandırmış)."""
    return bool((baslik or "").strip()) and not _STANDART_BASLIK.search(baslik or "")
