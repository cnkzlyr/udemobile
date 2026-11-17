#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UYAP Evrak İndirici & Antigravity Windows 11 Tam Aktarım Paketi Oluşturucu
Samsung / Google Quick Share için optimize edilmiştir.
"""

import os
import sys
import time
import zipfile
import shutil
from pathlib import Path

def main():
    start_time = time.time()
    conv_id = "cb9e5c44-86ab-4d5b-b419-ec7fc343613d"
    home_dir = Path("/data/data/com.termux/files/home")
    cli_dir = home_dir / ".gemini" / "antigravity-cli"
    uyap_project_dir = home_dir / "uyap-evrak-indirici"
    jars_dir = home_dir / "jars"
    uyap_indirilenler_dir = Path("/sdcard/Download/UYAP_Indirilenler")
    out_zip = Path("/sdcard/Download/UYAP_TAM_PAKET_WINDOWS.zip")

    print("==================================================================")
    print("    UYAP & Antigravity Windows 11 Tam Paket Oluşturucu")
    print("==================================================================")

    if out_zip.exists():
        print(f"[*] Eski paket siliniyor: {out_zip}")
        out_zip.unlink()

    bat_content = """@echo off
chcp 65001 >nul
title Antigravity AI & UYAP Windows 11 Tam Kurulum
color 0A

echo ======================================================================
echo    Antigravity AI ve UYAP Evrak Indirici - Windows 11 Otomatik Kurulum
echo ======================================================================
echo.

set CONV_ID=cb9e5c44-86ab-4d5b-b419-ec7fc343613d
set TARGET_CLI_DIR=%USERPROFILE%\\.gemini\\antigravity-cli
set TARGET_CONV_DIR=%TARGET_CLI_DIR%\\conversations
set TARGET_BRAIN_DIR=%TARGET_CLI_DIR%\\brain\\%CONV_ID%

echo [*] Antigravity hedef dizinleri kontrol ediliyor...
if not exist "%TARGET_CONV_DIR%" mkdir "%TARGET_CONV_DIR%"
if not exist "%TARGET_BRAIN_DIR%" mkdir "%TARGET_BRAIN_DIR%"

echo [*] Antigravity Konusma Veritabani kopyalaniyor...
if exist "Antigravity_Aktarim\\conversations\\%CONV_ID%.db" (
    copy /Y "Antigravity_Aktarim\\conversations\\%CONV_ID%.db" "%TARGET_CONV_DIR%\\" >nul
    echo [✓] Konusma veritabani yuklendi.
) else (
    echo [!] Antigravity_Aktarim\\conversations klasoru bulunamadi!
)

echo [*] Antigravity Brain, Artifacts ve Loglar kopyalaniyor...
if exist "Antigravity_Aktarim\\brain\\%CONV_ID%" (
    xcopy /E /I /Y "Antigravity_Aktarim\\brain\\%CONV_ID%" "%TARGET_BRAIN_DIR%" >nul
    echo [✓] Sohbet beyni ve calisma dosyalari yuklendi.
) else (
    echo [!] Antigravity_Aktarim\\brain klasoru bulunamadi!
)

echo.
echo [*] Masaustune UYAP kisayollari olusturuluyor...
set SCRIPT_DIR=%~dp0
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\\UYAP Indirilen Evraklar.lnk'); $s.TargetPath = '%SCRIPT_DIR%UYAP_Indirilenler'; $s.Description = 'Indirilen UYAP Evraklari ve Klasorleri'; $s.Save()" >nul 2>&1
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\\UYAP Evrak Indirici.lnk'); $s.TargetPath = '%SCRIPT_DIR%uyap-evrak-indirici\\baslat_windows.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%uyap-evrak-indirici'; $s.Description = 'UYAP Evrak Indirici Windows Baslatici'; $s.Save()" >nul 2>&1
echo [✓] Masaustune 'UYAP Indirilen Evraklar' ve 'UYAP Evrak Indirici' kisayollari eklendi!

echo.
echo [*] Python ve Gerekli Paketlerin Durumu Kontrol Ediliyor...
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [✓] Python tespit edildi.
    echo [*] Gerekli Python kutuphaneleri yukleniyor...
    python -m pip install playwright requests pydantic --quiet
) else (
    echo [!] Python bulunamadi. UYAP indiriciyi Windows'ta calistirmak icin python.org adresinden Python 3.10+ kurabilirsiniz.
)

