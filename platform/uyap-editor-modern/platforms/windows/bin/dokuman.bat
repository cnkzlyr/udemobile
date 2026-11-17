@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

:: ==============================================================================
:: UYAP Dokuman Editoru - Modern Windows Baslatici
:: Gelistirici: Can Kizilyar (github.com/cnkzlyr)
:: ==============================================================================

:: Ana dizin tespiti (uyap-modernizer.jar veya editor_lib.jar neredeyse)
if exist "%~dp0uyap-modernizer.jar" (
    set "BASE_DIR=%~dp0"
) else if exist "%~dp0editor_lib.jar" (
    set "BASE_DIR=%~dp0"
) else if exist "%~dp0..\uyap-modernizer.jar" (
    set "BASE_DIR=%~dp0.."
) else if exist "%LOCALAPPDATA%\Programs\UYAP Editor Modern\uyap-modernizer.jar" (
    set "BASE_DIR=%LOCALAPPDATA%\Programs\UYAP Editor Modern"
) else if exist "%LOCALAPPDATA%\UYAPEditorModern\uyap-modernizer.jar" (
    set "BASE_DIR=%LOCALAPPDATA%\UYAPEditorModern"
) else (
    set "BASE_DIR=%~dp0"
)
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"

:: Java 14.0.2 Tespiti
if exist "%BASE_DIR%\jdk-14.0.2\bin\javaw.exe" (
    set "JAVA_CMD=%BASE_DIR%\jdk-14.0.2\bin\javaw.exe"
) else if exist "%LOCALAPPDATA%\Programs\UYAP Editor Modern\jdk-14.0.2\bin\javaw.exe" (
    set "JAVA_CMD=%LOCALAPPDATA%\Programs\UYAP Editor Modern\jdk-14.0.2\bin\javaw.exe"
) else if exist "%LOCALAPPDATA%\UYAPEditorModern\jdk-14.0.2\bin\javaw.exe" (
    set "JAVA_CMD=%LOCALAPPDATA%\UYAPEditorModern\jdk-14.0.2\bin\javaw.exe"
) else if defined JAVA_HOME if exist "%JAVA_HOME%\bin\javaw.exe" (
    set "JAVA_CMD=%JAVA_HOME%\bin\javaw.exe"
) else (
    set "JAVA_CMD=javaw.exe"
)

:: Classpath Olusturma
if exist "%BASE_DIR%\uyap-modernizer.jar" (
    set "CP_PATH=%BASE_DIR%\uyap-modernizer.jar;%BASE_DIR%\*"
    set AGENT_OPTS="-javaagent:%BASE_DIR%\uyap-modernizer.jar"
) else (
    set "CP_PATH=%BASE_DIR%\*"
    set "AGENT_OPTS="
)

:: Resmi UYAP kütüphaneleri (editor_lib.jar) fallback
if not exist "%BASE_DIR%\editor_lib.jar" (
    if exist "C:\Uyap\Uyap Kelime Islemci\editor_lib.jar" (
        set "CP_PATH=%CP_PATH%;C:\Uyap\Uyap Kelime Islemci\*"
    ) else if exist "%ProgramFiles(x86)%\UYAP\UYAPEditor\editor_lib.jar" (
        set "CP_PATH=%CP_PATH%;%ProgramFiles(x86)%\UYAP\UYAPEditor\*"
    ) else if exist "%ProgramFiles%\UYAP\UYAPEditor\editor_lib.jar" (
        set "CP_PATH=%CP_PATH%;%ProgramFiles%\UYAP\UYAPEditor\*"
    ) else if exist "C:\UYAPEditor\editor_lib.jar" (
        set "CP_PATH=%CP_PATH%;C:\UYAPEditor\*"
    )
)

:: E-imza: Unicode PC/SC ajani. JDK'nin Windows PC/SC katmani adinda Turkce karakter olan okuyuculari
:: (ArkSigner: "Microsoft Usbccid Akilli Kart Okuyucusu (WUDF)") acamiyor; ajan Windows'un Unicode islevlerini kullanir.
if exist "%BASE_DIR%\uyap-pcsc-agent.jar" set AGENT_OPTS=%AGENT_OPTS% "-javaagent:%BASE_DIR%\uyap-pcsc-agent.jar"

:: E-Imza & Akilli Kart (Windows akisp11.dll & ArkSigner)
set "PKCS11_OPTS=-Djava.library.path=%BASE_DIR%;%SystemRoot%\System32;%SystemRoot%\SysWOW64"

:: UI & Performans Parametreleri
set "FONT_OPTS=-Dawt.useSystemAAFontSettings=lcd -Dswing.aatext=true"
set "MEM_OPTS=-Xms256m -Xmx1024m -XX:+UseG1GC -XX:+UseStringDeduplication"

:: Hedef dosya kontrolü ve tip tespiti (.usf şablon / .udf doküman)
set "TARGET=%~1"
set "EDITOR_TYPE=EDITOR_TYPE_DOCUMENT"
if defined TARGET (
    if /I "%TARGET:~-4%"==".usf" set "EDITOR_TYPE=EDITOR_TYPE_TEMPLATE"
    start "" "%JAVA_CMD%" %PKCS11_OPTS% %MEM_OPTS% %FONT_OPTS% %AGENT_OPTS% -cp "%CP_PATH%" tr.com.havelsan.uyap.system.editor.common.WPAppManager "getNewWPInstance" !EDITOR_TYPE! "%TARGET%"
) else (
    start "" "%JAVA_CMD%" %PKCS11_OPTS% %MEM_OPTS% %FONT_OPTS% %AGENT_OPTS% -cp "%CP_PATH%" tr.com.havelsan.uyap.system.editor.common.WPAppManager "getNewWPInstance" "EDITOR_TYPE_DOCUMENT"
)
