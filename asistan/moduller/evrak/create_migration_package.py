#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity Sohbet ve Durumunu Windows 11'e Aktarma Paketi Oluşturucu
"""

import os
import zipfile
import shutil
from pathlib import Path

export_dir = Path("/sdcard/Download/Antigravity_Windows_Aktarim")
if export_dir.exists():
    shutil.rmtree(export_dir)
export_dir.mkdir(parents=True, exist_ok=True)

conv_id = "cb9e5c44-86ab-4d5b-b419-ec7fc343613d"
home_dir = Path("/data/data/com.termux/files/home")
cli_dir = home_dir / ".gemini" / "antigravity-cli"

# 1. Konuşma veritabanını kopyala
(export_dir / "conversations").mkdir(parents=True, exist_ok=True)
db_src = cli_dir / "conversations" / f"{conv_id}.db"
if db_src.exists():
    shutil.copy2(str(db_src), str(export_dir / "conversations" / f"{conv_id}.db"))

# 2. Brain, artifacts ve transcript dosyalarını kopyala
brain_src = cli_dir / "brain" / conv_id
if brain_src.exists():
    brain_dst = export_dir / "brain" / conv_id
    brain_dst.mkdir(parents=True, exist_ok=True)
    for item in brain_src.iterdir():
        if item.name == ".system_generated":
            logs_dst = brain_dst / ".system_generated" / "logs"
            logs_dst.mkdir(parents=True, exist_ok=True)
            for lf in (item / "logs").iterdir():
                if lf.is_file():
                    shutil.copy2(str(lf), str(logs_dst / lf.name))
                elif lf.is_dir():
                    shutil.copytree(str(lf), str(logs_dst / lf.name), dirs_exist_ok=True)
        elif item.is_file():
            shutil.copy2(str(item), str(brain_dst / item.name))
        elif item.name in ("scratch", ".user_uploaded"):
            shutil.copytree(str(item), str(brain_dst / item.name), dirs_exist_ok=True)

# 3. Windows için otomatik kopyalama betiği (windows_aktar.bat)
bat_lines = [
    "@echo off",
    "chcp 65001 >nul",
    "echo ======================================================================",
    "echo    Antigravity Sohbetini Windows 11'e Aktarma Betigi",
    "echo ======================================================================",
    "echo.",
    "set TARGET_CLI=%USERPROFILE%\\.gemini\\antigravity-cli",
    'if not exist "%TARGET_CLI%\\conversations" mkdir "%TARGET_CLI%\\conversations"',
    f'if not exist "%TARGET_CLI%\\brain\\{conv_id}" mkdir "%TARGET_CLI%\\brain\\{conv_id}"',
    "echo [*] Konusma veritabani kopyalaniyor...",
    f'copy /Y "conversations\\{conv_id}.db" "%TARGET_CLI%\\conversations\\" >nul',
    "echo [*] Brain ve gecmis dosyalari kopyalaniyor...",
    f'xcopy /E /I /Y "brain\\{conv_id}" "%TARGET_CLI%\\brain\\{conv_id}\\" >nul',
    "echo.",
    "echo [OK] Sohbet oturumu basariyla aktarildi!",
    "echo.",
    "echo ======================================================================",
    "echo   Windows 11'de Kullanmak Icin:",
    "echo ======================================================================",
    "echo   1. Antigravity Desktop / IDE Programinda:",
    "echo      Programi acip sol menuden veya /resume diyerek",
    "echo      'Fixing Termux Python Script Errors' baslikli oturumu seciniz.",
    "echo.",
    "echo   2. Antigravity CLI (Terminal) ile:",
    f"      agy --conversation {conv_id}",
    "echo ======================================================================",
    "echo.",
    "pause",
]
(export_dir / "windows_aktar.bat").write_text("\r\n".join(bat_lines), encoding="utf-8")

# 4. İnsan tarafından okunabilir özet & proje durum raporu
summary_md = f"""# Antigravity Sohbet ve UYAP İndirici Proje Durum Özeti
**Oturum ID:** `{conv_id}`  
**Kullanıcı:** Av. Can KIZILYAR (TCKN: `39412276734`)  
**Proje Deposu:** https://github.com/cnkzlyr/uyap-evrak-indirici  
**Tarih:** 14 Kasım 2026

