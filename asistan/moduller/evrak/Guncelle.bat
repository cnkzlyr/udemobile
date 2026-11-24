@echo off
rem ================================================================
rem  UYAP Evrak Yöneticisi — Otomatik Güncelleyici
rem  © 2026 Av. Can KIZILYAR — Tüm hakları saklıdır.
rem ================================================================
chcp 65001 >nul
title UYAP Evrak Yöneticisi - Güncelleme

cd /d "%~dp0"

echo.
echo [*] En güncel sürüm ve hata düzeltmeleri alınıyor...
git pull origin main
if %errorlevel% equ 0 (
    echo.
    echo [✓] Güncelleme başarıyla tamamlandı!
    echo [*] Artık GUI_Baslat.bat veya Terminal_Baslat.bat ile çalıştırabilirsiniz.
) else (
    echo.
    echo [!] Güncelleme sırasında bir uyarı oluştu. İnternet bağlantınızı kontrol edin.
)
echo.
pause
