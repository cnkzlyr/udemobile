# CanEditor - Windows'ta derle ve GitHub Release'e yükle (GitHub Actions gerekmez)
# Kullanım: PowerShell'de  .\scripts\windows_yayin.ps1   (depo kökünden)
# Ne yapar: eksik araçları kurar -> gömülü Java + asistan sunucusu + görünmez Chrome -> Tauri (exe, msi)
#           -> taşınabilir web zip + (Android SDK varsa) APK -> gh ile v4.0.0 sürümünü oluşturup dosyaları yükler.
# Not: Windows PowerShell yerel komutların stderr çıktısını hata sanabildiği için ErrorActionPreference
#      'Continue' tutulur; her yerel komutun çıkış kodu Calistir ile ayrıca denetlenir.
param([string]$Surum = "4.0.0")
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$Kok = Split-Path -Parent $PSScriptRoot
Set-Location $Kok

function Adim($m) { Write-Host ""; Write-Host "==> $m" -ForegroundColor Cyan }
function YoluYenile {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User") + ";$env:USERPROFILE\.cargo\bin"
}
function Calistir {
    & $args[0] $args[1..($args.Count - 1)]
    if ($LASTEXITCODE -ne 0) { throw "Komut başarısız ($LASTEXITCODE): $($args -join ' ')" }
}
function Kur($Id, $Komut, $Ek = @()) {
    if (Get-Command $Komut -ErrorAction SilentlyContinue) { return }
    Write-Host "   kuruluyor: $Id"
    winget install --id $Id -e --accept-source-agreements --accept-package-agreements --silent @Ek | Out-Null
    YoluYenile
}

Adim "1/6 Araçlar (yalnızca eksik olanlar kurulur)"
Kur "Git.Git" "git"
Kur "OpenJS.NodeJS.LTS" "node"
# "python" Microsoft Store kısayolu olabilir: gerçekten çalışıyor mu bakılır
python -c "import sys" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "   kuruluyor: Python.Python.3.12"
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements --silent | Out-Null
    YoluYenile
}
# Başka bir JDK (ör. 14) kurulu olsa da gömülü Java için JDK 21 gerekir
if (-not (Get-ChildItem "$env:ProgramFiles\Eclipse Adoptium" -Directory -ErrorAction SilentlyContinue | Where-Object Name -like "jdk-21*")) {
    Write-Host "   kuruluyor: EclipseAdoptium.Temurin.21.JDK"
    winget install --id EclipseAdoptium.Temurin.21.JDK -e --accept-source-agreements --accept-package-agreements --silent | Out-Null
}
Kur "GitHub.cli" "gh"
Kur "Rustlang.Rustup" "rustup"
if (-not (Test-Path "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\VC")) {
    Write-Host "   kuruluyor: Visual Studio C++ derleme araçları (Rust için gerekli, ~10 dk)"
    winget install --id Microsoft.VisualStudio.2022.BuildTools -e --accept-source-agreements --accept-package-agreements --silent `
        --override "--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended" | Out-Null
}
YoluYenile
Calistir rustup default stable
$jdk = Get-ChildItem "$env:ProgramFiles\Eclipse Adoptium" -Directory -ErrorAction SilentlyContinue | Where-Object Name -like "jdk-21*" | Select-Object -First 1
if (-not $jdk) { throw "JDK 21 bulunamadı (Eclipse Adoptium)" }
$env:JAVA_HOME = $jdk.FullName
$env:Path = "$env:JAVA_HOME\bin;$env:Path"

Adim "2/6 GitHub girişi (tarayıcı açılırsa onaylayın)"
gh auth status 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Calistir gh auth login --hostname github.com --git-protocol https --web }

Adim "3/6 Gömülü Java + Hukuk Asistanı sunucusu + görünmez Chrome"
Calistir python -m pip install --upgrade pip
Calistir python -m pip install -r asistan/requirements.txt pyinstaller
Calistir python scripts/masaustu_hazirla.py --java-home $env:JAVA_HOME
Calistir python scripts/win_ajan_derle.py

Adim "4/6 Windows kurulum dosyaları (Tauri: .exe + .msi, ~15-25 dk)"
Calistir npm install
Push-Location frontend
Calistir npm install
Calistir npm run build
Pop-Location
npx tauri build
if ($LASTEXITCODE -ne 0) {
    # Windows 11 24H2'de VBScript kapalıysa MSI (WiX) derlenemez: yalnız .exe kurulumuyla devam
    Write-Host "   MSI derlenemedi; yalnız .exe kurulum dosyası derleniyor." -ForegroundColor Yellow
    Calistir npx tauri build --bundles nsis
}

Adim "5/6 Taşınabilir web zip + Android APK (Android SDK yoksa APK atlanır)"
$env:CANEDITOR_ASISTAN_ANDROID = "0"
New-Item -ItemType Directory -Force release | Out-Null   # seyrek klonda release/ indirilmez
python scripts/pack_release.py
if ($LASTEXITCODE -ne 0) { Write-Host "   APK üretilemedi (Android SDK / imza anahtarı yok olabilir); masaüstü paketleriyle devam." -ForegroundColor Yellow }

Adim "6/6 GitHub Release v$Surum"
$dosyalar = @()
$dosyalar += Get-ChildItem "src-tauri\target\release\bundle\nsis\*_${Surum}_*setup.exe" -ErrorAction SilentlyContinue
$dosyalar += Get-ChildItem "src-tauri\target\release\bundle\msi\*_${Surum}_*.msi" -ErrorAction SilentlyContinue
foreach ($ad in @("CanEditor-Portable-Web-GUI-v$Surum.zip", "CanEditor-v$Surum.apk")) {
    if (Test-Path "release\$ad") { $dosyalar += Get-Item "release\$ad" }
}
if (Test-Path "release\CanEditor-v$Surum.apk") {
    Copy-Item "release\CanEditor-v$Surum.apk" "$env:TEMP\CanEditor-latest.apk" -Force
    $dosyalar += Get-Item "$env:TEMP\CanEditor-latest.apk"
}
if (-not ($dosyalar | Where-Object Name -like "*.exe")) { throw "Windows kurulum dosyası üretilmedi" }
$dosyalar | ForEach-Object { Write-Host ("   " + $_.Name + "  (" + [math]::Round($_.Length / 1MB) + " MB)") }
$notlar = @"
CanEditor v$Surum — Editör + Hukuk Asistanı tek uygulamada.

Kurulum paketi her şeyi içinde taşır: Python, Java, görünmez Chrome ve sürücüsüz e-imza altyapısı.
- Yasal süre hesabı, A4 PDF birleştirici, ajanda, UYAP evrak arama, UETS/UYAP görevleri (Asistan menüsü, Ctrl+K)
- UYAP oturumu: e-imza kartı takılıysa e-imza; değilse ya da bağlantı koparsa bağlanana kadar Mobil İmza
- Android: asistan Termux gerektirmez

Windows: CanEditor_${Surum}_x64-setup.exe (SmartScreen: "Ek bilgi" -> "Yine de çalıştır") veya .msi
"@
$yollar = [string[]]($dosyalar | ForEach-Object { $_.FullName })
gh release view "v$Surum" 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    gh release upload "v$Surum" $yollar --clobber
} else {
    gh release create "v$Surum" $yollar --target main --title "CanEditor v$Surum" --notes $notlar
}
if ($LASTEXITCODE -ne 0) { throw "GitHub Release oluşturulamadı / dosyalar yüklenemedi" }
Write-Host ""
Write-Host "TAMAM: https://github.com/cnkzlyr/udemobile/releases/tag/v$Surum" -ForegroundColor Green
