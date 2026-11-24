#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UYAP Evrak Yöneticisi & Hukuk Asistanı — Evrensel Başlatıcı & Konsol Arayüzü
© 2026 Av. Can KIZILYAR — Tüm hakları saklıdır.

Kullanım:
  python baslat.py          -> Sade, güçlü Terminal Menüsü (Konsol)
  python baslat.py --gui    -> Modern Grafik Kullanıcı Arayüzü (GUI)
  python baslat.py --cli    -> Doğrudan Terminal Konsolu
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

IS_TERMUX = bool(os.environ.get("PREFIX", "").startswith("/data/data/com.termux"))
PYTHON_EXE = sys.executable or ("python3" if not sys.platform.startswith("win") else "python")


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def run_cmd(cmd_list: list[str]):
    try:
        subprocess.run(cmd_list, cwd=HERE)
    except KeyboardInterrupt:
        print("\n[!] İşlem kullanıcı tarafından durduruldu.")
    except Exception as e:
        print(f"\n[HATA] Komut çalıştırılamadı: {e}")
    try:
        input("\nDevam etmek için Enter'a basın...")
    except (KeyboardInterrupt, EOFError):
        pass


def launch_gui():
    try:
        import katalog_gui
        katalog_gui.main()
    except Exception as e:
        print(f"[!] Grafik arayüz başlatılamadı: {e}")
        print("[*] Terminal modunda devam ediliyor...")
        input("Enter'a basın...")


def print_main_menu():
    clear_screen()
    ortam = "Android / Termux" if IS_TERMUX else ("Windows" if os.name == "nt" else "Linux / macOS")
    headless_durum = "Gizli (Headless - Sessiz)" if os.environ.get("UYAP_HEADLESS", "1") == "1" else "Görünür Tarayıcı"
    print("=" * 70)
    print("       ⚖️  UYAP EVRAK YÖNETİCİSİ & HUKUK ASİSTANI (v3.0.0)")
    print("       © 2026 Av. Can KIZILYAR — Tüm hakları saklıdır.")
    print("=" * 70)
    print(f"  Çalışma Ortamı : {ortam}")
    print(f"  Tarayıcı Modu  : {headless_durum}")
    print("-" * 70)
    print(" [1] ⚡ İŞLEMLERİM İNDİRİCİ (Son 1 Yıl / Özel Tarih Aralığı)")
    print(" [2] 📂 DAVA DOSYALARI (Tüm Evrak ve Ekleri İndir / Tür Filtreli)")
    print(" [3] 🔍 EVRAK KATALOĞU (Tüm Portalı Hızlı Tara & İndeksle)")
    print(" [4] ☁️  DAVA ARŞİVLEME & GOOGLE DRIVE EŞİTLEME (Otonom Senkron)")
    print(" [5] 🔄 UDF / TIFF / ÇOKLU FORMAT -> PDF TOPLU DÖNÜŞTÜRÜCÜ")
    print(" [6] ⏳ TEBLİGAT, SÜRE & DURUŞMA TAKVİMİ (.ics + CSV + Mazbata)")
    print(" [7] ✍️  E-İMZA & OTURUM (ArkSigner Sessiz Giriş / Mobil İmza / İmzala)")
    print(" [8] 🤖 UYAP NÖBETÇİ BOT (7/24 Arka Planda İzleme & Keep-Alive)")
    print(" [9] ⚙️  AYARLAR & TARAYICI MODU (Gizli / Görünür / İndirme Klasörü)")
    print()
    print(" [G] 🖥️  GRAFİK KULLANICI ARAYÜZÜ (Modern GUI Aç)")
    print(" [0] 🚪 Çıkış")
    print("=" * 70)


