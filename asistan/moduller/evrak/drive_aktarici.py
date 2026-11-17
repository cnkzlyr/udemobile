#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır. / All rights reserved.
"""
UYAP Evrak Arşivi -> Google Drive Güvenli Aktarıcı
==================================================
Bilgisayara önceden indirilmiş tüm dava evraklarını (PDF, UDF, TIF vb.)
klasör yapısını ve hiyerarşisini KESİNLİKLE BOZMADAN Google Drive'a aktarır.

Aynı zamanda:
  1. Alt klasör düzenini (Ceza/Hukuk/Mahkeme/Esas/Evrak_Türü) birebir korur.
  2. SQLite veritabanındaki (uyap_katalog.db) tüm evrak ve PDF yollarını
     otomatik olarak yeni Google Drive yoluna günceller.
  3. Güncel veritabanının kilitlenmeyen bir yedeğini (uyap_katalog_yedek.db)
     Google Drive kök dizinine bırakır.
  4. Nöbetçi Bot (uyap_watcher.py) yapılandırmasını yeni Drive klasörüne bağlar.
  5. Orijinal dosyaları hemen silmez (güvenlik için korur; doğrulandıktan sonra
     isteğe bağlı silinebilir).

Kullanım:
  python drive_aktarici.py            # Otomatik algıla ve aktar
  python drive_aktarici.py --dry-run  # Hiçbir şey değiştirmeden simüle et
  python drive_aktarici.py --hedef "G:\\Drive'ım\\UYAP_Arsiv"
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
DATA_DIR = Path(os.environ.get("UYAP_VERI_DIZINI") or BASE_DIR)
DB_PATH = DATA_DIR / "uyap_katalog.db"
CONFIG_FILE = DATA_DIR / "watcher_config.json"


def detect_source_dir() -> Path:
    """Mevcut yerel indirme klasörünü bulur."""
    candidates = [
        Path.home() / "Downloads" / "UYAP_Indirilenler",
        BASE_DIR / "UYAP_Indirilenler",
        BASE_DIR.parent / "UYAP_Indirilenler",
    ]
    for c in candidates:
        if c.exists() and (c / "DAVA_EVRAKLARI").exists():
            return c.resolve()
    for c in candidates:
        if c.exists():
            return c.resolve()
    return candidates[0]


def detect_target_drive_dir() -> Path | None:
    """Google Drive klasörünü otomatik bulur."""
    cands = [
        Path("G:/Drive'ım/UYAP_Arsiv"),
        Path("G:/My Drive/UYAP_Arsiv"),
        Path.home() / "Google Drive" / "UYAP_Arsiv",
        Path.home() / "GoogleDrive" / "UYAP_Arsiv",
    ]
    for c in cands:
        if c.parent.exists():
            return c
    return None


def copy_files_preserving_structure(src: Path, dst: Path, dry_run: bool = False) -> tuple[int, int]:
    """Dosyaları ve klasör yapısını birebir kopyalar.
    Windows'ta robocopy kullanarak en yüksek hız ve öznitelik koruması sağlar."""
    dst.mkdir(parents=True, exist_ok=True)

    if dry_run:
        count = sum(1 for _ in src.rglob("*") if _.is_file())
        print(f"[Simülasyon] Toplam {count} adet dosya {src} -> {dst} konumuna kopyalanacak.")
        return count, 0

    print(f"[*] Dosyalar aktarılıyor: {src} -> {dst}")
    print("    (Klasör yapısı, alt dizinler ve dosya tarihleri birebir korunuyor...)")

    if os.name == "nt":
        # Windows Robocopy (en güvenli ve hızlı yöntem)
        cmd = [
            "robocopy",
            str(src),
            str(dst),
            "/E",         # Boş olanlar dahil tüm alt klasörleri al
            "/COPY:DAT",   # Veri, Öznitelik ve Zaman damgalarını koru
            "/R:2",        # Hata durumunda 2 kez tekrar dene
            "/W:1",        # Tekrarlar arası 1 sn bekle
            "/NFL", "/NDL", # Konsolu boğmamak için dosya/klasör listesini sustur
            "/NP",         # İlerleme yüzdesini sustur
        ]
        # robocopy exit kodları: 0-7 başarı kabul edilir (1=dosyalar kopyalandı)
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode >= 8:
            print(f"[!] Robocopy uyarı kodu: {res.returncode}. Standart Python kopyalamasına geçiliyor.")
            _copy_tree_python(src, dst)
    else:
        _copy_tree_python(src, dst)

    total_files = sum(1 for _ in dst.rglob("*") if _.is_file())
    print(f"[✓] Google Drive aktarımı tamamlandı! Hedefteki toplam dosya sayısı: {total_files}")
    return total_files, 0


