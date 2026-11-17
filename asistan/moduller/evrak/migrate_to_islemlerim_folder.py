#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
İşlemlerim Klasörleme ve Yol Güncelleme Betiği
=============================================
1. UYAP_Indirilenler altındaki 13 doğrudan mahkeme klasörünü
   UYAP_Indirilenler/ISLEMLERIM/ altına taşır.
2. indirme_gecmisi.json dosyasındaki yolları günceller.
3. indirme_indeksi.csv dosyasındaki yolları günceller.
4. Tüm dosyaların diskteki varlığını doğrular.
"""

import os
import sys
import json
import csv
import shutil
from pathlib import Path

BASE_DIR = Path("/sdcard/Download/UYAP_Indirilenler")
HISTORY_FILE = Path("/data/data/com.termux/files/home/uyap-evrak-indirici/indirme_gecmisi.json")
ISLEMLERIM_DIR = BASE_DIR / "ISLEMLERIM"

ISLEMLERIM_FOLDERS = [
    "Agir_Ceza_Mahkemesi",
    "Arabuluculuk_Burosu",
    "Asliye_Ceza_Mahkemesi",
    "Cocuk_Mahkemesi",
    "Cumhuriyet_Bassavciligi_Sorusturma",
    "Danistay",
    "Diger_Yargi_Birimi",
    "Icra_Dairesi",
    "Icra_Hukuk_Mahkemesi",
    "Infaz_Hakimligi",
    "Kadastro_Mahkemesi",
    "Sulh_Ceza_Hakimligi",
    "Sulh_Hukuk_Mahkemesi",
]

def main():
    print("=" * 70)
    print("  İşlemlerim Evraklarını ISLEMLERIM/ Klasörüne Taşıma")
    print("=" * 70)

    if not BASE_DIR.exists():
        print(f"[x] Ana dizin bulunamadı: {BASE_DIR}")
        sys.exit(1)

    ISLEMLERIM_DIR.mkdir(parents=True, exist_ok=True)
    moved_folders = []

    # 1. Klasörleri ISLEMLERIM altına taşı
    for folder_name in ISLEMLERIM_FOLDERS:
        src = BASE_DIR / folder_name
        dst = ISLEMLERIM_DIR / folder_name
        if src.exists() and src.is_dir():
            print(f"[*] Taşınıyor: {folder_name} -> ISLEMLERIM/{folder_name}")
            if dst.exists():
                # Merge if destination exists
                for item in src.iterdir():
                    shutil.move(str(item), str(dst / item.name))
                src.rmdir()
            else:
                shutil.move(str(src), str(dst))
            moved_folders.append(folder_name)

    print(f"[✓] {len(moved_folders)} adet klasör ISLEMLERIM altına taşındı.\n")

    # 2. indirme_gecmisi.json dosyasını güncelle
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            updated_count = 0
            for k, v in history.items():
                p = v.get("path", "")
                if not p:
                    continue
                # Eğer yol ISLEMLERIM içermiyorsa ve taşınan klasörlerden biriyse
                for folder in moved_folders:
                    target_sub = f"/{folder}/"
                    if target_sub in p and "/ISLEMLERIM/" not in p:
                        v["path"] = p.replace(f"/UYAP_Indirilenler/{folder}/", f"/UYAP_Indirilenler/ISLEMLERIM/{folder}/")
                        updated_count += 1
                        break

            HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[✓] indirme_gecmisi.json güncellendi: {updated_count} dosya yolu ISLEMLERIM/ ile tazelendi.")

            # Doğrulama
            valid_count = sum(1 for v in history.values() if os.path.exists(v.get("path", "")))
            print(f"[✓] Doğrulama: {valid_count} / {len(history)} kayıt diskte fiziksel olarak mevcut.")
        except Exception as e:
            print(f"[!] indirme_gecmisi.json güncellenirken hata: {e}")

    # 3. indirme_indeksi.csv dosyasını güncelle
    csv_file = BASE_DIR / "indirme_indeksi.csv"
    if csv_file.exists():
        try:
            content = csv_file.read_text(encoding="utf-8-sig")
            for folder in moved_folders:
                content = content.replace(f"/UYAP_Indirilenler/{folder}/", f"/UYAP_Indirilenler/ISLEMLERIM/{folder}/")
            csv_file.write_text(content, encoding="utf-8-sig")
            
            # Ayrıca bir kopyasını ISLEMLERIM altına da koy
            shutil.copy2(str(csv_file), str(ISLEMLERIM_DIR / "indeks.csv"))
            print(f"[✓] indirme_indeksi.csv güncellendi ve ISLEMLERIM/indeks.csv oluşturuldu.")
        except Exception as e:
            print(f"[!] indirme_indeksi.csv güncellenirken hata: {e}")

    print("\n" + "=" * 70)
    print("  İŞLEM BAŞARIYLA TAMAMLANDI")
    print("=" * 70)

if __name__ == "__main__":
    main()
