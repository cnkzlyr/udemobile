@echo off
rem caneditor - CanEditor terminal arayuzu (Windows). EN: CanEditor CLI launcher for Windows.
rem Kullanim: caneditor --help  ^|  caneditor durum  ^|  caneditor pdf "C:\UYAP_Indirilenler"
chcp 65001 >nul
setlocal
set "KOK=%~dp0"
if exist "%KOK%asistan\caneditor_cli.py" set "KOK=%KOK%asistan\"
if exist "%KOK%_up_\asistan\caneditor_cli.py" set "KOK=%KOK%_up_\asistan\"
if not exist "%KOK%caneditor_cli.py" if exist "%LOCALAPPDATA%\CanEditor\asistan\caneditor_cli.py" set "KOK=%LOCALAPPDATA%\CanEditor\asistan\"
if not exist "%KOK%caneditor_cli.py" if exist "%ProgramFiles%\CanEditor\asistan\caneditor_cli.py" set "KOK=%ProgramFiles%\CanEditor\asistan\"
if not defined CANASISTAN_PAKET_JARS if exist "%KOK%jars\uyap-editor" set "CANASISTAN_PAKET_JARS=%KOK%jars\uyap-editor"
if not defined CANASISTAN_FONTS if exist "%KOK%fonts" set "CANASISTAN_FONTS=%KOK%fonts"
if not defined CANASISTAN_JAVA_HOME if exist "%KOK%..\eimza\jre\bin\java.exe" set "CANASISTAN_JAVA_HOME=%KOK%..\eimza\jre"
set PYTHONIOENCODING=utf-8
where py >nul 2>nul && (py -3 "%KOK%caneditor_cli.py" %* & exit /b %errorlevel%)
where python >nul 2>nul && (python "%KOK%caneditor_cli.py" %* & exit /b %errorlevel%)
if exist "%KOK%..\sidecar\asistan-sunucu-x86_64\asistan-sunucu.exe" ("%KOK%..\sidecar\asistan-sunucu-x86_64\asistan-sunucu.exe" --calistir "%KOK%caneditor_cli.py" %* & exit /b %errorlevel%)
echo caneditor: Python 3 ya da CanEditor masaustu paketi gerekli. 1>&2
exit /b 2