def menu_islemlerim():
    print("\n--- ⚡ İŞLEMLERİM İNDİRİCİ ---")
    print("  1) Son 1 Yıl — Hızlı Tek Tıkla İndir [Önerilen]")
    print("  2) Özel Tarih Aralığı Belirle (Geçmiş Yıllar)")
    print("  0) Ana Menüye Dön")
    sub = input("\nSeçiminiz (0-2) [Varsayılan: 1]: ").strip() or "1"
    if sub == "1":
        print("\n[*] İşlemlerim - Son 1 Yıl taranıyor ve indiriliyor...")
        run_cmd([PYTHON_EXE, "uyap_indirici.py", "--cli", "--mode", "islemlerim"])
    elif sub == "2":
        start_d = input("Başlangıç Tarihi (GG.AA.YYYY) [Örn: 01.01.2023]: ").strip()
        end_d = input("Bitiş Tarihi     (GG.AA.YYYY) [Örn: 24.11.2026]: ").strip()
        cmd = [PYTHON_EXE, "uyap_indirici.py", "--cli", "--mode", "islemlerim"]
        if start_d:
            cmd.extend(["--start-date", start_d])
        if end_d:
            cmd.extend(["--end-date", end_d])
        run_cmd(cmd)


def menu_dava_dosyalari():
    print("\n--- 📂 DAVA DOSYALARINDAN İNDİRME ---")
    print("  1) TÜM Evrakları ve EKLERİ İndir (Eksiksiz Arşiv) [Önerilen]")
    print("  2) Yalnızca Duruşma Zabıtları")
    print("  3) Bilirkişi Raporları")
    print("  4) Gerekçeli Karar ve İlamlar")
    print("  5) Tensip Zabıtları")
    print("  6) Dava ve Cevap Layihaları (Dilekçeler, Beyanlar)")
    print("  7) Müzekkere ve Kurum Cevapları")
    print("  8) Tebligat ve Mazbatalar")
    print("  9) Özel Kelime / Tür Arama")
    print("  0) Ana Menüye Dön")
    sub = input("\nSeçiminiz (0-9) [Varsayılan: 1]: ").strip() or "1"
    if sub == "0":
        return

    tur_map = {
        "1": "tumu", "2": "durusma", "3": "bilirkisi", "4": "karar",
        "5": "tensip", "6": "layihalar", "7": "muzekkere", "8": "tebligat"
    }
    tur = tur_map.get(sub, "tumu")
    if sub == "9":
        tur = input("Aranacak evrak türü / kelime: ").strip() or "tumu"

    print("\n  Dosya Kapsamı:")
    print("  1) Tüm Dosyalar (Açık + Kapalı / 700+ Dosya) [Varsayılan]")
    print("  2) Yalnızca Açık / Derdest Dosyalar")
    print("  3) Sık Kullanılan Dosyalar")
    k_sec = input("Kapsam (1-3) [Varsayılan: 1]: ").strip() or "1"
    scope = "acik" if k_sec == "2" else ("fav" if k_sec == "3" else "all")

    kw = input("Mahkeme veya Esas No Filtresi (Tümü için boş geçin): ").strip()
    cmd = [PYTHON_EXE, "uyap_indirici.py", "--cli", "--mode", "dosyalar", "--evrak-turu", tur, "--scope", scope]
    if sub == "1":
        cmd.append("--include-attachments")
    if kw:
        cmd.extend(["--filter-birim", kw])
    run_cmd(cmd)


def menu_katalog():
    print("\n--- 🔍 EVRAK KATALOĞU ---")
    print("  1) Portaldan Tüm Evrak Listesini Tara & İndeksle (İndirme Yapmaz) [Hızlı]")
    print("  2) Görsel Katalog Arayüzünü Aç (Filtrele, Seç ve İndir)")
    print("  0) Ana Menüye Dön")
    sub = input("\nSeçiminiz (0-2) [Varsayılan: 1]: ").strip() or "1"
    if sub == "1":
        print("\n[*] UYAP Portaldaki dava dosyaları taranıyor ve yerel kataloğa kaydediliyor...")
        run_cmd([PYTHON_EXE, "uyap_indirici.py", "--katalog-tara"])
    elif sub == "2":
        launch_gui()


