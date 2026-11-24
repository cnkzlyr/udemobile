@echo off
rem ================================================================
rem  UYAP Dosya Arsivleyici ^& Drive Senkronizasyonu (Windows CMD)
rem  (c) 2026 Av. Can KIZILYAR - Tum haklari saklidir.
rem ================================================================
setlocal
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%dosya_arsivle.py" %*
endlocal
