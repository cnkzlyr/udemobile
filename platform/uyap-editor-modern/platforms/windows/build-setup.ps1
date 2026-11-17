# ==============================================================================
# UYAP Editör Modern - Windows Setup (.exe) Derleme Betiği
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "=== UYAP Editör Modern Windows Setup Derleyici ===" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$StagingDir = "$ScriptDir\staging"
$DistDir = "$RootDir\dist"
$CacheDir = "$env:TEMP\uyap_build_cache"

if (-not (Test-Path $StagingDir)) { New-Item -ItemType Directory -Path $StagingDir -Force | Out-Null }
if (-not (Test-Path $DistDir)) { New-Item -ItemType Directory -Path $DistDir -Force | Out-Null }
if (-not (Test-Path $CacheDir)) { New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null }

# İkonları staging'e aktar
if (Test-Path "$ScriptDir\icons") {
    Copy-Item "$ScriptDir\icons\*" "$StagingDir\" -Force -ErrorAction SilentlyContinue
}

# ------------------------------------------------------------------------------
# 1. OpenJDK 14.0.2 Windows x64 Temini
# ------------------------------------------------------------------------------
Write-Host "`n[1/5] OpenJDK 14.0.2 kontrol ediliyor..." -ForegroundColor Yellow
$JdkTarget = "$StagingDir\jdk-14.0.2"
if (-not (Test-Path "$JdkTarget\bin\javaw.exe")) {
    $JdkZip = "$CacheDir\openjdk-14.0.2_windows-x64_bin.zip"
    if (-not (Test-Path $JdkZip)) {
        Write-Host "OpenJDK 14.0.2 indiriliyor..." -ForegroundColor Yellow
        $JdkUrl = "https://download.java.net/java/GA/jdk14.0.2/205943a0976c4ed48cb16f1043c5c647/12/GPL/openjdk-14.0.2_windows-x64_bin.zip"
        curl.exe -L $JdkUrl -o $JdkZip
    }
    Write-Host "OpenJDK 14.0.2 aciliyor..." -ForegroundColor Yellow
    Expand-Archive -Path $JdkZip -DestinationPath "$CacheDir\jdk_temp" -Force
    Copy-Item -Path "$CacheDir\jdk_temp\jdk-14.0.2" -Destination $StagingDir -Recurse -Force
}
Write-Host "[OK] OpenJDK 14.0.2 hazir." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 2. Resmi UYAP Kütüphaneleri ve Varlıkları
# ------------------------------------------------------------------------------
Write-Host "`n[2/5] Resmi UYAP dosyalari kontrol ediliyor..." -ForegroundColor Yellow
$RequiredJars = @("editor_lib.jar", "editor_lib2.jar", "editor_utility.jar", "editor_laf.jar", "jai_hvl.jar", "jdom.jar", "updater.jar")
$MissingJars = $RequiredJars | Where-Object { -not (Test-Path "$StagingDir\$_") }

