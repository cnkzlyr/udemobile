@echo off
rem ================================================================
rem  UYAP Evrak Yöneticisi & Hukuk Asistanı (Terminal / Konsol Menüsü)
rem  © 2026 Av. Can KIZILYAR — Tüm hakları saklıdır.
rem ================================================================
chcp 65001 >nul
title UYAP Evrak Yöneticisi - Terminal Menüsü

cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% equ 0 (
    python baslat.py --cli
    goto end
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 baslat.py --cli
    goto end
)

echo [HATA] Python bulunamadi! Lutfen Python 3.10+ yukleyin (python.org).
pause

:end
