# -*- coding: utf-8 -*-
"""
DOSYA KONUSU / ÖZETİ: her UYAP dosyası için 5-10 cümlelik konu özeti.

İki yol:
  1. Yapay zekâ anahtarı girildiyse (Entegrasyonlar > "Özet için yapay zekâ anahtarı": OZET_API_KEY,
     OZET_SAGLAYICI = anthropic | openai, isteğe bağlı OZET_MODEL) evrak metinlerinden gerçek bir özet yazdırılır.
  2. Anahtar yoksa (ya da yapay zekâ ulaşılamazsa) ÇIKARIMSAL özet: dosya türü, taraflar, açılış, dava/iddianame
     metnindeki "KONU" satırı, önemli evraklar (karar, bilirkişi, tensip...) ve son durumdan cümleler kurulur.
     Hiçbir bilgi uydurulmaz; yalnızca katalogda olan yazılır.

Özet Notion "DOSYA KONUSU" sütununa ve TickTick dosya kartının "📌 Dosya konusu" başlığına yazılır. Kullanıcının
Notion'da elle yazdığı konu ASLA ezilmez (notion_uyap.py, en son kendi yazdığı metinle karşılaştırır).
"""
from __future__ import annotations

import json
import re
import sqlite3
import urllib.request

_ONEMLI = (
    ("dava dilek", "dava dilekçesi"), ("iddianame", "iddianame"), ("takip talep", "takip talebi"),
    ("ödeme emri", "ödeme emri"), ("cevap dilek", "cevap dilekçesi"), ("tensip", "tensip zaptı"),
    ("ön inceleme", "ön inceleme"), ("bilirkişi", "bilirkişi raporu"), ("ara karar", "ara karar"),
    ("gerekçeli karar", "gerekçeli karar"), ("karar", "karar"), ("istinaf", "istinaf"),
    ("temyiz", "temyiz"), ("hükmün açıklanmasının", "HAGB kararı"), ("kesinleş", "kesinleşme"),
    ("haciz", "haciz"), ("itiraz", "itiraz"),
)
_KONU_DESEN = re.compile(
    r"(?:DAVANIN\s+KONUSU|DAVA\s+KONUSU|TALEP\s+KONUSU|KONUSU|KONU|SUÇ|SUÇLAR|ALACAK\s+MİKTARI)\s*[:：]\s*(.{15,400}?)(?:\n\s*\n|\n[A-ZÇĞİÖŞÜ ]{4,}\s*:|$)",
    re.S | re.I,
)


def _tr_tarih(iso: str) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(iso or ""))
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else str(iso or "")[:10]


