#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TickTick Ek Dağıtıcı (Attachment Distributor):
- E-posta ile TickTick'e atılan taşıyıcı görevi (carrier task) Inbox'ta bulur.
- İçindeki ![file](...) ek linklerini parse eder.
- İlgili hedef görevlerin içeriğine (content) dosyaları (.udf ve .odt) ekler.
- Taşıyıcı görevi temizler.
"""

import sys, os, re, time, json
import requests

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # proje kökü (araç araclar/ altında)
sys.path.insert(0, HERE)
from config import CONFIG, PROJECT_IDS

H = {"Authorization": f"Bearer {CONFIG['TICKTICK_TOKEN']}", "Content-Type": "application/json"}
B = CONFIG["TICKTICK_API_BASE"]

TARGET_MAPPING = {
    # Dosya anahtar kelimesi -> (Hedef Task ID, Hedef Proje Adı, Başlık Özeti)
    "Oltu2AsH_2025_48": ("6ace1edc8f086d8c22f168d6", "AsliyeHukukMahkemesi", "Erol Atmaca SGK Bilirkişi Raporuna İtiraz"),
    "Ankara73AsC_2026_142": ("6ad49cc58f08baf7cbd1fdcd", "AsliyeCezaMahkemesi", "Baneen Zaid Mütalaaya Karşı Beyan"),
    "Ankara2Cocuk_2025_385": ("6acf7a0c8f0876e81c516c5a", "ÇocukMahkemesi", "Nesrin Tektek CVOK İstinaf Başvurusu"),
    "Oltu3AsH_2026_24_Derkenar": ("6ad899018f0899b8c562b52a", "AsliyeHukukMahkemesi", "Oltu 3. Asliye Derkenar Talebi"),
    "OltuIcra_2026_345_Mehil": ("6ad899038f0899b8c562b56e", "AsliyeHukukMahkemesi", "Oltu İcra Mehil Vesikası Talebi")
}


def wait_for_carrier_task(max_retries=15, delay=5):
    print("⏳ TickTick Inbox taranıyor, ek taşıyıcı e-postanın işlenmesi bekleniyor...")
    inbox_pid = PROJECT_IDS.get("Inbox", "inbox")

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(f"{B}/project/{inbox_pid}/data", headers=H, timeout=15)
            if r.status_code == 200:
                tasks = r.json().get("tasks", [])
                for t in tasks:
                    ti = t.get("title") or ""
                    cnt = t.get("content") or ""
                    if "DİLEKÇE EK TAŞIYICI" in ti or "![file]" in cnt:
                        print(f"🎯 Taşıyıcı görev bulundu! (ID: {t['id']}, Deneme: {attempt})")
                        return t
        except Exception as e:
            print(f"⚠️ Hata: {e}")

        print(f"   [{attempt}/{max_retries}] Henüz işlenmedi, {delay} sn bekleniyor...")
        time.sleep(delay)

    return None


def distribute():
    carrier = wait_for_carrier_task()
    if not carrier:
        print("❌ Taşıyıcı görev bulunamadı veya TickTick henüz ekleri işlemedi.")
        return False

    cnt = carrier.get("content") or ""
    file_matches = re.findall(r"(!\[file\]\([^)]+\))", cnt)
    print(f"📎 Bulunan toplam ek sayısı: {len(file_matches)}")

    if not file_matches:
        print("⚠️ Görevde ![file] linki bulunamadı. İçerik:\n", cnt[:500])
        return False

    distributed = 0
    for key, (target_tid, target_proj, desc) in TARGET_MAPPING.items():
        # Bu dosyaya ait ekleri filtrele
        matched_links = [m for m in file_matches if key in m]
        if not matched_links:
            print(f"⚠️ {key} için eşleşen ek bulunamadı.")
            continue

        pid = PROJECT_IDS[target_proj]
        r_get = requests.get(f"{B}/project/{pid}/task/{target_tid}", headers=H, timeout=10)
        if r_get.status_code != 200:
            print(f"⚠️ Hedef görev çekilemedi ({target_tid})")
            continue

        target_task = r_get.json()
        old_content = target_task.get("content") or ""

        # Ekleri markdown bloğu olarak hazırla
        attachment_block = "\n\n### ⚖️ HAZIRLANAN DİLEKÇELER (.UDF & .ODT):\n"
        for link in matched_links:
            attachment_block += f"- {link}\n"

        # İçeriğe iliştir (zaten eklenmemişse)
        if key not in old_content:
            new_content = old_content + attachment_block
            payload = {
                "id": target_tid,
                "projectId": pid,
                "content": new_content
            }
            r_post = requests.post(f"{B}/task/{target_tid}", headers=H, json=payload, timeout=10)
            if r_post.status_code == 200:
                print(f"✅ Ekler başarıyla eklendi -> [{target_proj}] {desc} ({len(matched_links)} dosya)")
                distributed += 1
            else:
                print(f"❌ Güncellenemedi ({target_tid}): {r_post.status_code}")
        else:
            print(f"ℹ️ {desc} görevinde bu ekler zaten mevcut.")

    # Taşıyıcı görevi temizle (Inbox'ta kalabalık yapmasın)
    print("\n🧹 Taşıyıcı görev TickTick'ten siliniyor...")
    inbox_pid = PROJECT_IDS.get("Inbox", "inbox")
    requests.delete(f"{B}/project/{inbox_pid}/task/{carrier['id']}", headers=H, timeout=10)
    print("✅ Taşıyıcı görev temizlendi.")
    return True


if __name__ == "__main__":
    distribute()
