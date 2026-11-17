@echo off
rem Copyright (c) 2026 Av. Can KIZILYAR. Tum haklari saklidir.
chcp 65001 >nul
title UYAP Avukat Portal Evrak Indirici - Windows 11
color 0B

cd /d "%~dp0"

:menu
cls
echo ==================================================================
echo    UYAP Avukat Portal Evrak Indirici - Windows 11
echo    (c) 2026 Av. Can KIZILYAR - Tum haklari saklidir
echo ==================================================================
echo.
echo   1. Islemlerim Indirici [Son 1 Yil - Hizli]
echo   2. Islemlerim Indirici [Gecmis Yillar / Ozel Tarih Araligi]
echo   3. Dava Dosyalarindan Belirli Evrak Indir [Durusma, Rapor vb.]
echo   4. Dava Dosyalarindan TUM Evraklari ve EKLERI Indir [Toplu Arsiv]
echo   5. Dava ve Cevap Layihalari [Dava, Cevap, Bilirkisi Itiraz, Beyan]
echo   6. Tebligat ve Mazbatalar [Fiziki PTT + UETS Sureli Tebligatlar]
echo   7. Durusma Takvimi Olustur [.ics / Google ve Outlook Takvim + CSV]
echo   8. Indirilen UDF'leri PDF'e Donustur [TrueType Embedded PDF]
echo   9. Tebligat ve Sure Analizi Calistir [tebligat_takip_listesi.csv]
echo  10. Evrak Zenginlestirme ve Akilli Isimlendirme [enrich_and_rename]
echo  11. Chrome / Edge UYAP Oturumu Baslat [Port 9223]
echo  12. EVRAK KATALOGU: Tara, Filtrele, Secip Bir Kez Indir [Pencere]
echo  13. UYAP Nobetci Bot [Pencere / GUI - Canli Izleme ve Drive Esitleme]
echo  14. UYAP Nobetci Bot [Terminal / Konsol - GUI Filtreleriyle Eksikleri Tamamla ve Drive]
echo  15. Hukuki Sure ve Gorev Analizi [Canli Durusma + Ara Karar + Tebligat]
echo  16. Notion ve TickTick Entegrasyon Paketini Uret [CSV + ICS]
echo   0. Cikis
echo.
echo ==================================================================
set secim=
set /p secim="Seciminiz 0-16 [Varsayilan: 1]: "
if "%secim%"=="" set secim=1
if "%secim%"=="0" goto cikis

if "%secim%"=="1" goto opt1
if "%secim%"=="2" goto opt2
if "%secim%"=="3" goto opt3
if "%secim%"=="4" goto opt4
if "%secim%"=="5" goto opt5
if "%secim%"=="6" goto opt6
if "%secim%"=="7" goto opt7
if "%secim%"=="8" goto opt8
if "%secim%"=="9" goto opt9
if "%secim%"=="10" goto opt10
if "%secim%"=="11" goto opt11
if "%secim%"=="12" goto opt12
if "%secim%"=="13" goto opt13
if "%secim%"=="14" goto opt14
if "%secim%"=="15" goto opt15
if "%secim%"=="16" goto opt16
goto opt1

:opt1
echo.
echo [*] Islemlerim - Son 1 Yil indiriliyor...
python uyap_indirici.py --cli --mode islemlerim
goto bitir

:opt2
echo.
echo [*] Islemlerim - Ozel Tarih Araligi
set /p start_d="Baslangic Tarihi GG.AA.YYYY [Orn: 01.01.2020]: "
set /p end_d="Bitis Tarihi     GG.AA.YYYY [Orn: 14.11.2026]: "
python uyap_indirici.py --cli --mode islemlerim --start-date "%start_d%" --end-date "%end_d%"
goto bitir