def _copy_tree_python(src: Path, dst: Path):
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        target_dir = dst / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            s_file = Path(root) / f
            d_file = target_dir / f
            if not d_file.exists() or d_file.stat().st_size != s_file.stat().st_size:
                shutil.copy2(s_file, d_file)


def update_database_paths(db_path: Path, old_prefix: str, new_prefix: str, dry_run: bool = False) -> dict:
    """uyap_katalog.db içindeki dosya ve PDF yollarını yeni Google Drive konumuna günceller."""
    if not db_path.exists():
        print(f"[!] Veritabanı bulunamadı: {db_path}")
        return {}

    # Yolları normalize et
    old_p1 = str(Path(old_prefix))
    new_p1 = str(Path(new_prefix))

    con = sqlite3.connect(str(db_path), timeout=30)
    cur = con.cursor()

    # Eşleşen kayıt sayıları
    c_evrak = cur.execute(
        "SELECT COUNT(*) FROM evrak WHERE path LIKE ? OR pdf_path LIKE ?",
        (f"{old_p1}%", f"{old_p1}%")
    ).fetchone()[0]

    c_teb = 0
    try:
        c_teb = cur.execute(
            "SELECT COUNT(*) FROM tebligat WHERE path LIKE ? OR pdf_path LIKE ?",
            (f"{old_p1}%", f"{old_p1}%")
        ).fetchone()[0]
    except Exception:
        pass

    print(f"\n[*] Veritabanı Güncelleme Analizi ({db_path.name}):")
    print(f"    - Güncellenecek Evrak Kaydı: {c_evrak} adet")
    print(f"    - Güncellenecek Tebligat Kaydı: {c_teb} adet")
    print(f"    - Eski Yol Ön Eki: {old_p1}")
    print(f"    - Yeni Yol Ön Eki: {new_p1}")

    if dry_run:
        print("[Simülasyon] Veritabanı güncellenmedi (dry-run modu).")
        con.close()
        return {"evrak": c_evrak, "tebligat": c_teb}

    with con:
        # 1. evrak tablosu
        cur.execute("""
            UPDATE evrak
            SET path = REPLACE(path, ?, ?),
                pdf_path = REPLACE(pdf_path, ?, ?),
                cache_path = REPLACE(cache_path, ?, ?)
            WHERE path LIKE ? OR pdf_path LIKE ? OR cache_path LIKE ?
        """, (old_p1, new_p1, old_p1, new_p1, old_p1, new_p1, f"{old_p1}%", f"{old_p1}%", f"{old_p1}%"))

        # 2. tebligat tablosu (varsa)
        try:
            cur.execute("""
                UPDATE tebligat
                SET path = REPLACE(path, ?, ?),
                pdf_path = REPLACE(pdf_path, ?, ?)
                WHERE path LIKE ? OR pdf_path LIKE ?
            """, (old_p1, new_p1, old_p1, new_p1, f"{old_p1}%", f"{old_p1}%"))
        except Exception:
            pass

    con.close()
    print("[✓] Veritabanındaki tüm dosya ve PDF yolları Google Drive konumuna bağlandı!")
    return {"evrak": c_evrak, "tebligat": c_teb}


