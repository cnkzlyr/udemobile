@echo off
rem ================================================================
rem  UYAP UDF E-Imza ^& Mobil Imza Evrensel Imzalayici (Windows CMD)
rem  (c) 2026 Av. Can KIZILYAR - Tum haklari saklidir.
rem ================================================================
setlocal
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%uyap_imzala.py" %*
endlocal