:opt3
echo.
echo [*] Dava Dosyalarindan Belirli Evrak Indirme
echo   1. Durusma Tutanaklari / Zabitlari [Onerilen]
echo   2. Bilirkisi Raporlari
echo   3. Gerekceli Karar, Hukum ve Ilamlar
echo   4. Tensip Zabitlari
echo   5. Muzekkere ve Kurum Cevaplari [Banka, Tapu, SGK vb.]
echo   6. Iddianame ve Fezleke
echo   7. Kesinlesme Serhleri
echo   8. Ozel Evrak Turu / Serbest Kelime Arama
set /p ev_sec="Seciminiz 1-8 [Varsayilan: 1]: "
if "%ev_sec%"=="" set ev_sec=1

set TUR=durusma
if "%ev_sec%"=="2" set TUR=bilirkisi
if "%ev_sec%"=="3" set TUR=karar
if "%ev_sec%"=="4" set TUR=tensip
if "%ev_sec%"=="5" set TUR=muzekkere
if "%ev_sec%"=="6" set TUR=iddianame
if "%ev_sec%"=="7" set TUR=kesinlesme
if "%ev_sec%"=="8" (
    set /p custom_type="Aranacak Evrak Turu / Kelime: "
    set TUR=%custom_type%
)

echo.
echo   Dosya Kapsami:
echo     1. Tum Dosyalar [Acik + Kapali / Karara Cikmis] [Onerilen]
echo     2. Yalnizca Acik / Derdest Dosyalar
echo     3. Sik Kullanilan Dosyalar [Hizli]
set /p kap_sec="Seciminiz 1-3 [Varsayilan: 1]: "
if "%kap_sec%"=="" set kap_sec=1

set SCOPE=all
if "%kap_sec%"=="2" set SCOPE=acik
if "%kap_sec%"=="3" set SCOPE=fav

set /p filter_kw="Filtrelenecek Mahkeme veya Esas No [Tumu icin bos gecin]: "
if not "%filter_kw%"=="" (
    python uyap_indirici.py --cli --mode dosyalar --evrak-turu "%TUR%" --scope "%SCOPE%" --filter-birim "%filter_kw%"
) else (
    python uyap_indirici.py --cli --mode dosyalar --evrak-turu "%TUR%" --scope "%SCOPE%"
)
goto bitir

:opt4
echo.
echo [*] Dava Dosyalarindan TUM Evraklari ve Ekleri Indirme [Toplu Arsiv]
set /p filter_kw="Filtrelenecek Mahkeme veya Esas No [Tumu icin bos gecin]: "
if not "%filter_kw%"=="" (
    python uyap_indirici.py --cli --mode dosyalar --evrak-turu tumu --include-attachments --scope all --filter-birim "%filter_kw%"
) else (
    python uyap_indirici.py --cli --mode dosyalar --evrak-turu tumu --include-attachments --scope all
)
goto bitir

:opt5
echo.
echo [*] Dava ve Cevap Layihalari Indiriliyor [Dava, Cevap, Bilirkisi Itiraz, Beyan]...
python uyap_indirici.py --cli --mode dosyalar --evrak-turu layihalar --scope all
goto bitir