def menu_arsiv_ve_drive():
    print("\n--- ☁️ DAVA ARŞİVLEME & GOOGLE DRIVE EŞİTLEME ---")
    print("  1) Google Drive Akıllı Kademeli Eşitleyiciyi Başlat [Otonom]")
    print("  2) Google Drive Arşiv Denetimi ve Eksik Raporu (CSV / JSON)")
    print("  3) Yerel Dava Dosyalarını Arşivle ve Vektörel PDF Üret")
    print("  0) Ana Menüye Dön")
    sub = input("\nSeçiminiz (0-3) [Varsayılan: 1]: ").strip() or "1"
    if sub == "1":
        print("\n[*] Google Drive Akıllı Eşitleyici başlatılıyor...")
        run_cmd([PYTHON_EXE, "drive_arsiv_esitle.py"])
    elif sub == "2":
        print("\n[*] Google Drive UYAP Arşiv Denetimi çalıştırılıyor...")
        run_cmd([PYTHON_EXE, "drive_arsiv_denetle.py"])
    elif sub == "3":
        kw = input("Arşivlenecek Mahkeme / Esas No (Tümü için boş geçin): ").strip()
        cmd = [PYTHON_EXE, "dosya_arsivle.py"]
        if kw:
            cmd.extend(["--birim", kw])
        run_cmd(cmd)


def menu_donusturucu():
    print("\n--- 🔄 UDF / TIFF -> PDF TOPLU DÖNÜŞTÜRÜCÜ ---")
    print("  1) UYAP İndirilenler Klasöründeki Tüm UDF'leri PDF'e Dönüştür [Önerilen]")
    print("  2) Belirli Bir Klasör Seç ve Dönüştür")
    print("  0) Ana Menüye Dön")
    sub = input("\nSeçiminiz (0-2) [Varsayılan: 1]: ").strip() or "1"
    if sub == "1":
        run_cmd([PYTHON_EXE, "donusturucu.py"])
    elif sub == "2":
        target = input("Dönüştürülecek klasör yolu: ").strip()
        if target:
            run_cmd([PYTHON_EXE, "donusturucu.py", "--dir", target])


def menu_tebligat_ve_sure():
    print("\n--- ⏳ TEBLİGAT, YASAL SÜRE & DURUŞMA TAKVİMİ ---")
    print("  1) Duruşma Takvimi Oluştur (.ics / Google & Outlook Takvim + CSV) [Önerilen]")
    print("  2) Tebligat ve Mazbata Süre Analizi (PTT Mazbata + UETS)")
    print("  3) Hukuki Süre, Ara Karar ve Görev Analizi (Kesin Süreler)")
    print("  4) Evrak Zenginleştirme ve Akıllı Dosya İsimlendirme")
    print("  0) Ana Menüye Dön")
    sub = input("\nSeçiminiz (0-4) [Varsayılan: 1]: ").strip() or "1"
    if sub == "1":
        run_cmd([PYTHON_EXE, "uyap_indirici.py", "--cli", "--mode", "durusmalar"])
    elif sub == "2":
        run_cmd([PYTHON_EXE, "tebligat_yoneticisi.py"])
    elif sub == "3":
        run_cmd([PYTHON_EXE, "uyap_sure_analiz.py"])
    elif sub == "4":
        run_cmd([PYTHON_EXE, "enrich_and_rename_documents.py"])


def menu_imza_ve_oturum():
    print("\n--- ✍️ E-İMZA & UYAP OTURUM YÖNETİMİ ---")
    print("  1) Aktif UYAP Oturum Durumunu Doğrula [Port 9223]")
    print("  2) e-İmza ile Otomatik Giriş Yap (ArkSigner / Sessiz)")
    print("  3) Mobil İmza ile Giriş Yap (Telefona Onay Gönder)")
    print("  4) UDF Belgesini E-İmza ile İmzala (CAdES-BES)")
    print("  5) Chrome / Edge UYAP Oturumu Başlat (Görünür Tarayıcı)")
    print("  0) Ana Menüye Dön")
    sub = input("\nSeçiminiz (0-5) [Varsayılan: 1]: ").strip() or "1"
    if sub == "1":
        run_cmd([PYTHON_EXE, "uyap_indirici.py", "--check-login"])
    elif sub == "2":
        run_cmd([PYTHON_EXE, "uyap_indirici.py", "--relogin"])
    elif sub == "3":
        run_cmd([PYTHON_EXE, "uyap_indirici.py", "--cli", "--mode", "login", "--mobil-imza"])
    elif sub == "4":
        udf_path = input("İmzalanacak UDF dosyasının yolu: ").strip()
        if udf_path:
            run_cmd([PYTHON_EXE, "uyap_imzala.py", udf_path])
        else:
            run_cmd([PYTHON_EXE, "uyap_imzala.py", "--help"])
    elif sub == "5":
        run_cmd([PYTHON_EXE, "uyap_indirici.py", "--browser-only"])


