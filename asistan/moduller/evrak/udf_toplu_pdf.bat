@echo off
chcp 65001 >nul
set DIR=%~dp0
set JARS_DIR=%DIR%jars
if not exist "%JARS_DIR%" (
    if exist "%DIR%..\jars" set JARS_DIR=%DIR%..\jars
)

set CP="%DIR%;%JARS_DIR%\*"
echo [*] UDF -^> PDF Havelsan Donusturucu Baslatiliyor...
java -Xmx1024m -Djava.awt.headless=true ^
    --add-opens=java.base/java.util=ALL-UNNAMED ^
    --add-opens=java.base/java.lang=ALL-UNNAMED ^
    --add-opens=java.desktop/java.awt=ALL-UNNAMED ^
    --add-opens=java.desktop/javax.swing=ALL-UNNAMED ^
    -cp %CP% uyap.UdfBatchPdfConverter %*