echo.
echo ======================================================================
echo    [✓] Windows 11 AKTARIMI BASARIYLA TAMAMLANDI!
echo ======================================================================
echo.
echo   1. Antigravity Desktop (IDE) ile Acis:
echo      - Antigravity IDE uygulamasini acin.
echo      - 'cb9e5c44-86ab-4d5b-b419-ec7fc343613d' oturumuna kaldiginiz yerden devam edin.
echo.
echo   2. Antigravity CLI (Komut Satiri) ile Acis:
echo      - PowerShell veya Windows Terminal acin:
echo        agy --conversation cb9e5c44-86ab-4d5b-b419-ec7fc343613d
echo.
echo   3. UYAP Evrak Indiriciyi Windows'ta Calistirmak Icin:
echo      - Masaustundeki 'UYAP Evrak Indirici' kisayoluna cift tiklayin.
echo.
echo   4. Indirilen Evraklara Erisim:
echo      - Masaustundeki 'UYAP Indirilen Evraklar' kisayolundan 4.400+ evraka
echo        ve Excel/CSV kutuklerine erisebilirsiniz.
echo ======================================================================
echo.
pause
"""

    guide_md = f"""# UYAP & Antigravity Windows 11 Tam Aktarım ve Kullanım Kılavuzu

**Kullanıcı:** Av. Can KIZILYAR (TCKN: `39412276734`)  
**Tarih:** 14 Kasım 2026  
**Oturum ID:** `{conv_id}`  
**GitHub Deposu:** https://github.com/cnkzlyr/uyap-evrak-indirici  

---

## 🚀 1. Quick Share ile Windows 11'e Gönderme (15-20 Saniye)
1. Telefonunuzda **Samsung Dosyalarım (My Files)** uygulamasını açın.
2. **Dahili Depolama -> Download (İndirilenler)** klasörüne girin.
3. **`UYAP_TAM_PAKET_WINDOWS.zip`** dosyasına basılı tutun ve **Paylaş (Share)** butonuna basın.
4. **Quick Share** simgesine dokunun ve laptopunuzu (Windows 11 PC) seçin.
5. Laptop ekranınızda beliren bildirimi **Kabul Et (Accept)** deyin.
   *(Dosya saniyeler içinde laptopunuzun `İndirilenler` klasörüne inecektir).*

---

## 💻 2. Windows 11'de Kurulum (Tek Tıkla)
1. Windows 11 laptopunuzda `İndirilenler` klasöründeki **`UYAP_TAM_PAKET_WINDOWS.zip`** dosyasına sağ tıklayın ve **"Tümünü Ayıkla" (Extract All)** deyin (Örn: `C:\\UYAP_ve_Antigravity` veya İndirilenler klasörüne).
2. Ayıklanan klasörün içindeki **`windows_tam_kurulum.bat`** dosyasına çift tıklayın.
3. Bu betik otomatik olarak:
   - Antigravity sohbet geçmişini, yapay zeka beynini ve tüm logları Windows sistem dizinine yerleştirir.
   - Masaüstünüze **"UYAP İndirilen Evraklar"** kısayolunu ekler (tek tıkla 4.400+ evraka erişirsiniz).
   - Masaüstünüze **"UYAP Evrak İndirici"** kısayolunu ekler.

---

## ⚖️ 3. Antigravity Desktop (IDE) mi, CLI mi?
| Özellik | Antigravity IDE (Desktop Programı) ⭐ Önerilen | Antigravity CLI (`agy`) |
| :--- | :--- | :--- |
| **Görsel Arayüz** | Dosya ağacı, kod editörü, sohbet ve terminal yan yana | Sadece metin tabanlı siyah konsol |
| **Evrak & Rapor İnceleme** | PDF, görsel, markdown ve CSV tablolarını doğrudan açıp gösterir | Dosyaları harici programla açmak gerekir |
| **Kullanım Kolaylığı** | Çok daha konforlu, pencereli ve modern bir hukuk bürosu deneyimi | Hızlı ve hafif, sadece komut satırı sevenler için |
| **Sohbet Geçmişi** | Sol menüde listelenir, tıklandığında hemen açılır | `agy --conversation ...` komutuyla açılır |

**Tavsiyemiz:** Antigravity Desktop (IDE) programını kullanmanızdır. Böylece indirilen evrakları, CSV kütüklerini ve yapay zeka sohbetini tek pencerede kolayca takip edebilirsiniz.