def menu_nobetci_bot():
    print("\n--- 🤖 UYAP NÖBETÇİ BOT (7/24 Kesintisiz Arka Plan İzleme) ---")
    print("  1) Sürekli Nöbetçi Modunda Başlat (15 Dakikada Bir Otomatik Denetle)")
    print("  2) Tek Seferlik Hızlı Tarama Yap ve Çık (--once)")
    print("  0) Ana Menüye Dön")
    sub = input("\nSeçiminiz (0-2) [Varsayılan: 1]: ").strip() or "1"
    if sub == "1":
        intv = input("Kontrol Sıklığı (Dakika) [Varsayılan: 15]: ").strip() or "15"
        run_cmd([PYTHON_EXE, "uyap_watcher.py", "--interval", intv])
    elif sub == "2":
        run_cmd([PYTHON_EXE, "uyap_watcher.py", "--once"])


def menu_ayarlar():
    print("\n--- ⚙️ AYARLAR & ENTEGRASYONLAR ---")
    cur_headless = os.environ.get("UYAP_HEADLESS", "1")
    yeni_durum = "Görünür Pencereli" if cur_headless == "1" else "Gizli Arka Plan (Headless)"
    print(f"  1) Tarayıcı Modunu Değiştir (Şu anki: {'Gizli' if cur_headless == '1' else 'Görünür'} -> Yap: {yeni_durum})")
    print("  2) Notion & TickTick Entegrasyon Paketlerini Üret (CSV + ICS)")
    print("  3) Sistem Kontrolü ve Sağlık Denetimi")
    print("  0) Ana Menüye Dön")
    sub = input("\nSeçiminiz (0-3) [Varsayılan: 1]: ").strip() or "1"
    if sub == "1":
        if cur_headless == "1":
            os.environ["UYAP_HEADLESS"] = "0"
            print("\n[✓] Tarayıcı modu 'GÖRÜNÜR PENCERELİ' olarak ayarlandı.")
        else:
            os.environ["UYAP_HEADLESS"] = "1"
            print("\n[✓] Tarayıcı modu 'GİZLİ ARKA PLAN (HEADLESS)' olarak ayarlandı.")
        input("Devam etmek için Enter'a basın...")
    elif sub == "2":
        run_cmd([PYTHON_EXE, "uyap_entegrasyon.py"])
    elif sub == "3":
        run_cmd([PYTHON_EXE, "sistem_kontrol_ve_tam_kurulum.bat" if os.name == "nt" else "termux_kurulum.sh"])


def main():
    # Komut satırı argümanları verilmişse doğrudan yönlendir
    args = sys.argv[1:]
    if args:
        if args[0] in ("--gui", "-g", "--katalog"):
            launch_gui()
            return
        elif args[0] in ("--cli", "-c", "--terminal"):
            pass  # Aşağıdaki interaktif menüye devam et
        else:
            # Belirli bir komut verilmişse doğrudan uygulama.py veya uyap_indirici'ye yönlendir
            import uygulama
            uygulama.main()
            return

    while True:
        print_main_menu()
        try:
            secim = input("Seçiminiz (0-9, G) [Varsayılan: 1]: ").strip().upper()
        except (KeyboardInterrupt, EOFError):
            print("\nÇıkış yapıldı.")
            break

        if not secim:
            secim = "1"

        if secim == "0":
            print("\nİyi çalışmalar dileriz.")
            break
        elif secim in ("G", "GUI"):
            launch_gui()
        elif secim == "1":
            menu_islemlerim()
        elif secim == "2":
            menu_dava_dosyalari()
        elif secim == "3":
            menu_katalog()
        elif secim == "4":
            menu_arsiv_ve_drive()
        elif secim == "5":
            menu_donusturucu()
        elif secim == "6":
            menu_tebligat_ve_sure()
        elif secim == "7":
            menu_imza_ve_oturum()
        elif secim == "8":
            menu_nobetci_bot()
        elif secim == "9":
            menu_ayarlar()
        else:
            print("[!] Geçersiz seçim!")
            try:
                input("Tekrar denemek için Enter'a basın...")
            except (KeyboardInterrupt, EOFError):
                break


if __name__ == "__main__":
    main()
