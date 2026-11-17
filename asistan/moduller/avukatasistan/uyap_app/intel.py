#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Duruşma tutanağı analizi: son N günün duruşmalarının evraklarından tutanak/zabıtları bulur, indirir,
UDF/PDF metnini çıkarır, yapılacakları ve sonraki tarihleri sezgisel olarak ayıklar.
Sonuç intel.json'a yazılır; TickTick/Notion için YALNIZCA öneri (dry-run) üretilir, otomatik yazmaz.
"""
import os, re, io, json, zipfile, threading, time
from datetime import datetime

import uyap_bridge as ub

HERE = os.path.dirname(os.path.abspath(__file__))
INTEL_PATH = os.path.join(HERE, "intel.json")
DOC_DIR = os.path.join(HERE, "documents")
TUTANAK = re.compile(r"duru[sş]ma|zab[ıi]t|tutana[gğ]|celse", re.I)
TODO_RX = re.compile(r"[^.\n]*(süre|gün içinde|ihtar|bilirkişi|tanık|ertelen|talep|beklen|ibraz|dinlen|celbi|müzekkere|tebliğ|ödenme|harç|avans)[^.\n]*[.\n]?", re.I)
DATE_RX = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b")


def udf_text(data: bytes) -> str:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        xml = z.read("content.xml").decode("utf-8", "ignore")
        m = re.search(r"<content><!\[CDATA\[(.*?)\]\]></content>", xml, re.S)
        return (m.group(1) if m else re.sub(r"<[^>]+>", " ", xml)).strip()
    except Exception:
        return ""


def pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    except Exception:
        return ""


def doc_text(data: bytes) -> str:
    if data[:2] == b"PK":
        return udf_text(data)
    if data[:4] == b"%PDF":
        return pdf_text(data)
    return data.decode("utf-8", "ignore")


def analyze(text: str) -> dict:
    todos = []
    for m in TODO_RX.finditer(text):
        s = " ".join(m.group(0).split())
        if 15 < len(s) < 300 and s not in todos:
            todos.append(s)
    dates = sorted({f"{int(d):02d}.{int(mo):02d}.{y}" for d, mo, y in DATE_RX.findall(text)},
                   key=lambda s: s.split(".")[::-1])
    return {"yapilacaklar": todos[:12], "tarihler": dates[-6:], "ozet": " ".join(text.split())[:600]}


class IntelEngine:
    def __init__(self, service):
        self.svc = service
        self.state = {"running": False, "progress": "", "items": {}}
        try:
            self.state["items"] = json.load(open(INTEL_PATH, encoding="utf-8")).get("items", {})
        except Exception:
            pass
        self.lock = threading.Lock()

    def save(self):
        json.dump({"items": self.state["items"], "saved": datetime.now().isoformat()},
                  open(INTEL_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def start(self, days=30):
        with self.lock:
            if self.state["running"]:
                return False
            self.state["running"] = True
        threading.Thread(target=self._run, args=(days,), daemon=True).start()
        return True

    def _run(self, days):
        try:
            os.makedirs(DOC_DIR, exist_ok=True)
            hear, _ = self.svc.hearings(days_back=days, days_fwd=0)
            seen = set()
            for i, h in enumerate(hear, 1):
                did = h["dosyaId"]
                if not did or did in seen:
                    continue
                seen.add(did)
                self.state["progress"] = f"{i}/{len(hear)} {h['dosyaNo']}"
                evs = self.svc.evraklar(did)[0]
                cands = [e for e in evs if TUTANAK.search(f"{e['tur']} {e['aciklama']}")][:3]
                item = self.state["items"].setdefault(did, {"dosyaNo": h["dosyaNo"], "birim": h["birimAdi"],
                                                            "taraflar": h["taraflar"], "belgeler": {}, "yapildi": []})
                item["digerEvraklar"] = [f"{e['tur']} {e['aciklama']}".strip() for e in evs[:25]]
                for e in cands:
                    key = e["evrakId"]
                    if key in item["belgeler"]:
                        continue
                    try:
                        data, ctype, disp = self.svc.document(e["evrakId"], did)
                    except ub.BridgeError as ex:
                        item["belgeler"][key] = {"ad": e["aciklama"], "hata": str(ex)}
                        continue
                    ext = "udf" if data[:2] == b"PK" else "pdf" if data[:4] == b"%PDF" else "bin"
                    fn = re.sub(r"[^\w.-]+", "_", f"{h['dosyaNo']}_{e['evrakId'][:12]}.{ext}")
                    open(os.path.join(DOC_DIR, fn), "wb").write(data)
                    item["belgeler"][key] = dict(analyze(doc_text(data)), ad=e["aciklama"] or e["tur"], dosya=fn)
                self.save()
            self.state["progress"] = "tamamlandı"
        except Exception as ex:
            self.state["progress"] = f"hata: {ex}"
        finally:
            self.state["running"] = False
            self.save()

    def toggle(self, dosya_id, todo):
        it = self.state["items"].get(dosya_id)
        if not it:
            return False
        if todo in it["yapildi"]:
            it["yapildi"].remove(todo)
        else:
            it["yapildi"].append(todo)
        self.save()
        return True

    def proposals(self):
        """TickTick/Notion için öneri listesi (otomatik yazılmaz)."""
        out = []
        for did, it in self.state["items"].items():
            for b in it["belgeler"].values():
                for t in b.get("yapilacaklar", []):
                    out.append({"dosyaNo": it["dosyaNo"], "birim": it["birim"], "gorev": t,
                                "tarihler": b.get("tarihler", []), "yapildi": t in it["yapildi"]})
        return out
