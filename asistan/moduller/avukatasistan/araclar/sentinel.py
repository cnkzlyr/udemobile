#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SENTINEL: TickTick'i SALT OKUNUR tarar, gatekeeper kurallarına uymayan görevleri gruplayıp raporlar.
Hiçbir görevi değiştirmez/silmez. Kimin açtığını (yerel script mi, bulut/e-posta mı) tahmin eder.
Kullanım:  python3 sentinel.py            # ekrana rapor
           python3 sentinel.py --telegram # özeti Telegram'a da gönder (yalnızca sorun varsa)
           python3 sentinel.py --json out.json
"""
import sys, os, re, json, time, argparse, collections
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # proje kökü
import requests
from config import CONFIG
import gatekeeper as gk

H = {"Authorization": f"Bearer {CONFIG['TICKTICK_TOKEN']}"}
B = CONFIG["TICKTICK_API_BASE"]


def fetch_all():
    ps = [{"id": "inbox", "name": "Inbox"}] + requests.get(B + "/project", headers=H, timeout=25).json()
    out = []
    for p in ps:
        r = requests.get(f"{B}/project/{p['id']}/data", headers=H, timeout=25)
        for t in (r.json().get("tasks", []) if r.status_code == 200 else []):
            t["_p"] = p["name"]
            out.append(t)
        time.sleep(0.3)
    return out


def writer_guess(t):
    ti = t.get("title") or ""
    if ti.startswith(("⚖️ DURUŞMA", "📨 TEBLİGAT")):
        return "yerel script"
    if re.match(r"^#\w+", ti):
        return "bulut/e-posta (ham #etiket biçimi)"
    return "elle / bilinmiyor"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--telegram", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    tasks = fetch_all()
    ids = {t["id"] for t in tasks}
    now = datetime.now(timezone.utc)
    by_code = collections.defaultdict(list)
    for t in tasks:
        k = gk.infer_kind(t)
        for code, sev, msg in gk.check(t, k):
            by_code[(code, sev, msg)].append((t, k))
        if t.get("parentId") and t["parentId"] not in ids:
            by_code[("V13", "blok", "Yetim alt görev (parent bulunamadı)")].append((t, k))
        if t["_p"] == "Inbox":
            try:
                age = (now - datetime.strptime(t["createdTime"], "%Y-%m-%dT%H:%M:%S%z")).days
                if age > 7:
                    by_code[("V14", "uyari", "Inbox'ta 7 günden eski (triaj bekliyor)")].append((t, k))
            except Exception:
                pass
    print(f"⚖️ SENTINEL {datetime.now():%d.%m.%Y %H:%M} | {len(tasks)} aktif görev")
    total_block = 0
    report = []
    for (code, sev, msg), items in sorted(by_code.items(), key=lambda x: (x[0][1] != "blok", x[0][0])):
        if sev == "blok":
            total_block += len(items)
        w = collections.Counter(writer_guess(t) for t, _ in items)
        print(f"\n[{code}] {'🛑' if sev == 'blok' else '⚠️'} {msg}: {len(items)}  (kaynak: {dict(w)})")
        for t, k in items[:4]:
            print(f"    - [{t['_p']}] {t['title'][:70]}")
        report.append({"kod": code, "ciddiyet": sev, "mesaj": msg, "adet": len(items),
                       "kaynak": dict(w), "gorevler": [{"id": t["id"], "proje": t["_p"], "baslik": t["title"]} for t, _ in items]})
    q = os.path.join(gk.HERE, "karantina.jsonl")
    qn = sum(1 for _ in open(q, encoding="utf-8")) if os.path.exists(q) else 0
    print(f"\nÖZET: engelleyici ihlal {total_block} | karantinaya alınan (hiç açılmayan) {qn}")
    if a.json:
        json.dump(report, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.telegram and (total_block or qn):
        txt = f"⚖️ TickTick Sentinel: {total_block} engelleyici ihlal, {qn} karantina.\n" + "\n".join(
            f"[{r['kod']}] {r['mesaj']}: {r['adet']}" for r in report if r["ciddiyet"] == "blok")
        try:
            requests.post(f"https://api.telegram.org/bot{CONFIG['TELEGRAM_BOT_TOKEN']}/sendMessage",
                          json={"chat_id": CONFIG["TELEGRAM_CHAT_ID"], "text": txt[:3500]}, timeout=10)
        except Exception as e:
            print("Telegram gönderilemedi:", e)


if __name__ == "__main__":
    main()
