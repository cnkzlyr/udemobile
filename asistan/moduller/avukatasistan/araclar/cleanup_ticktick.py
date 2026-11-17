#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧹 TICKTICK GÜVENLİ TEMİZLİK VE İYİLEŞTİRME SCRİPTİ (v1.0)
- Varsayılan olarak DRY-RUN (Önizleme) modundadır. Hiçbir veriye dokunmaz!
- Canlı uygulamak için: python3 cleanup_ticktick.py --apply
- Yapılan işlemler:
  1. 9 yetim duruşma alt görevini aynı projedeki ana dava kartlarına bağlar ve başlıklarını '⚖️ DURUŞMA - ' formatına çevirir.
  2. Yanlışlıkla parentId atanmış 2 ana dava kartını (Ankara Batı 4. Ağır Ceza ve Ereğli Ağır Ceza) üst karta dönüştürür.
  3. Kalan yetim icra/vekalet ücreti görevlerinin parentId'sini temizler veya varsa dosyasına bağlar.
  4. 2 mükerrer dava kartını (Torul İcra ve Bigadiç Ceza) notlarını birleştirerek teke indirir.
  5. Başlığında ham '#DURUŞMA' kalan diğer tüm görevleri kanonik '⚖️ DURUŞMA - ' formatına dönüştürür.
  6. Başlığı kesilmiş 2 İdare Mahkemesi tebligatına esas numaralarını ekler.