def _cumle(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip(" .;,")
    return (s[0].upper() + s[1:] + ".") if s else ""


def _taraflar(taraf_txt: str, muv_txt: str) -> tuple[list, list]:
    muv = {m.strip() for m in (muv_txt or "").split(";") if m.strip()}
    biz, karsi = [], []
    for p in (taraf_txt or "").split(";"):
        p = p.strip()
        if not p:
            continue
        m = re.match(r"^(.*?)\s*\(([^()]*)\)", p)
        ad, rol = (m.group(1).strip(), m.group(2).strip()) if m else (p, "")
        (biz if f"{ad} ({rol})" in muv else karsi).append((ad, rol))
    return biz, karsi


def veri_topla(db: sqlite3.Connection, dkey: str) -> dict | None:
    """Özet için katalogdan dosya, evrak listesi ve (varsa) metinleri toplar."""
    db.row_factory = sqlite3.Row
    d = db.execute("SELECT * FROM dosya WHERE dkey=?", (dkey,)).fetchone()
    if not d:
        return None
    evraklar = [dict(r) for r in db.execute(
        "SELECT id, tur, aciklama, tarih, kategori, is_ek FROM evrak WHERE dkey=? AND COALESCE(is_ek,0)=0 ORDER BY tarih, id",
        (dkey,)).fetchall()]
    metinler = []
    try:
        aday = [e for e in evraklar if any(k in (e.get("tur") or "").lower() for k, _ in _ONEMLI[:4])] or evraklar[:3]
        for e in aday[:4]:
            r = db.execute("SELECT metin FROM evrak_fts WHERE rowid=?", (e["id"],)).fetchone()
            if r and r[0]:
                metinler.append({"tur": e.get("tur") or "", "tarih": e.get("tarih") or "", "metin": r[0][:6000]})
    except sqlite3.Error:
        pass
    hesap = None
    try:
        r = db.execute("SELECT takip_kesinlesen_miktar, bakiye_borc FROM icra_hesap WHERE dkey=?", (dkey,)).fetchone()
        if r:
            hesap = {"takip": r[0], "bakiye": r[1]}
    except sqlite3.Error:
        pass
    return {"dosya": dict(d), "evraklar": evraklar, "metinler": metinler, "hesap": hesap}


def cikarimsal_ozet(v: dict) -> str:
    """Yapay zekâsız 5-10 cümlelik konu özeti (yalnızca katalogdaki bilgiler)."""
    d = v["dosya"]
    tur = (d.get("dosya_tur") or "").strip() or "dava"
    cumleler = []
    acilis = _tr_tarih(d.get("acilis"))
    tur_ad = tur.lower() if tur.lower().endswith("dosyası") else f"{tur.lower()} dosyası"
    cumleler.append(_cumle(f"{d.get('birim') or ''} {d.get('dosya_no') or ''} sayılı {tur_ad}"
                           + (f" {acilis} tarihinde açılmıştır" if acilis else " UYAP'ta kayıtlıdır")))
    biz, karsi = _taraflar(d.get("taraflar") or "", d.get("muvekkil") or "")
    if biz:
        cumleler.append(_cumle("Müvekkil " + ", ".join(f"{a} ({r.lower()})" if r else a for a, r in biz[:3])
                               + (f" ve {len(biz) - 3} kişi daha" if len(biz) > 3 else "")))
    if karsi:
        cumleler.append(_cumle("Karşı taraf/diğer taraflar " + ", ".join(f"{a} ({r.lower()})" if r else a for a, r in karsi[:4])
                               + (f" ve {len(karsi) - 4} taraf daha" if len(karsi) > 4 else "")))
    konu = ""
    for m in v.get("metinler") or []:
        k = _KONU_DESEN.search(m.get("metin") or "")
        if k:
            konu = re.sub(r"\s+", " ", k.group(1)).strip()[:350]
            cumleler.append(_cumle(f"{m['tur'] or 'Esas evrak'} metnine göre uyuşmazlığın konusu: {konu}"))
            break
    evr = v.get("evraklar") or []
    if evr:
        ilk = evr[0]
        if not konu:
            cumleler.append(_cumle(f"Dosyadaki ilk evrak {_tr_tarih(ilk.get('tarih'))} tarihli "
                                   f"{(ilk.get('tur') or 'evrak').strip()}" + (f" ({ilk['aciklama'][:80]})" if ilk.get("aciklama") else "")))
        gorulen, onemli = set(), []
        for e in evr:
            t = (e.get("tur") or "").lower()
            for anahtar, ad in _ONEMLI[4:]:
                if anahtar in t and ad not in gorulen:
                    gorulen.add(ad)
                    onemli.append(f"{_tr_tarih(e.get('tarih'))} {ad}")
                    break
        if onemli:
            cumleler.append(_cumle("Önemli aşamalar: " + "; ".join(onemli[-5:])))
        cumleler.append(_cumle(f"Dosyada toplam {len(evr)} evrak bulunmaktadır"))
        son = evr[-1]
        cumleler.append(_cumle(f"Son işlem {_tr_tarih(son.get('tarih'))} tarihli {(son.get('tur') or 'evrak').strip()}"
                               + (f" ({son['aciklama'][:80]})" if son.get("aciklama") else "")))
    h = v.get("hesap")
    if h and (h.get("takip") or h.get("bakiye")):
        cumleler.append(_cumle(f"Takip miktarı {float(h.get('takip') or 0):,.2f} TL, kalan bakiye {float(h.get('bakiye') or 0):,.2f} TL"
                               .replace(",", "X").replace(".", ",").replace("X", ".")))
    durum = (d.get("durum") or "").strip()
    if durum:
        cumleler.append(_cumle(f"Dosya UYAP'ta {durum.lower()} durumdadır"))
    cumleler = [c for c in cumleler if c]
    while len(cumleler) < 5:
        cumleler.append(_cumle("Ayrıntılı bilgi için dosya evrakları incelenmelidir") if len(cumleler) == 4
                        else _cumle(f"Yargı türü: {(d.get('yargi') or tur)}"))
    return " ".join(cumleler[:10])


def _istem(v: dict) -> str:
    d = v["dosya"]
    parca = [f"Mahkeme/Birim: {d.get('birim')}", f"Esas: {d.get('dosya_no')}", f"Tür: {d.get('dosya_tur')}",
             f"Durum: {d.get('durum')}", f"Açılış: {d.get('acilis')}", f"Taraflar: {d.get('taraflar')}",
             f"Müvekkil(ler): {d.get('muvekkil')}", "Evraklar (tarih - tür - açıklama):"]
    for e in (v.get("evraklar") or [])[-60:]:
        parca.append(f"- {str(e.get('tarih') or '')[:10]} - {e.get('tur') or ''} - {(e.get('aciklama') or '')[:120]}")
    for m in v.get("metinler") or []:
        parca.append(f"\n[{m['tur']} metni]\n{m['metin'][:5000]}")
    return ("Aşağıda bir Türk mahkeme/icra dosyasının UYAP bilgileri var. Avukatın dosya kartı için 5-10 cümlelik, "
            "Türkçe, yalın bir 'dosya konusu' özeti yaz: uyuşmazlığın/suçun konusu, taraflar ve rolleri, talep, "
            "önemli aşamalar ve son durum. Bilgide olmayan hiçbir şeyi uydurma, tahmin yürütme; madde işareti ve "
            "başlık kullanma, yalnızca düz paragraf yaz.\n\n" + "\n".join(parca))[:30000]


def yapay_zeka_ozet(v: dict, anahtar: str, saglayici: str = "anthropic", model: str = "", zaman_asimi: int = 60) -> str:
    istem = _istem(v)
    saglayici = (saglayici or "anthropic").lower()
    if saglayici == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        govde = {"model": model or "gpt-4o-mini", "messages": [{"role": "user", "content": istem}], "max_tokens": 700}
        bas = {"Authorization": f"Bearer {anahtar}", "Content-Type": "application/json"}
    else:
        url = "https://api.anthropic.com/v1/messages"
        govde = {"model": model or "claude-haiku-5-5", "max_tokens": 700, "messages": [{"role": "user", "content": istem}]}
        bas = {"x-api-key": anahtar, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(govde).encode("utf-8"), headers=bas, method="POST")
    with urllib.request.urlopen(req, timeout=zaman_asimi) as r:
        cevap = json.loads(r.read().decode("utf-8"))
    if saglayici == "openai":
        metin = cevap["choices"][0]["message"]["content"]
    else:
        metin = "".join(b.get("text", "") for b in cevap.get("content") or [] if b.get("type") == "text")
    metin = re.sub(r"\s+", " ", metin or "").strip()
    if len(metin) < 40:
        raise ValueError("Yapay zekâ boş özet döndürdü")
    return metin[:1900]


def ozetle(db: sqlite3.Connection, dkey: str, ayar: dict | None = None) -> dict | None:
    """{'metin', 'kaynak': 'yapay zekâ' | 'otomatik (evraklardan)'} döner. Notion metin alanı sınırı: 2000 karakter."""
    v = veri_topla(db, dkey)
    if not v:
        return None
    ayar = ayar or {}
    anahtar = (ayar.get("OZET_API_KEY") or "").strip()
    if anahtar:
        try:
            return {"metin": yapay_zeka_ozet(v, anahtar, ayar.get("OZET_SAGLAYICI") or "anthropic", ayar.get("OZET_MODEL") or ""),
                    "kaynak": "yapay zekâ"}
        except Exception as e:  # noqa: BLE001  — ulaşılamazsa çıkarımsal özete düşülür
            return {"metin": cikarimsal_ozet(v)[:1900], "kaynak": "otomatik (evraklardan)", "uyari": f"Yapay zekâ: {str(e)[:160]}"}
    return {"metin": cikarimsal_ozet(v)[:1900], "kaynak": "otomatik (evraklardan)"}