---

## 📥 4. Windows 11'de UYAP İndiriciyi Çalıştırma
Masaüstündeki **"UYAP Evrak İndirici"** kısayoluna çift tıkladığınızda interaktif menü açılır:
1. **İşlemlerim İndirici** (Son 1 Yıl / Özel Tarih)
2. **Duruşma Zabıtları İndirici** (Tüm dosyalar)
3. **Gerekçeli Kararlar ve BAM/Yargıtay İlamları**
4. **Tüm Dilekçeler ve Layihalar** (Dava, Cevap, İtiraz, Beyan)
5. **Tebligatlar ve Mazbatalar** (Fiziki PTT + UETS TK m.7/a 5 gün kuralı ile)
6. **Toplu UDF -> Vektörel PDF Dönüştürücü** (Windows Fonts desteğiyle)
"""

    guide_html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>UYAP & Antigravity Windows 11 Aktarım Kılavuzu</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px auto; max-width: 850px; line-height: 1.6; color: #222; background: #f8fafc; }}
  .card {{ background: white; border-radius: 12px; padding: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); }}
  h1 {{ color: #1e3a8a; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; }}
  h2 {{ color: #1e40af; margin-top: 25px; }}
  .badge {{ background: #dbeafe; color: #1e40af; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 0.9em; }}
  table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 12px; text-align: left; }}
  th {{ background: #f1f5f9; }}
  .btn {{ display: inline-block; background: #2563eb; color: white; padding: 10px 18px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 10px; }}
  code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-family: Consolas, monospace; color: #0f172a; }}
</style>
</head>
<body>
<div class="card">
  <h1>⚖️ UYAP & Antigravity Windows 11 Tam Aktarım Kılavuzu</h1>
  <p><span class="badge">Av. Can KIZILYAR</span> <span class="badge">Oturum: {conv_id}</span></p>

  <h2>🚀 Adım 1: Quick Share ile Laptopa Gönderme</h2>
  <ol>
    <li>Samsung <strong>Dosyalarım</strong> uygulamasından <code>Download</code> klasörüne girin.</li>
    <li><strong><code>UYAP_TAM_PAKET_WINDOWS.zip</code></strong> dosyasına basılı tutup <strong>Paylaş -&gt; Quick Share</strong> seçin.</li>
    <li>Windows 11 laptopunuza dokunun ve laptopta <strong>Kabul Et</strong> deyin (15-20 saniyede aktarılır).</li>
  </ol>

  <h2>💻 Adım 2: Windows 11'de Kurulum (Tek Tıkla)</h2>
  <ol>
    <li>Laptopunuzda indirilen zip dosyasına sağ tıklayıp <strong>Tümünü Ayıkla</strong> deyin.</li>
    <li>Klasör içindeki <strong><code>windows_tam_kurulum.bat</code></strong> dosyasına çift tıklayın.</li>
    <li>Masaüstünüze <strong>UYAP İndirilen Evraklar</strong> ve <strong>UYAP Evrak İndirici</strong> kısayolları otomatik eklenir.</li>
  </ol>

  <h2>⭐ Antigravity IDE (Masaüstü) vs CLI</h2>
  <table>
    <tr><th>Özellik</th><th>Antigravity Desktop (IDE) ⭐ Tavsiye Edilen</th><th>Antigravity CLI (agy)</th></tr>
    <tr><td>Arayüz</td><td>Görsel panel, dosya ağacı, sekmeler ve sohbet yan yana</td><td>Siyah komut satırı</td></tr>
    <tr><td>Evrak &amp; CSV İnceleme</td><td>PDF, görsel, markdown ve tabloları anında gösterir</td><td>Harici program gerektirir</td></tr>
    <tr><td>Avukatlık İş Akışı</td><td>Modern, konforlu çalışma masası</td><td>Konsol script çalıştırıcı</td></tr>
  </table>

  <h2>📂 Paket İçeriği</h2>
  <ul>
    <li><strong>UYAP_Indirilenler/:</strong> 4.489 adet düzenlenmiş, mahkemelere göre ayrılmış UDF ve PDF evrakları + CSV kütükleri.</li>
    <li><strong>Antigravity_Aktarim/:</strong> Bu sohbetin SQLite veritabanı, logları ve hafızası.</li>
    <li><strong>uyap-evrak-indirici/:</strong> Güncel kaynak kodlar, <code>indirme_gecmisi.json</code>, Havelsan Java kütüphaneleri ve Windows başlatıcıları.</li>
  </ul>
</div>
</body>
</html>
"""

    print("[*] ZIP arşivi oluşturuluyor (Hızlı sıkıştırma modu)...")
    # compresslevel=1 ensures very fast compression of 900MB without hogging phone CPU
    with zipfile.ZipFile(str(out_zip), "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        
        # 1. windows_tam_kurulum.bat
        zf.writestr("windows_tam_kurulum.bat", bat_content.replace("\n", "\r\n"))
        # 2. Rehber dosyaları
        zf.writestr("AKTARIM_KILAVUZU.md", guide_md.replace("\n", "\r\n"))
        zf.writestr("AKTARIM_KILAVUZU.html", guide_html)

        # 3. Antigravity SQLite DB
        db_file = cli_dir / "conversations" / f"{conv_id}.db"
        if db_file.exists():
            print(f"  [+] Ekleniyor: Antigravity DB ({db_file.stat().st_size / (1024*1024):.1f} MB)")
            zf.write(str(db_file), arcname=f"Antigravity_Aktarim/conversations/{conv_id}.db")

        # 4. Antigravity Brain, Artifacts, Logs
        brain_dir = cli_dir / "brain" / conv_id
        if brain_dir.exists():
            print("  [+] Ekleniyor: Antigravity Brain ve Artifacts...")
            for root, dirs, files in os.walk(str(brain_dir)):
                for f in files:
                    full_p = Path(root) / f
                    rel_p = full_p.relative_to(brain_dir)
                    zf.write(str(full_p), arcname=f"Antigravity_Aktarim/brain/{conv_id}/{rel_p}")

        # 5. uyap-evrak-indirici kaynak kodları, cache ve indirme_gecmisi.json
        print("  [+] Ekleniyor: uyap-evrak-indirici kaynak kodları ve indirme_gecmisi.json...")
        for item in uyap_project_dir.iterdir():
            if item.name in (".git", ".uyap_chrome_profile", "__pycache__", "UYAP_Indirilenler"):
                continue
            if item.is_file():
                zf.write(str(item), arcname=f"uyap-evrak-indirici/{item.name}")
            elif item.is_dir():
                for root, dirs, files in os.walk(str(item)):
                    for f in files:
                        full_p = Path(root) / f
                        rel_p = full_p.relative_to(uyap_project_dir)
                        zf.write(str(full_p), arcname=f"uyap-evrak-indirici/{rel_p}")

        # 6. Havelsan JARS (Java UDF -> PDF dönüştürücü kütüphaneleri)
        if jars_dir.exists():
            print("  [+] Ekleniyor: Havelsan Java Jars (UDF/PDF motoru)...")
            for root, dirs, files in os.walk(str(jars_dir)):
                for f in files:
                    full_p = Path(root) / f
                    rel_p = full_p.relative_to(jars_dir)
                    zf.write(str(full_p), arcname=f"uyap-evrak-indirici/jars/{rel_p}")

        # 7. UYAP_Indirilenler (Tüm mahkeme klasörleri, evraklar ve CSV'ler)
        if uyap_indirilenler_dir.exists():
            print("  [+] Ekleniyor: UYAP_Indirilenler arşivi (4.489 evrak)...")
            file_count = 0
            for root, dirs, files in os.walk(str(uyap_indirilenler_dir)):
                for f in files:
                    full_p = Path(root) / f
                    rel_p = full_p.relative_to(uyap_indirilenler_dir)
                    zf.write(str(full_p), arcname=f"UYAP_Indirilenler/{rel_p}")
                    file_count += 1
                    if file_count % 1000 == 0:
                        print(f"    --> {file_count} evrak arşivlendi...")
            print(f"  [✓] Toplam {file_count} evrak başarıyla arşive eklendi.")

    duration = time.time() - start_time
    zip_size_mb = out_zip.stat().st_size / (1024 * 1024)
    print("==================================================================")
    print(f"[✓] Paketleme Tamamlandı!")
    print(f"[*] Dosya Yolu: {out_zip}")
    print(f"[*] Dosya Boyutu: {zip_size_mb:.2f} MB")
    print(f"[*] Geçen Süre: {duration:.1f} saniye")
    print("==================================================================")

if __name__ == "__main__":
    main()