if ($MissingJars.Count -gt 0) {
    # Once yerel sistemde kurulu mu kontrol et
    $FoundLocal = $false
    $OfficialDirs = @(
        "C:\Uyap\Uyap Kelime Islemci",
        (Join-Path ${env:ProgramFiles(x86)} "UYAP\UYAPEditor"),
        (Join-Path $env:ProgramFiles "UYAP\UYAPEditor"),
        "C:\UYAPEditor",
        "C:\Program Files\Uyap Kelime Islemci",
        (Join-Path ${env:ProgramFiles(x86)} "Uyap Kelime Islemci"),
        "$env:LOCALAPPDATA\UYAPEditorModern"
    )
    foreach ($dir in $OfficialDirs) {
        if (Test-Path "$dir\editor_lib.jar") {
            Write-Host "Yerel UYAP dosyalari bulundu: $dir, kopyalaniyor..." -ForegroundColor Green
            Copy-Item -Path "$dir\*.jar" -Destination $StagingDir -Force -ErrorAction SilentlyContinue
            Copy-Item -Path "$dir\*.ico" -Destination $StagingDir -Force -ErrorAction SilentlyContinue
            Copy-Item -Path "$dir\*.gif" -Destination $StagingDir -Force -ErrorAction SilentlyContinue
            $FoundLocal = $true
            break
        }
    }

    if (-not $FoundLocal) {
        Write-Host "Resmi UYAP MSI paketi indiriliyor..." -ForegroundColor Yellow
        $MsiPath = "$CacheDir\uki.msi"
        if (-not (Test-Path $MsiPath)) {
            curl.exe -sL "https://rayp.adalet.gov.tr/resimler/2/dosya/UKI_V5.4.20.msi" -o $MsiPath
        }
        $MsiExtractDir = "$CacheDir\msi_out"
        if (-not (Test-Path "$MsiExtractDir\editor_lib.jar")) {
            New-Item -ItemType Directory -Path $MsiExtractDir -Force | Out-Null
            Start-Process -FilePath "msiexec.exe" -ArgumentList "/a `"$MsiPath`" /qn TARGETDIR=`"$MsiExtractDir`"" -Wait
        }
        Get-ChildItem -Path $MsiExtractDir -Recurse -File -Include "*.jar","*.ico","*.gif" | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination $StagingDir -Force -ErrorAction SilentlyContinue
        }
    }
}
Write-Host "[OK] Resmi UYAP kutuphaneleri hazir." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 3. E-İmza AKİS Kütüphanesi (akisp11.dll)
# ------------------------------------------------------------------------------
Write-Host "`n[3/5] E-Imza surucu kutuphaneleri kontrol ediliyor..." -ForegroundColor Yellow
if (-not (Test-Path "$StagingDir\akisp11.dll")) {
    if (Test-Path "$env:LOCALAPPDATA\UYAPEditorModern\akisp11.dll") {
        Copy-Item "$env:LOCALAPPDATA\UYAPEditorModern\akisp11.dll" "$StagingDir\akisp11.dll" -Force
    } else {
        Write-Host "akisp11.dll indiriliyor..." -ForegroundColor Yellow
        $AkisUrl = "https://raw.githubusercontent.com/ferhat-mousavi/kamusm-akis-signature/main/akis_lib/akisp11.dll"
        curl.exe -sL $AkisUrl -o "$StagingDir\akisp11.dll"
    }
}
Write-Host "[OK] E-Imza surucusu hazir." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 4. Modernizer JAR, E-İmza Agent, Batch/VBS ve Özgün Başlatıcılar (.exe)
# ------------------------------------------------------------------------------
Write-Host "`n[4/5] Baslaticilar ve modernizer derleniyor..." -ForegroundColor Yellow
Copy-Item "$DistDir\uyap-modernizer.jar" "$StagingDir\" -Force -ErrorAction SilentlyContinue
if (Test-Path "$RootDir\build\uyap-pcsc-agent.jar") {
    Copy-Item "$RootDir\build\uyap-pcsc-agent.jar" "$StagingDir\" -Force -ErrorAction SilentlyContinue
}
Copy-Item "$ScriptDir\bin\*" "$StagingDir\" -Force

# C# ile yerel Windows GUI Calistirilabilir Dosyalari (.exe) derle
$CscPath = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$LauncherCs = "$ScriptDir\src\Launcher.cs"

if ((Test-Path $CscPath) -and (Test-Path $LauncherCs)) {
    Write-Host "UYAP Dokuman Editoru.exe derleniyor..." -ForegroundColor Yellow
    & $CscPath /target:winexe /win32icon:"$StagingDir\uyapicon.ico" /out:"$StagingDir\UYAP Dokuman Editoru.exe" $LauncherCs | Out-Null
    
    Write-Host "UYAP Sablon Editoru.exe derleniyor..." -ForegroundColor Yellow
    & $CscPath /target:winexe /define:TEMPLATE_MODE /win32icon:"$StagingDir\uyap_ki_icon.ico" /out:"$StagingDir\UYAP Sablon Editoru.exe" $LauncherCs | Out-Null
}
Write-Host "[OK] Baslatici .exe dosyalari hazir." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 5. Inno Setup ile Setup .exe Olusturma
# ------------------------------------------------------------------------------
Write-Host "`n[5/5] Inno Setup ile Kurulum Dosyasi paketleniyor..." -ForegroundColor Yellow
$IsccPaths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$Iscc = $IsccPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Iscc) {
    throw "Inno Setup (ISCC.exe) bulunamadi!"
}

& $Iscc "$ScriptDir\installer.iss"
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup derleme hatasi olustu!"
}

$SetupExe = "$DistDir\UYAP-Editor-Modern-Setup-v2.2.0.exe"
if (Test-Path $SetupExe) {
    Write-Host "`n========================================================" -ForegroundColor Green
    Write-Host " [BAŞARILI] Kurulum Paketi (.exe) Üretildi!" -ForegroundColor Green
    Write-Host " Dosya Konumu: $SetupExe" -ForegroundColor Cyan
    Write-Host "========================================================" -ForegroundColor Green
}
