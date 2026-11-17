#!/usr/bin/env python3
"""TickTick SALT OKUNUR denetim: yalnızca GET. Hiçbir görev/proje değiştirilmez."""
import sys, json, time, re, collections
from datetime import datetime, timezone
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))  # proje kökü
import requests
from config import CONFIG

H = {"Authorization": f"Bearer {CONFIG['TICKTICK_TOKEN']}"}
B = CONFIG["TICKTICK_API_BASE"]
now = datetime.now(timezone.utc)


def get(p):
    for _ in range(3):
        r = requests.get(B + p, headers=H, timeout=25)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            time.sleep(5); continue
        return None
    return None


def norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


projects = get("/project") or []
print("projeler:", len(projects))
all_tasks, per = [], {}
for p in [{"id": "inbox", "name": "Inbox", "closed": False}] + projects:
    d = get(f"/project/{p['id']}/data")
    time.sleep(0.4)
    ts = (d or {}).get("tasks", [])
    per[p["name"]] = len(ts)
    for t in ts:
        t["_proj"] = p["name"]
    all_tasks += ts

print("aktif görev:", len(all_tasks))
print("\nProje başına görev (çoktan aza):")
for n, c in sorted(per.items(), key=lambda x: -x[1]):
    print(f"  {c:4d}  {n}")

ids = {t["id"] for t in all_tasks}
subs = [t for t in all_tasks if t.get("parentId")]
orph = [t for t in subs if t["parentId"] not in ids]
tops = [t for t in all_tasks if not t.get("parentId")]
print(f"\nüst görev: {len(tops)}  alt görev: {len(subs)}  yetim alt görev (parent yok): {len(orph)}")

def due(t):
    d = t.get("dueDate")
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%dT%H:%M:%S%z")
    except Exception:
        return None

over = [t for t in all_tasks if due(t) and due(t) < now]
nodue = [t for t in all_tasks if not t.get("dueDate")]
print(f"vadesi geçmiş: {len(over)}  tarihsiz: {len(nodue)}")
bucket = collections.Counter()
for t in over:
    days = (now - due(t)).days
    bucket["0-7g" if days <= 7 else "8-30g" if days <= 30 else "31-90g" if days <= 90 else "90g+"] += 1
print("gecikme dağılımı:", dict(bucket))
print("öncelik dağılımı:", dict(collections.Counter(t.get("priority", 0) for t in all_tasks)))

tags = collections.Counter(tg for t in all_tasks for tg in (t.get("tags") or []))
print(f"\nbenzersiz etiket: {len(tags)}  etiketsiz görev: {sum(1 for t in all_tasks if not t.get('tags'))}")
print("en sık 15 etiket:", tags.most_common(15))
cmk_bad = [tg for tg in tags if tg.startswith("cmk") and tg != "cmk" and not tg.startswith("cmk_")]
print("kural dışı cmk etiketleri:", cmk_bad[:15])
uets_on_cards = [t for t in tops if "uets" in (t.get("tags") or []) and re.search(r"\d{4}/\d+", t.get("title", "")) and not t.get("dueDate")]
print("#uets taşıyan olası dosya kartı:", len(uets_on_cards))
# benzer etiketler (ayırıcı farkı)
canon = collections.defaultdict(list)
for tg in tags:
    canon[re.sub(r"[^a-z0-9]", "", tg.lower())].append(tg)
print("yazım varyantlı etiketler:", [v for v in canon.values() if len(v) > 1][:12])

# yinelenen başlıklar
by = collections.defaultdict(list)
for t in all_tasks:
    by[(norm(t.get("title")), t["_proj"])].append(t)
dups = {k: v for k, v in by.items() if len(v) > 1 and k[0]}
print(f"\naynı proje+aynı başlık yinelenen grup: {len(dups)} (fazladan görev: {sum(len(v)-1 for v in dups.values())})")
for k, v in list(sorted(dups.items(), key=lambda x: -len(x[1])))[:8]:
    print(f"  x{len(v)} [{k[1]}] {k[0][:70]}")
by2 = collections.defaultdict(list)
for t in all_tasks:
    m = re.search(r"(\d{4}/\d+)", t.get("title", ""))
    if m and not t.get("parentId") and re.search(r"(esas|dosya|k\.|e\.)|mahkeme", t.get("title", ""), re.I):
        by2[(m.group(1), t["_proj"])].append(t)
cards_dup = {k: v for k, v in by2.items() if len(v) > 1}
print("aynı esas no için birden çok üst kart:", len(cards_dup))

# başlık kalıpları
pat = collections.Counter()
for t in all_tasks:
    ti = t.get("title", "")
    pat["tebligat" if re.search(r"tebligat|uets", ti, re.I) else "duruşma" if re.search(r"duruşma|celse|durusma", ti, re.I) else "diğer"] += 1
print("\nbaşlık türleri:", dict(pat))
empty = [n for n, c in per.items() if c == 0]
print("boş liste:", len(empty), empty[:10])
print("\nÖrnek vadesi çok geçmiş 8 görev:")
for t in sorted(over, key=lambda t: due(t))[:8]:
    print("  ", due(t).date(), t["_proj"], "|", t.get("title", "")[:70])
json.dump({"counts": per, "tags": tags.most_common(60), "overdue": len(over), "dups": len(dups)},
          open("ticktick_audit_ozet.json", "w"), ensure_ascii=False)