def backup_database_to_drive(db_path: Path, target_dir: Path, dry_run: bool = False):
    """Veritabanının kilitlenmeyen anlık yedeğini Google Drive'a yazar."""
    if dry_run or not db_path.exists():
        return
    backup_file = target_dir / "uyap_katalog_yedek.db"
    print(f"[*] Veritabanı yedeği Google Drive'a çıkarılıyor: {backup_file.name}")
    try:
        src = sqlite3.connect(str(db_path), timeout=30)
        dst = sqlite3.connect(str(backup_file), timeout=30)
        with dst:
            src.backup(dst, pages=100)
        dst.close()
        src.close()
        print(f"[✓] Veritabanı yedeği Drive'da hazır ({backup_file.stat().st_size / (1024*1024):.1f} MB).")
    except Exception as e:
        print(f"[!] Veritabanı yedekleme uyarısı: {e}")


def update_config_files(new_dir: Path, dry_run: bool = False):
    """Nöbetçi bot ve uygulama ayarlarını günceller."""
    if dry_run:
        return
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            cfg["google_drive_dir"] = str(new_dir)
            CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[✓] Nöbetçi Bot yapılandırması (watcher_config.json) Google Drive'a bağlandı.")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="UYAP Evrak Arşivi -> Google Drive Güvenli Aktarıcı")
    parser.add_argument("--kaynak", type=str, default=None, help="Eski yerel indirme klasörü")
    parser.add_argument("--hedef", type=str, default=None, help="Yeni Google Drive klasörü")
    parser.add_argument("--dry-run", action="store_true", help="Değişiklik yapmadan simüle et")
    parser.add_argument("-y", "--yes", action="store_true", help="Onay istemeden doğrudan aktarımı başlat")
    args = parser.parse_args()

    print("=" * 70)
    print("  UYAP Arşivi -> Google Drive Sıfır Kayıplı Güvenli Aktarım Aracı")
    print("=" * 70)

    src = Path(args.kaynak) if args.kaynak else detect_source_dir()
    dst = Path(args.hedef) if args.hedef else detect_target_drive_dir()

    if not src or not src.exists():
        print(f"[!] Kaynak indirme klasörü bulunamadı: {src}")
        return

    if not dst:
        print("[!] Google Drive klasörü otomatik algılanamadı.")
        print("    Lütfen --hedef parametresiyle belirtin:")
        print("    python drive_aktarici.py --hedef \"G:\\Drive'ım\\UYAP_Arsiv\"")
        return

    print(f"\n[1] Kaynak Klasör (Yerel):  {src}")
    print(f"[2] Hedef Klasör (Drive):   {dst}")
    print(f"[3] Veritabanı:             {DB_PATH}\n")

    if not args.dry_run and not args.yes:
        onay = input("Aktarımı ve veritabanı yol güncellemesini başlatmak istiyor musunuz? [E/h]: ").strip().lower()
        if onay not in ("", "e", "evet", "y", "yes"):
            print("İşlem kullanıcı tarafından iptal edildi.")
            return

    start_time = time.time()

    # 1. Dosyaları yapıyı bozmadan aktar
    copy_files_preserving_structure(src, dst, dry_run=args.dry_run)

    # 2. Veritabanındaki yolları güncelle
    update_database_paths(DB_PATH, str(src), str(dst), dry_run=args.dry_run)

    # 3. Veritabanı yedeğini Drive'a bırak
    backup_database_to_drive(DB_PATH, dst, dry_run=args.dry_run)

    # 4. Yapılandırma dosyalarını tazele
    update_config_files(dst, dry_run=args.dry_run)

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"  [✓] AKTARIM VE EŞİTLEME BAŞARIYLA TAMAMLANDI ({elapsed:.1f} saniye)!")
    print("=" * 70)
    print(f"1. Artık tüm dosyalarınız Google Drive'da: {dst}")
    print("2. Google Drive Masaüstü uygulaması dosyaları arka planda buluta yüklüyor.")
    print("3. Telefonunuzdaki Google Drive uygulamasından veya MacBook'unuzdan anında erişebilirsiniz.")
    print(f"4. Orijinal dosyalarınız güvenlik amacıyla eski konumunda ({src}) aynen durmaktadır.")
    print("   Bulut yüklemesini teyit ettikten sonra dilerseniz eski klasörü silebilirsiniz.\n")


if __name__ == "__main__":
    main()
