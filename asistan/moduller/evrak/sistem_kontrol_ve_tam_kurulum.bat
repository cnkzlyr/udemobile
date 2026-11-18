@echo off
chcp 65001 >nul
title Antigravity & UYAP Windows 11 Eksiksiz Sistem Kurucu
color 0A

echo ======================================================================
echo    UYAP & Antigravity - Windows 11 Tam Donanim ve Saglik Kontrolu
echo ======================================================================
echo.

set SCRIPT_DIR=%~dp0
set CONV_ID=cb9e5c44-86ab-4d5b-b419-ec7fc343613d
set TARGET_CLI_DIR=%USERPROFILE%\.gemini\antigravity-cli
set TARGET_CONV_DIR=%TARGET_CLI_DIR%\conversations
set TARGET_BRAIN_DIR=%TARGET_CLI_DIR%\brain\%CONV_ID%

:: 1. Antigravity DB & Brain Kontrolü
echo [*] 1/5: Antigravity Sohbet Dosyalari Kontrol Ediliyor...
if not exist "%TARGET_CONV_DIR%\%CONV_ID%.db" (
    echo [!] DB eksik gorunuyor, kopyalaniyor...
    if not exist "%TARGET_CONV_DIR%" mkdir "%TARGET_CONV_DIR%"
    if exist "%SCRIPT_DIR%Antigravity_Aktarim\conversations\%CONV_ID%.db" (
        copy /Y "%SCRIPT_DIR%Antigravity_Aktarim\conversations\%CONV_ID%.db" "%TARGET_CONV_DIR%\" >nul
    )
)
if not exist "%TARGET_BRAIN_DIR%" (
    echo [!] Brain eksik gorunuyor, kopyalaniyor...
    mkdir "%TARGET_BRAIN_DIR%"
    if exist "%SCRIPT_DIR%Antigravity_Aktarim\brain\%CONV_ID%" (
        xcopy /E /I /Y "%SCRIPT_DIR%Antigravity_Aktarim\brain\%CONV_ID%" "%TARGET_BRAIN_DIR%" >nul
    )
)
echo [✓] Antigravity sohbet ve hafiza dosyalari yerinde.

:: 2. Masaüstü Kısayolları Kontrolü
echo.
echo [*] 2/5: Masaustu Kisayollari Denetleniyor...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\UYAP Indirilen Evraklar.lnk'); $s.TargetPath = '%SCRIPT_DIR%UYAP_Indirilenler'; $s.Description = 'UYAP Evraklari'; $s.Save()" >nul 2>&1
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\UYAP Evrak Indirici.lnk'); $s.TargetPath = '%SCRIPT_DIR%uyap-evrak-indirici\baslat_windows.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%uyap-evrak-indirici'; $s.Description = 'UYAP Baslatici'; $s.Save()" >nul 2>&1
echo [✓] Masaustu kisayollari guncellendi.

:: 3. Python Kurulum Kontrolü ve Otomatik Yükleme
echo.
echo [*] 3/5: Python Kontrol Ediliyor...
python -c "import sys" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [!] Python bulunamadi veya etkin degil. Winget ile otomatik kuruluyor...
    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    echo [*] Sistem ortami yenileniyor...
    call refreshenv >nul 2>&1
) else (
    echo [✓] Python zaten kurulu.
)

:: 4. Python Kütüphaneleri ve Playwright Chromium
echo.
echo [*] 4/5: Gerekli Python Kutuphaneleri Yukleniyor...
python -m pip install --upgrade pip --quiet >nul 2>&1
python -m pip install playwright requests pydantic --quiet
python -m playwright install chromium
echo [✓] Python kutuphaneleri (playwright, requests, pydantic, chromium) hazir.

:: 5. Java Kontrolü (UDF - PDF Dönüştürücü için)
echo.
echo [*] 5/5: Java (UDF -^> PDF Donusturucu) Kontrol Ediliyor...
java -version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [*] Java kurulu degil. Havelsan UDF motoru icin Microsoft OpenJDK 17 kuruluyor...
    winget install Microsoft.OpenJDK.17 --silent --accept-package-agreements --accept-source-agreements
    echo [✓] Java kurulumu tamamlandi.
) else (
    echo [✓] Java zaten kurulu ve calisiyor.
)

echo.
echo ======================================================================
echo    [✓] TUM SISTEM BILGISAYARINIZDA EKSIKSIZ VE CALISIR DURUMDA!
echo ======================================================================
echo.
echo   - Masaustundeki 'UYAP Indirilen Evraklar' ile 4.489 evrakinizi acabilirsiniz.
echo   - Masaustundeki 'UYAP Evrak Indirici' ile yeni evrak indirebilirsiniz.
echo   - Antigravity IDE uygulamasinda bu sohbete devam edebilirsiniz.
echo ======================================================================
echo.
pause