:opt6
echo.
echo ==================================================================
echo    Tebligat ve Mazbata Indirici [Fiziki PTT + UETS]
echo ==================================================================
echo.
echo   Dosya / Yargi Turu Secimi:
echo     1. Hukuk Mahkemeleri [Hukuk Yargisi]
echo     2. Ceza Mahkemeleri [Ceza Yargisi]
echo     3. Idari Yargi [Idare ve Vergi Mahkemeleri, BIM]
echo     4. Icra [Icra Daireleri ve Mahkemeleri]
echo     [Tumu icin bos birakin / Enter'a basin]
echo.
set /p yargi_sec="Yargi Turu Seciminiz [1-4 veya Bos]: "

set YARGI_PARAM=
if "%yargi_sec%"=="1" set YARGI_PARAM=--yargi-turu hukuk
if "%yargi_sec%"=="2" set YARGI_PARAM=--yargi-turu ceza
if "%yargi_sec%"=="3" set YARGI_PARAM=--yargi-turu idari
if "%yargi_sec%"=="4" set YARGI_PARAM=--yargi-turu icra

echo.
echo   Tebligat Zaman Araligi:
echo     1. Son 5 Gunluk [Acil Yasal Sureli Tebligatlar] - Onerilen
echo     2. Son 1 Haftalik [7 Gun]
echo     3. Son 2 Haftalik [14 Gun]
echo     4. Son 30 Gunluk [1 Ay]
echo     5. Son 60 Gunluk [2 Ay]
echo     6. Son 90 Gunluk [3 Ay]
echo     7. Su Tarihten Beri... [Ozel Baslangic Tarihi]
echo     8. Tum Gecmis [Sinirlama Yok]
echo.
set /p teb_time="Zaman Araligi Seciminiz [1-8, Varsayilan: 1]: "
if "%teb_time%"=="" set teb_time=1

if "%teb_time%"=="1" set DATE_PARAM=--days 5
if "%teb_time%"=="2" set DATE_PARAM=--days 7
if "%teb_time%"=="3" set DATE_PARAM=--days 14
if "%teb_time%"=="4" set DATE_PARAM=--days 30
if "%teb_time%"=="5" set DATE_PARAM=--days 60
if "%teb_time%"=="6" set DATE_PARAM=--days 90
if "%teb_time%"=="8" set DATE_PARAM=
if "%teb_time%"=="7" goto opt6_custom_date
goto opt6_run

:opt6_custom_date
set /p custom_start="Baslangic Tarihi GG.AA.YYYY [Orn: 01.10.2026]: "
set DATE_PARAM=--start-date "%custom_start%"
goto opt6_run

:opt6_run
echo.
echo [*] Tebligatlar indiriliyor...
python uyap_indirici.py --cli --mode dosyalar --evrak-turu tebligat --scope all %YARGI_PARAM% %DATE_PARAM%
goto bitir

:opt7
echo.
echo [*] Durusma Takvimi Olusturuluyor [.ics ve CSV]...
python uyap_indirici.py --cli --mode durusmalar
goto bitir

:opt8
echo.
echo [*] UDF - PDF Donusturucu Calistiriliyor...
call udf_toplu_pdf.bat
goto bitir

:opt9
echo.
echo [*] Tebligat ve Sure Yoneticisi Calistiriliyor [PTT ve UETS Analizi]...
python tebligat_yoneticisi.py
goto bitir

:opt10
echo.
echo [*] Evrak Zenginlestirme ve Akilli Isimlendirme Calistiriliyor...
python enrich_and_rename_documents.py
goto bitir

:opt11
echo.
echo [*] Chrome / Edge UYAP Oturumu Baslatiliyor [Port 9223]...
rem Script ile ayni profil ve port kullanilir (oturum ortak olur)
python uyap_indirici.py --browser-only
goto bitir

:opt12
echo.
echo [*] Evrak Katalogu aciliyor...
python uyap_indirici.py --katalog
goto bitir

:opt13
echo.
echo [*] UYAP Nobetci Bot (Pencereli / GUI Modu) baslatiliyor...
python uyap_indirici.py --katalog --watcher
goto bitir

:opt14
echo.
echo ==================================================================
echo   UYAP Nobetci Bot - Terminal / Konsol Modu
echo   (GUI Filtreleri varsayilan alinir; yeni + eksik evraklar Drive'a aktarilir)
echo ==================================================================
echo.
set /p intv="Kontrol Sikligi (Dakika) [Varsayilan: 15]: "
if "%intv%"=="" set intv=15
python uyap_watcher.py --interval %intv%
goto bitir

:opt15
echo.
echo ==================================================================
echo   Hukuki Sure ve Gorev Analizi
echo   (Canli UYAP Durusmalari + Durusma Zabti Ara Kararlari + Tebligatlar)
echo ==================================================================
echo.
python uyap_sure_analiz.py
goto bitir

:opt16
echo.
echo ==================================================================
echo   Notion ve TickTick Entegrasyon Paketini Uret
echo ==================================================================
echo.
python uyap_entegrasyon.py
goto bitir

:bitir
echo.
echo [*] Islem bitti. Menuye donmek icin bir tusa basin.
pause >nul
goto menu

:cikis
exit /b 0