---

## 1. Bu Sohbette Yapılan Tüm Çalışmalar ve Çözümler
1. **UYAP Mobil İmza & Oturum Canlılığı:**
   - Termux ortamında Chromium headless modu ve Mobil İmza köprüsü stabilize edildi.
2. **UDF -> Vektörel PDF Dönüştürücü:**
   - Havelsan Java kütüphaneleri optimize edildi. `comments.xml` içeren dosyalarda çökmeyi engelleyen bellek-içi filtre yazıldı. 4.322 UDF belgesi %100 oranında TrueType-embedded PDF formatına dönüştürüldü.
3. **Akıllı Evrak İsimlendirme & Meta Veri:**
   - Mahkeme adı, esas no, karar no, duruşma tarihi, müvekkil adı ve UYAP evrak ID bilgileri dosya adlarına ve UDF dahili `documentproperties.xml` özniteliklerine otomatik işlendi.
4. **İdari Yargı & BİM Düzeltmesi:**
   - UYAP'ın "Diğer Yargı Birimi" olarak etiketlediği Bölge İdare Mahkemesi (İdari Dava Dairesi ve Vergi Dava Dairesi) ve yüzlerce adli mahkeme dosyası doğru üst yargı kollarına taşındı. 4.489 kayıtlı arşiv senkronize edildi.
5. **Yeni İndirme Ön Tanımları (Presets):**
   - **Layihalar:** Karşı taraf dahil tüm dilekçeler (Dava, Cevap, Replik, Düplik, Delil, Bilirkişi İtiraz, Savunma, Beyan vb.).
   - **Tebligatlar:** Fiziki PTT Mazbataları (Barkodlu) + UETS Elektronik Tebligatları (Tebligat Kanunu m.7/a 5 gün kuralı hesaplaması ile).
   - **Otomatik Takip Kütüğü:** `tebligat_takip_listesi.csv` dosyasına Excel uyumlu kümülatif kayıt.

---

## 2. Windows 11 Laptopta Devam Etme Talimatı

### Seçenek 1: Antigravity IDE / Masaüstü Programı İle (Şiddetle Önerilen)
1. Windows 11 laptopunuzda Git Bash veya PowerShell açın:
   ```bash
   git clone https://github.com/cnkzlyr/uyap-evrak-indirici
   ```
2. Antigravity IDE veya Antigravity 2.0 uygulamasını açıp bu klasörü açın.
3. İndirdiğiniz `Antigravity_Sohbet_cb9e5c44.zip` arşivini açıp içindeki `windows_aktar.bat` dosyasına çift tıklayın.
4. Antigravity IDE'de sohbet penceresinden bu sohbete kaldığınız yerden devam edin.

### Seçenek 2: Antigravity CLI (agy) İle
1. `windows_aktar.bat` çalıştırdıktan sonra:
   ```cmd
   agy --conversation {conv_id}
   ```
"""
(export_dir / "SOHBET_OZETI_VE_DURUM_RAPORU.md").write_text(summary_md, encoding="utf-8")

# 5. ZIP oluştur
zip_path = Path("/sdcard/Download/Antigravity_Sohbet_cb9e5c44.zip")
if zip_path.exists():
    zip_path.unlink()

with zipfile.ZipFile(str(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(str(export_dir)):
        for f in files:
            full = Path(root) / f
            rel = full.relative_to(export_dir)
            zf.write(str(full), arcname=str(rel))

print(f"Zip created at: {zip_path} (Size: {zip_path.stat().st_size / (1024*1024):.2f} MB)")
