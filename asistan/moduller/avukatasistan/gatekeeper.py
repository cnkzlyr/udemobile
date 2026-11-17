#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GÖREV SÖZLEŞMESİ (gatekeeper): TickTick'e yazılacak/yazılmış her görevin uyması gereken kurallar.
- check(task_dict)  -> ihlal listesi (hem yazmadan önce hem sentinel taramasında aynı kural)
- guard_create(...) -> ihlal varsa görevi AÇTIRMAZ, karantina.jsonl'a yazar
Kurallar SISTEM.md ile birebir aynıdır. Değiştirmek için yalnızca bu dosya düzenlenir.
"""
import os, re, json
from datetime import datetime
import kimlik

HERE = os.path.dirname(os.path.abspath(__file__))
QUARANTINE = os.path.join(HERE, "karantina.jsonl")

TYPE_TAGS = {"uets", "duruşma", "durusma", "cmk"}
GENERIC_TITLE = re.compile(r"^\s*(yap[ıi]lacak|g[öo]rev|not|todo|yeni)?\s*(#\w+\s*)*$", re.I)
ESAS = re.compile(r"\d{4}/\d+")
CANON = {
    "tebligat": re.compile(r"^📨 TEBLİGAT - .+ - \d{4}/\d+ Esas"),
    "durusma": re.compile(r"^⚖️ DURUŞMA - .+ - \d{4}/\d+ Esas"),
    "kart": re.compile(r"^.+ - \d{4}/\d+ Esas\s*$"),
}


def infer_kind(t: dict) -> str:
    k = kimlik.oku(t.get("content") or "")
    if k.get("tur") in ("TEBLİGAT", "DURUŞMA", "DOSYA"):
        return {"TEBLİGAT": "tebligat", "DURUŞMA": "durusma", "DOSYA": "kart"}[k["tur"]]
    ti = t.get("title") or ""
    tags = [x.lower() for x in (t.get("tags") or [])]
    if "TEBL" in ti.upper() or "uets" in tags:
        return "tebligat"
    if re.search(r"duruşma|durusma", ti, re.I) or "duruşma" in tags:
        return "durusma"
    if not t.get("parentId") and ESAS.search(ti):
        return "kart"
    return "diger"


def client_tags(tags):
    return [x for x in (tags or []) if x.lower() not in TYPE_TAGS]


def check(t: dict, kind: str = None):
    """[(kod, ciddiyet, mesaj)] döner. ciddiyet: 'blok' (açılamaz) ya da 'uyari'."""
    kind = kind or infer_kind(t)
    ti = (t.get("title") or "").strip()
    tags = t.get("tags") or []
    v = []
    # Dosya bilgisi KİMLİK satırındaysa başlık serbesttir (kullanıcı başlığı değiştirebilir).
    k = kimlik.oku(t.get("content") or "")
    kimlikte_dosya = bool(k.get("esas") or k.get("uets_no") or k.get("barkod"))
    ozel_baslik = kimlik.kullanici_basligi_mi(ti)

    def add(code, sev, msg):
        v.append((code, sev, msg))

    if not ti or GENERIC_TITLE.match(ti):
        add("V01", "blok", "Başlık boş ya da genel ('Yapılacak' gibi)")
    if re.search(r"(^|\s)#\w+", ti):
        add("V02", "uyari", "Başlıkta ham #etiket kalmış (e-posta/bulut biçimi)")
    if kind in ("tebligat", "durusma", "kart") and not ESAS.search(ti) and not kimlikte_dosya:
        add("V03", "blok", "Başlıkta esas no (YYYY/N) yok")
    if kind in ("tebligat", "durusma") and not CANON[kind].match(ti) and not ozel_baslik and not kimlikte_dosya:
        add("V04", "uyari", f"Başlık standart biçimde değil ({kind})")
    if kind == "tebligat" and "uets" not in [x.lower() for x in tags]:
        add("V05", "blok", "Tebligat görevinde #uets etiketi yok")
    if kind == "durusma" and not {"duruşma", "durusma"} & {x.lower() for x in tags}:
        add("V05", "blok", "Duruşma görevinde #duruşma etiketi yok")
    if kind in ("tebligat", "durusma", "kart") and not client_tags(tags):
        add("V06", "uyari", "Müvekkil etiketi yok")
    if kind in ("tebligat", "durusma") and not t.get("parentId") and not t.get("_parent_pending"):
        add("V07", "uyari", "Dosya kartına (parent) bağlı değil")
    if kind in ("tebligat", "durusma") and not t.get("dueDate"):
        add("V08", "blok", "Tarih/süre (dueDate) yok")
    if kind == "tebligat" and not t.get("startDate"):
        add("V08", "uyari", "Tebligat süre çubuğu için startDate yok")
    if kind in ("tebligat", "durusma", "kart") and not (t.get("content") or "").strip():
        add("V09", "blok", "Açıklama/içerik boş")
    if kind == "tebligat" and (t.get("priority") or 0) != 5:
        add("V10", "uyari", "Tebligat önceliği 5 olmalı")
    if kind == "durusma" and (t.get("priority") or 0) < 3:
        add("V10", "uyari", "Duruşma önceliği en az 3 olmalı")
    if kind in ("kart", "durusma") and "uets" in [x.lower() for x in tags]:
        add("V11", "blok", "#uets yalnızca aktif tebligat görevine verilir")
    if kind == "kart" and t.get("dueDate"):
        add("V12", "uyari", "Dosya kartı tarihsiz olmalı")
    return v


def blocking(violations):
    return [x for x in violations if x[1] == "blok"]


def quarantine(entry: dict, violations, source=""):
    rec = {"ts": datetime.now().isoformat(timespec="seconds"), "source": source,
           "task": {k: entry.get(k) for k in ("title", "projectId", "tags", "content", "dueDate")},
           "ihlaller": [f"{c}: {m}" for c, _, m in violations]}
    try:
        with open(QUARANTINE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def guard_create(entry: dict, kind: str = None, source=""):
    """True: açılabilir. False: sözleşmeyi bozuyor, açılmadı, karantinaya yazıldı."""
    t = dict(entry)
    if "dueDate" not in t and entry.get("due_iso"):
        t["dueDate"] = entry["due_iso"]
    v = check(t, kind)
    b = blocking(v)
    if b:
        quarantine(t, b, source)
        print("   🛑 SÖZLEŞME İHLALİ, görev AÇILMADI: " + "; ".join(m for _, _, m in b))
        return False
    return True
