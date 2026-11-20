#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GÖREV STANDARTLARI: her görev türünün (TEBLİGAT, DURUŞMA, DOSYA kartı) aynı öğeleri taşıması.

Her türün ZORUNLU öğeleri burada tek yerde tanımlıdır; ticktick_sync görevi bu biçimde açar, ticktick_duzen
var olan görevleri bu listeye göre denetler ve eksik görevleri "⚠️ EKSİK" satırı + 'eksik' etiketiyle işaretler
(tamamlandığında satır ve etiket kendiliğinden kalkar).

  TEBLİGAT : kimlik (mahkeme, esas, barkod) · Merci · Dosya · Barkod · Geliş · Tebliğ sayılma · Uygulanan yasal süre
             · son gün (dueDate) · ÜSTYAZI VE EKLER (EYP dosyaları görevde ya da 📎 alt görevinde)
  DURUŞMA  : kimlik (mahkeme, esas, duruşma) · Merci · Dosya · Duruşma tarihi · saat (dueDate)
  DOSYA    : kimlik (mahkeme, esas) · Merci · Dosya · 📌 Dosya konusu (Notion'dan) · Notion bağlantısı (varsa)

Sistem blokları işaretlerle sınırlanır; kullanıcının görev notuna yazdıkları ASLA silinmez.
"""
import re

import kimlik

EKSIK_ONEK = "⚠️ EKSİK:"
EKSIK_ETIKET = "eksik"
KONU_BAS = "📌 **Dosya konusu**"
KONU_SON = "〰️ konu sonu"


def _temiz(metin):
    return re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>~])", r"\1", metin or "")


def _var(content, *desenler):
    t = _temiz(content)
    return any(re.search(d, t, re.I) for d in desenler)


def tur_bul(task):
    """Görevin türü: kimlik satırından; yoksa başlık/etiketten. DOSYA, TEBLİGAT, DURUŞMA, EK ya da ''."""
    k = kimlik.oku((task or {}).get("content") or "")
    if k.get("tur"):
        return k["tur"]
    baslik = ((task or {}).get("title") or "").upper()
    etiket = (task or {}).get("tags") or []
    if "TEBLİGAT" in baslik or "📨" in baslik or "uets" in etiket:
        return "TEBLİGAT"
    if "DURUŞMA" in baslik or "⚖️" in baslik:
        return "DURUŞMA"
    if re.search(r" - \d{4}/\d+ Esas\s*$", (task or {}).get("title") or ""):
        return "DOSYA"
    return ""


def eksikler(task, ek_var=None):
    """Görevin standarda göre eksik öğeleri (liste). ek_var: tebligatta EYP ekinin gerçekten olup olmadığı."""
    c = (task or {}).get("content") or ""
    k = kimlik.oku(c)
    tur = tur_bul(task)
    eksik = []
    if not k:
        eksik.append("kimlik satırı")
    if tur in ("TEBLİGAT", "DURUŞMA", "DOSYA"):
        if not (k.get("mahkeme") or _var(c, r"Merci:")):
            eksik.append("mahkeme")
        if not (k.get("esas") or _var(c, r"Dosya:\**\s*\d{4}/\d+")):
            eksik.append("esas no")
    if tur == "TEBLİGAT":
        if not (k.get("barkod") or k.get("uets_no") or _var(c, r"Barkod:")):
            eksik.append("barkod")
        if not _var(c, r"Geliş:"):
            eksik.append("geliş tarihi")
        if not _var(c, r"Tebliğ Sayılma"):
            eksik.append("tebliğ tarihi")
        if not (_var(c, r"UYGULANAN YASAL SÜRE") and (task or {}).get("dueDate")):
            eksik.append("yasal süre / son gün")
        if ek_var is False or _var(c, r"EYP ekleri henüz indirilmedi"):
            eksik.append("üstyazı ve ekler")
    elif tur == "DURUŞMA":
        if not (k.get("durusma") or _var(c, r"Duruşma Tarihi:")):
            eksik.append("duruşma tarihi")
        if not (task or {}).get("dueDate"):
            eksik.append("takvim tarihi")
    elif tur == "DOSYA":
        if KONU_BAS not in _temiz(c):
            eksik.append("dosya konusu")
    return eksik


def eksik_isaretle(content, tags, eksik):
    """EKSİK satırını (kimlik satırının hemen altına) yazar / kaldırır; 'eksik' etiketini ekler / kaldırır.
    Döner: (yeni_content, yeni_tags, degisti_mi)."""
    satirlar = (content or "").splitlines()
    kalan = [s for s in satirlar if not _temiz(s).strip().startswith(EKSIK_ONEK)]
    if eksik:
        yeni = f"{EKSIK_ONEK} {', '.join(eksik)} (otomatik denetim; tamamlanınca bu satır kalkar)"
        konum = 1 if kalan and _temiz(kalan[0]).strip().startswith(kimlik.ONEK) else 0
        kalan.insert(konum, yeni)
    yeni_c = "\n".join(kalan)
    t = [x for x in (tags or []) if x != EKSIK_ETIKET] + ([EKSIK_ETIKET] if eksik else [])
    return yeni_c, t, (yeni_c.strip() != (content or "").strip() or sorted(t) != sorted(tags or []))


def konu_blogu(content, konu, kaynak="Notion"):
    """'📌 Dosya konusu' bloğunu yazar/yeniler (kimlik ve EKSİK satırlarının altına). Kullanıcı notları korunur."""
    t = content or ""
    temiz = _temiz(t)
    if KONU_BAS in temiz and KONU_SON in temiz:
        bas = temiz.index(KONU_BAS)
        son = temiz.index(KONU_SON, bas) + len(KONU_SON)
        t = (temiz[:bas].rstrip("\n") + "\n" + temiz[son:].lstrip("\n")).strip("\n")
    if not (konu or "").strip():
        return t
    blok = f"{KONU_BAS} ({kaynak})\n{konu.strip()}\n{KONU_SON}"
    satirlar = t.splitlines()
    i = 0
    while i < len(satirlar) and (_temiz(satirlar[i]).strip().startswith(kimlik.ONEK) or
                                 _temiz(satirlar[i]).strip().startswith(EKSIK_ONEK) or not satirlar[i].strip()):
        i += 1
    ust, alt = satirlar[:i], satirlar[i:]
    while ust and not ust[-1].strip():
        ust.pop()
    return "\n".join(ust + ["", blok, ""] + alt).strip("\n")


def konu_oku(content):
    temiz = _temiz(content)
    if KONU_BAS in temiz and KONU_SON in temiz:
        bas = temiz.index(KONU_BAS)
        govde = temiz[bas:temiz.index(KONU_SON, bas)].splitlines()[1:]
        return "\n".join(govde).strip()
    return ""


def dosya_karti_icerigi(court, esas_no, raw_tag="", notion_url="", konu="", konu_kaynak="Notion", baslik_konu=""):
    """Standart DOSYA kartı notu (yeni açılan kartlar)."""
    c = kimlik.satir("DOSYA", mahkeme=court, esas=esas_no, konu=baslik_konu) + "\n\n⚖️ **Dava Dosyası**\n"
    if court:
        c += f"- **Merci:** {court}\n"
    if esas_no:
        c += f"- **Dosya:** {esas_no} Esas\n"
    if raw_tag:
        c += f"👤 **Müvekkil:** #{raw_tag}\n"
    if notion_url:
        c += f"🔗 **Notion Dosyası:** {notion_url}\n"
    return konu_blogu(c, konu, konu_kaynak) if konu else c
