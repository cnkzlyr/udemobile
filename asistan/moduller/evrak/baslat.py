#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UYAP Avukat Portal Evrak İndirici - Evrensel Başlatıcı (Python Menü)
(c) 2026 Av. Can KIZILYAR - Tüm hakları saklıdır.

Windows, Termux (Android), Linux ve macOS üzerinde 'python baslat.py'
veya 'python3 baslat.py' yazılarak doğrudan çalıştırılabilir.
"""

import os
import sys
import subprocess

IS_TERMUX = bool(os.environ.get("PREFIX", "").startswith("/data/data/com.termux"))
PYTHON_EXE = sys.executable or ("python3" if not sys.platform.startswith("win") else "python")


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_menu():
    clear_screen()
    ortam = "Android / Termux" if IS_TERMUX else ("Windows" if os.name == "nt" else "Linux / macOS")
    print("=" * 66)
    print(f"   UYAP Avukat Portal Evrak İndirici — {ortam}")
    print("   (c) 2026 Av. Can KIZILYAR — Tüm hakları saklıdır")
    print("=" * 66)
    print()
    print("  1. İşlemlerim İndirici [Son 1 Yıl - Hızlı]")
    print("  2. İşlemlerim İndirici [Geçmiş Yıllar / Özel Tarih Aralığı]")
    print("  3. Dava Dosyalarından Belirli Evrak İndir [Duruşma, Rapor vb.]")
    print("  4. Dava Dosyalarından TÜM Evrakları ve EKLERİ İndir [Toplu Arşiv]")
    print("  5. Dava ve Cevap Layihaları [Dava, Cevap, Bilirkişi İtiraz, Beyan]")
    print("  6. Tebligat ve Mazbatalar [Fiziki PTT + UETS Süreli Tebligatlar]")
    print("  7. Duruşma Takvimi Oluştur [.ics / Google ve Outlook Takvim + CSV]")
    print("  8. İndirilen UDF'leri PDF'e Dönüştür [Toplu Vektörel PDF]")
    print("  9. Tebligat ve Süre Analizi Çalıştır [tebligat_takip_listesi.csv]")
    print(" 10. Evrak Zenginleştirme ve Akıllı İsimlendirme [enrich_and_rename]")
    print(" 11. Chrome / Edge UYAP Oturumu Başlat [Port 9223]")
    print(" 12. EVRAK KATALOĞU: Tara, Filtrele, Seçip İndir [Pencere / GUI]")
    print(" 13. UYAP Nöbetçi Bot [Pencere / GUI - Canlı İzleme ve Drive Eşitleme]")
    print(" 14. UYAP Nöbetçi Bot [Terminal / Konsol - Eksikleri Tamamla ve Drive]")
    print(" 15. Hukuki Süre ve Görev Analizi [Canlı Duruşma + Ara Karar + Tebligat]")
    print(" 16. Notion ve TickTick Entegrasyon Paketini Üret [CSV + ICS]")
    print("  0. Çıkış")
    print()
    print("=" * 66)


def run_cmd(cmd_list):
    try:
        subprocess.run(cmd_list)
    except KeyboardInterrupt:
        print("\n[!] İşlem kullanıcı tarafından durduruldu.")
    except Exception as e:
        print(f"\n[HATA] Komut çalıştırılamadı: {e}")
    input("\nDevam etmek için Enter'a basın...")


def main():
    while True:
        print_menu()
        try:
            secim = input("Seçiminiz (0-16) [Varsayılan: 1]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nÇıkış yapıldı.")
            break

        if not secim:
            secim = "1"

        if secim == "0":
            print("\nİyi çalışmalar dileriz.")
            break

        elif secim == "1":
            print("\n[*] İşlemlerim - Son 1 Yıl indiriliyor...")
            run_cmd([PYTHON_EXE, "uyap_indirici.py", "--cli", "--mode", "islemlerim"])

        elif secim == "2":
            print("\n[*] İşlemlerim - Özel Tarih Aralığı")
            start_d = input("Başlangıç Tarihi (GG.AA.YYYY) [Örn: 01.01.2020]: ").strip()
            end_d = input("Bitiş Tarihi     (GG.AA.YYYY) [Örn: 16.11.2026]: ").strip()
            cmd = [PYTHON_EXE, "uyap_indirici.py", "--cli", "--mode", "islemlerim"]
            if start_d:
                cmd.extend(["--start-date", start_d])
            if end_d:
                cmd.extend(["--end-date", end_d])
            run_cmd(cmd)

        elif secim == "3":
            print("\n[*] Dava Dosyalarından Belirli Evrak İndirme")
            print("  1) Duruşma Zabıtları [Önerilen]")
            print("  2) Bilirkişi Raporları")
            print("  3) Gerekçeli Karar / İlamlar")
            print("  4) Tensip Zabıtları")
            print("  5) Layihalar (Dava, Cevap, İtiraz, Beyan)")
            print("  6) Müzekkere Cevapları")
            print("  7) İddianame ve Fezleke")
            print("  8) Kesinleşme Şerhleri")
            print("  9) Özel Kelime Arama")
            e_sec = input("Seçim (1-9) [Varsayılan: 1]: ").strip()
            tur_map = {
                "2": "bilirkisi", "3": "karar", "4": "tensip", "5": "layihalar",
                "6": "muzekkere", "7": "iddianame", "8": "kesinlesme"
            }
            tur = tur_map.get(e_sec, "durusma")
            if e_sec == "9":
                tur = input("Aranacak evrak türü / kelime: ").strip() or "durusma"

            print("\n  Dosya Kapsamı:")
            print("  1) Tüm Dosyalar [Açık + Kapalı]")
            print("  2) Yalnızca Açık / Derdest Dosyalar")
            print("  3) Sık Kullanılan Dosyalar")
            k_sec = input("Kapsam (1-3) [Varsayılan: 1]: ").strip()
            scope = "acik" if k_sec == "2" else ("fav" if k_sec == "3" else "all")
            kw = input("Filtrelemek istenen Mahkeme / Esas No (Tümü için boş geçin): ").strip()

            cmd = [PYTHON_EXE, "uyap_indirici.py", "--cli", "--mode", "dosyalar", "--evrak-turu", tur, "--scope", scope]
            if kw:
                cmd.extend(["--filter-birim", kw])
            run_cmd(cmd)

        elif secim == "4":
            print("\n[*] Dava Dosyalarından TÜM Evraklar ve Ekleri [Toplu Arşiv]")
            kw = input("Filtrelenecek Mahkeme / Esas No (Tümü için boş geçin): ").strip()
            cmd = [PYTHON_EXE, "uyap_indirici.py", "--cli", "--mode", "dosyalar", "--evrak-turu", "tumu", "--include-attachments", "--scope", "all"]
            if kw:
                cmd.extend(["--filter-birim", kw])
            run_cmd(cmd)

        elif secim == "5":
            print("\n[*] Dava ve Cevap Layihaları İndiriliyor...")
            run_cmd([PYTHON_EXE, "uyap_indirici.py", "--cli", "--mode", "dosyalar", "--evrak-turu", "layihalar", "--scope", "all"])

        elif secim == "6":
            print("\n[*] Tebligat ve Mazbatalar İndiriliyor...")
            run_cmd([PYTHON_EXE, "uyap_indirici.py", "--cli", "--mode", "dosyalar", "--evrak-turu", "tebligat", "--scope", "all"])

        elif secim == "7":
            print("\n[*] Duruşma Takvimi Oluşturuluyor [.ics ve CSV]...")
            run_cmd([PYTHON_EXE, "uyap_indirici.py", "--cli", "--mode", "durusmalar"])

        elif secim == "8":
            print("\n[*] UDF -> PDF Dönüştürücü Başlatılıyor...")
            run_cmd([PYTHON_EXE, "donusturucu.py"])

        elif secim == "9":
            print("\n[*] Tebligat ve Süre Analizi Çalıştırılıyor...")
            run_cmd([PYTHON_EXE, "tebligat_yoneticisi.py"])

        elif secim == "10":
            print("\n[*] Evrak Zenginleştirme ve Akıllı İsimlendirme...")
            run_cmd([PYTHON_EXE, "enrich_and_rename_documents.py"])

        elif secim == "11":
            print("\n[*] UYAP Oturumu ve Tarayıcı Yönetimi")
            print("  1) Tarayıcı Başlat [Port 9223]")
            print("  2) Mobil İmza ile Giriş Yap [Android Termux & e-Devlet]")
            print("  3) e-İmza ile Otomatik Giriş Yap [ArkSigner & pin.txt]")
            print("  4) Aktif Oturum Durumunu Doğrula")
            sub = input("Seçiminiz (1-4) [Varsayılan: 1]: ").strip() or "1"
            if sub == "2":
                run_cmd([PYTHON_EXE, "uyap_indirici.py", "--cli", "--mode", "login"])
            elif sub == "3":
                run_cmd([PYTHON_EXE, "uyap_indirici.py", "--relogin"])
            elif sub == "4":
                run_cmd([PYTHON_EXE, "uyap_indirici.py", "--check-login"])
            else:
                run_cmd([PYTHON_EXE, "uyap_indirici.py", "--browser-only"])

        elif secim == "12":
            print("\n[*] Evrak Kataloğu Açılıyor...")
            run_cmd([PYTHON_EXE, "uyap_indirici.py", "--katalog"])

        elif secim == "13":
            print("\n[*] UYAP Nöbetçi Bot (Pencereli GUI Modu) Açılıyor...")
            run_cmd([PYTHON_EXE, "uyap_indirici.py", "--katalog", "--watcher"])

        elif secim == "14":
            print("\n[*] UYAP Nöbetçi Bot (Terminal / Konsol Modu)...")
            intv = input("Kontrol Sıklığı (Dakika) [Varsayılan: 15]: ").strip() or "15"
            run_cmd([PYTHON_EXE, "uyap_watcher.py", "--interval", intv])

        elif secim == "15":
            print("\n[*] Hukuki Süre ve Görev Analizi...")
            run_cmd([PYTHON_EXE, "uyap_sure_analiz.py"])

        elif secim == "16":
            print("\n[*] Notion ve TickTick Entegrasyon Paketleri Üretiliyor...")
            run_cmd([PYTHON_EXE, "uyap_entegrasyon.py"])

        else:
            print("[!] Geçersiz seçim!")
            input("Tekrar denemek için Enter'a basın...")


if __name__ == "__main__":
    main()