- Her canlı işlemden önce etkilenen tüm görevlerin ham hali 'backup_before_cleanup.json' dosyasına kaydedilir!
"""

import sys, os, re, json, time, argparse
from datetime import datetime
from collections import defaultdict
import requests

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # proje kökü (araç araclar/ altında)
sys.path.insert(0, HERE)
from config import CONFIG, PROJECT_IDS

H = {"Authorization": f"Bearer {CONFIG['TICKTICK_TOKEN']}", "Content-Type": "application/json"}
B = CONFIG["TICKTICK_API_BASE"]


def fetch_all_tasks():
    print("⏳ TickTick görevleri taranıyor...")
    ps = [{"id": "inbox", "name": "Inbox"}] + requests.get(B + "/project", headers=H, timeout=25).json()
    tasks = []
    for p in ps:
        r = requests.get(f"{B}/project/{p['id']}/data", headers=H, timeout=25)
        if r.status_code == 200:
            for t in r.json().get("tasks", []):
                t["_p"] = p["name"]
                t["_pid"] = p["id"]
                tasks.append(t)
        time.sleep(0.2)
    print(f"✅ Toplam {len(tasks)} görev çekildi.\n")
    return tasks


def plan_actions(tasks):
    ids = {t["id"]: t for t in tasks}
    actions = []

    # 1. Yetim Alt Görevler (parentId var ama aktif görevler arasında yok)
    orphans = [t for t in tasks if t.get("parentId") and t["parentId"] not in ids]

    for o in orphans:
        ti = o.get("title") or ""
        pid = o["_pid"]
        pname = o["_p"]
        esas_matches = re.findall(r"\d{4}/\d+", ti)

        # Durum A: Duruşma görevi ve esas no var
        if ("#DURUŞMA" in ti or "DURUŞMA" in ti.upper()) and esas_matches:
            esas = esas_matches[0]
            # Aynı projede aynı esas numarasına sahip ana dava kartını bul
            parent = next((t for t in tasks if t["_pid"] == pid and not t.get("parentId") and esas in (t.get("title") or "")), None)
            new_title = re.sub(r"^#DURUŞMA\s*-\s*", "⚖️ DURUŞMA - ", ti)
            if parent:
                actions.append({
                    "tur": "RELINK_DURUSMA",
                    "task": o,
                    "target_parent": parent["id"],
                    "parent_title": parent["title"],
                    "new_title": new_title,
                    "aciklama": f"Yetim duruşma görevi aynı projedeki dava kartına ({parent['title']}) bağlanacak, başlık düzeltilecek"
                })
            else:
                actions.append({
                    "tur": "UNPARENT_DURUSMA",
                    "task": o,
                    "target_parent": None,
                    "new_title": new_title,
                    "aciklama": "Duruşma görevinin parentId'si temizlenecek (bağlı kart bulunamadı)"
                })

        # Durum B: Kendisi aslında bir ana dava kartı olan ama yanlışlıkla parentId set edilmişler
        elif "Ağır Ceza Mahkemesi" in ti and ("Esas" in ti or esas_matches):
            actions.append({
                "tur": "CLEAR_PARENT_CASE",
                "task": o,
                "target_parent": None,
                "new_title": None,
                "aciklama": f"Yanlışlıkla parentId atanmış dava kartı üst seviye karta dönüştürülecek ({ti})"
            })

        # Durum C: İcra takibi / vekalet ücreti görevleri
        else:
            # İçerikte dosya no var mı bak
            cnt = o.get("content") or ""
            m_esas = re.findall(r"\d{4}/\d+", cnt)
            parent = None
            if m_esas:
                parent = next((t for t in tasks if m_esas[0] in (t.get("title") or "")), None)

            if parent:
                actions.append({
                    "tur": "RELINK_SUBTASK",
                    "task": o,
                    "target_parent": parent["id"],
                    "parent_title": parent["title"],
                    "new_title": None,
                    "aciklama": f"İçerikten tespit edilen dava kartına ({parent['title']}) bağlanacak"
                })
            else:
                actions.append({
                    "tur": "CLEAR_PARENT_ORPHAN",
                    "task": o,
                    "target_parent": None,
                    "new_title": None,
                    "aciklama": "Bağlı olduğu eski parent silinmiş; kopuk alt görev hatasını gidermek için parentId temizlenecek"
                })

    # 2. Gerçek Mükerrer Dava Kartları
    # Bigadiç Asliye Ceza 2021/289
    bigadic = [t for t in tasks if t["_p"] == "AsliyeCezaMahkemesi" and "2021/289" in (t.get("title") or "") and not t.get("parentId")]
    if len(bigadic) == 2:
        keep, remove = bigadic[0], bigadic[1]
        actions.append({
            "tur": "MERGE_DUPLICATE_CARD",
            "task": remove,
            "keep_task": keep,
            "aciklama": f"Birebir aynı Bigadiç 2021/289 kartı silinecek (Asıl: {keep['id']}, Silinecek: {remove['id']})"
        })

    # Torul İcra 2026/2 (2023/99)
    torul = [t for t in tasks if t["_p"] == "İcraTakipleri" and "Torul" in (t.get("title") or "") and "2026/2" in (t.get("title") or "") and not t.get("parentId")]
    if len(torul) == 2:
        keep, remove = torul[0], torul[1]
        actions.append({
            "tur": "MERGE_DUPLICATE_CARD",
            "task": remove,
            "keep_task": keep,
            "aciklama": f"Yinelenen Torul İcra kartı notları korunarak birleştirilecek (Silinecek: {remove['id']})"
        })

    # 3. Başlığında ham #DURUŞMA kalan diğer görevleri kanonik ⚖️ formatına çevir
    for t in tasks:
        ti = t.get("title") or ""
        if ti.startswith("#DURUŞMA"):
            # Daha önce orphans listesinde ele alınmadıysa
            if not any(a["task"]["id"] == t["id"] for a in actions):
                new_title = re.sub(r"^#DURUŞMA\s*-\s*", "⚖️ DURUŞMA - ", ti)
                tags = list(t.get("tags") or [])
                if "duruşma" not in [x.lower() for x in tags]:
                    tags.append("duruşma")
                actions.append({
                    "tur": "CANONICAL_DURUSMA_TITLE",
                    "task": t,
                    "new_title": new_title,
                    "new_tags": tags,
                    "aciklama": f"Başlıktaki ham '#DURUŞMA' kaldırılıp standart kanonik '⚖️ DURUŞMA - ' biçimine getirilecek"
                })

    # 4. İdare Mahkemesindeki başlığı kesilmiş tebligat görevleri
    yd_1366 = next((t for t in tasks if t["id"] == "6acdda598f08b7e28b4815fe"), None)
    if yd_1366 and "2026/1366" not in (yd_1366.get("title") or ""):
        actions.append({
            "tur": "RENAME_TEBLIGAT_ESAS",
            "task": yd_1366,
            "new_title": "📨 TEBLİGAT - Ankara 3. İdare Mahkemesi - 2026/1366 Esas (YD Kararı)",
            "aciklama": "Başlıkta eksik olan mahkeme ve esas numarası (2026/1366) eklenecek"
        })

    yd_1367 = next((t for t in tasks if t["id"] == "6ace00da8f08210fc185187b"), None)
    if yd_1367 and "2026/1367" not in (yd_1367.get("title") or ""):
        actions.append({
            "tur": "RENAME_TEBLIGAT_ESAS",
            "task": yd_1367,
            "new_title": "📨 TEBLİGAT - Ankara 3. İdare Mahkemesi - 2026/1367 Esas (YD Kararı)",
            "aciklama": "Başlıkta eksik olan mahkeme ve esas numarası (2026/1367) eklenecek"
        })

    return actions


def execute_plan(actions, apply=False):
    print("=" * 80)
    print(f"📋 İŞLEM PLANI ({'🚀 UYGULANIYOR' if apply else '🔍 ÖNİZLEME / DRY-RUN'}) - Toplam: {len(actions)} işlem")
    print("=" * 80)

    by_type = defaultdict(list)
    for a in actions:
        by_type[a["tur"]].append(a)

    for tur, items in by_type.items():
        print(f"\n📂 [{tur}] ({len(items)} adet)")
        for it in items:
            t = it["task"]
            print(f"  • [{t['_p']}] {t['title'][:65]}")
            print(f"    └─> {it['aciklama']}")
            if it.get("new_title"):
                print(f"    └─> Yeni Başlık: {it['new_title']}")

    if not apply:
        print("\n" + "=" * 80)
        print("💡 Bu bir ÖNİZLEMEDİR. TickTick üzerinde hiçbir değişiklik YAPILMADI.")
        print("💡 Canlı uygulamak için: python3 cleanup_ticktick.py --apply")
        print("=" * 80)
        return

    # Canlı Uygulama
    backup_file = os.path.join(HERE, "backup_before_cleanup.json")
    print(f"\n💾 Güvenlik amacıyla etkilenen görevler yedekleniyor -> {backup_file} ...")
    backup_data = []
    for a in actions:
        backup_data.append({
            "action": a["tur"],
            "task": a["task"],
            "timestamp": datetime.now().isoformat()
        })
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    print(f"✅ {len(backup_data)} görev başarıyla yedeklendi.\n")

    print("🚀 Değişiklikler TickTick'e uygulanıyor...")
    success = 0
    fail = 0

    for idx, a in enumerate(actions, 1):
        t = a["task"]
        tid = t["id"]
        pid = t["_pid"]
        tur = a["tur"]

        try:
            if tur in ("RELINK_DURUSMA", "RELINK_SUBTASK"):
                payload = {
                    "id": tid,
                    "projectId": pid,
                    "parentId": a["target_parent"]
                }
                if a.get("new_title"):
                    payload["title"] = a["new_title"]
                r = requests.post(f"{B}/task/{tid}", headers=H, json=payload, timeout=10)
                if r.status_code == 200:
                    success += 1
                else:
                    fail += 1

            elif tur in ("UNPARENT_DURUSMA", "CLEAR_PARENT_CASE", "CLEAR_PARENT_ORPHAN"):
                payload = {
                    "id": tid,
                    "projectId": pid,
                    "parentId": None
                }
                if a.get("new_title"):
                    payload["title"] = a["new_title"]
                r = requests.post(f"{B}/task/{tid}", headers=H, json=payload, timeout=10)
                if r.status_code == 200:
                    success += 1
                else:
                    fail += 1

            elif tur == "MERGE_DUPLICATE_CARD":
                keep = a["keep_task"]
                rem = a["task"]
                # Notları birleştir
                keep_cnt = (keep.get("content") or "").strip()
                rem_cnt = (rem.get("content") or "").strip()
                if rem_cnt and rem_cnt != keep_cnt:
                    new_cnt = keep_cnt + "\n\n📌 **BİRLEŞTİRİLEN EK NOTLAR:**\n" + rem_cnt
                    requests.post(f"{B}/task/{keep['id']}", headers=H, json={"id": keep["id"], "projectId": keep["_pid"], "content": new_cnt}, timeout=10)
                # Silinecek kartı sil
                r = requests.delete(f"{B}/project/{rem['_pid']}/task/{rem['id']}", headers=H, timeout=10)
                if r.status_code == 200:
                    success += 1
                else:
                    fail += 1

            elif tur == "CANONICAL_DURUSMA_TITLE":
                payload = {
                    "id": tid,
                    "projectId": pid,
                    "title": a["new_title"],
                    "tags": a["new_tags"]
                }
                r = requests.post(f"{B}/task/{tid}", headers=H, json=payload, timeout=10)
                if r.status_code == 200:
                    success += 1
                else:
                    fail += 1

            elif tur == "RENAME_TEBLIGAT_ESAS":
                payload = {
                    "id": tid,
                    "projectId": pid,
                    "title": a["new_title"]
                }
                r = requests.post(f"{B}/task/{tid}", headers=H, json=payload, timeout=10)
                if r.status_code == 200:
                    success += 1
                else:
                    fail += 1

            time.sleep(0.3)
        except Exception as e:
            print(f"⚠️ Hata ({tid}): {e}")
            fail += 1

    print(f"\n🎉 İşlem tamamlandı! Başarılı: {success}, Başarısız: {fail}")


def main():
    parser = argparse.ArgumentParser(description="TickTick Güvenli Temizlik Scripti")
    parser.add_argument("--apply", action="store_true", help="Değişiklikleri TickTick üzerinde canlı uygula")
    args = parser.parse_args()

    tasks = fetch_all_tasks()
    actions = plan_actions(tasks)
    execute_plan(actions, apply=args.apply)


if __name__ == "__main__":
    main()
