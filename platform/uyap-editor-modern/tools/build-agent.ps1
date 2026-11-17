# ==============================================================================
# UYAP Modernizer JAR Derleme Betigi (PowerShell)
# ==============================================================================

$ErrorActionPreference = "Stop"
Write-Host "=== UYAP Modernizer JAR Derleniyor ===" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir
$BuildDir = "$RootDir\build"
$SrcDir = "$RootDir\core\src"
$DistDir = "$RootDir\dist"
$CacheDir = "$env:TEMP\uyap_build_cache"

if (-not (Test-Path "$BuildDir\classes")) { New-Item -ItemType Directory -Path "$BuildDir\classes" -Force | Out-Null }
if (-not (Test-Path $DistDir)) { New-Item -ItemType Directory -Path $DistDir -Force | Out-Null }
if (-not (Test-Path $CacheDir)) { New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null }

# 1. FlatLaf JAR temini
$FlatLafJar = "$CacheDir\flatlaf-3.5.4.jar"
if (-not (Test-Path $FlatLafJar)) {
    Write-Host "FlatLaf 3.5.4 indiriliyor..." -ForegroundColor Yellow
    curl.exe -sL -o $FlatLafJar "https://repo1.maven.org/maven2/com/formdev/flatlaf/3.5.4/flatlaf-3.5.4.jar"
}

# FlatLaf sınıflarını aç
Write-Host "FlatLaf siniflari aciliyor..." -ForegroundColor Yellow
& "C:\Program Files\7-Zip\7z.exe" x $FlatLafJar -o"$BuildDir\classes" -y | Out-Null
if (Test-Path "$BuildDir\classes\META-INF") { Remove-Item "$BuildDir\classes\META-INF" -Recurse -Force }
if (Test-Path "$BuildDir\classes\module-info.class") { Remove-Item "$BuildDir\classes\module-info.class" -Force }

# 2. İkonları kopyala
$IconsTarget = "$BuildDir\classes\icons"
if (-not (Test-Path $IconsTarget)) { New-Item -ItemType Directory -Path $IconsTarget -Force | Out-Null }
$LinuxIcons = "$RootDir\platforms\linux\icons\hicolor"
if (Test-Path $LinuxIcons) {
    foreach ($size in @(16, 32, 48, 128, 256)) {
        $srcUdf = "$LinuxIcons\${size}x${size}\mimetypes\application-udf.png"
        $srcUsf = "$LinuxIcons\${size}x${size}\mimetypes\application-usf.png"
        if (Test-Path $srcUdf) { Copy-Item $srcUdf "$IconsTarget\application-udf-$size.png" -Force }
        if (Test-Path $srcUsf) { Copy-Item $srcUsf "$IconsTarget\application-usf-$size.png" -Force }
    }
}

# 3. Java derleme
Write-Host "Kaynak kodlar derleniyor..." -ForegroundColor Yellow
$Sources = Get-ChildItem -Path $SrcDir -Recurse -Filter "*.java" | Select-Object -ExpandProperty FullName
$SourcesFile = "$BuildDir\sources.txt"
[IO.File]::WriteAllLines($SourcesFile, $Sources, [System.Text.UTF8Encoding]::new($false))

$JavaBin = "$env:LOCALAPPDATA\Programs\UYAP Editor Modern\jdk-14.0.2\bin"
if (-not (Test-Path "$JavaBin\javac.exe")) {
    $JavaBin = "C:\Users\Can\uyap-editor-modern\platforms\windows\staging\jdk-14.0.2\bin"
}

$Cp = "$BuildDir\classes"
if (Test-Path "$RootDir\platforms\windows\staging\editor_lib.jar") {
    $Cp += ";$RootDir\platforms\windows\staging\*"
}

& "$JavaBin\javac.exe" -encoding UTF-8 -cp $Cp -d "$BuildDir\classes" "@$SourcesFile"
if ($LASTEXITCODE -ne 0) { throw "javac derleme hatasi!" }

# 4. Manifest ve JAR oluşturma
Write-Host "JAR olusturuluyor..." -ForegroundColor Yellow
$ManifestContent = @"
Manifest-Version: 1.0
Premain-Class: tr.gov.uyap.modernizer.ModernizerAgent
Can-Redefine-Classes: true
Can-Retransform-Classes: true
"@
$ManifestFile = "$BuildDir\MANIFEST.MF"
[IO.File]::WriteAllText($ManifestFile, $ManifestContent.Replace("`r`n", "`n"), [System.Text.UTF8Encoding]::new($false))

$OutputJar = "$DistDir\uyap-modernizer.jar"
& "$JavaBin\jar.exe" cfm $OutputJar $ManifestFile -C "$BuildDir\classes" .
if ($LASTEXITCODE -ne 0) { throw "jar paketleme hatasi!" }

Write-Host "`n[OK] uyap-modernizer.jar basariyla derlendi: $OutputJar" -ForegroundColor Green
