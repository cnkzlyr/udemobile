# ==============================================================================
# UYAP Editör Modern - Windows Otomatik Kurulum ve Yapılandırma Betiği
# PowerShell 5.1+ Uyumlu (Yönetici izni gerektirmez)
# Geliştirici: Can Kızılyar (github.com/cnkzlyr/uyap-editor-modern)
# ==============================================================================

$ErrorActionPreference = "Continue"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         UYAP Editör Modern - Windows Kurulumu            " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$InstallDir = "$env:LOCALAPPDATA\UYAPEditorModern"
$CacheDir = "$env:TEMP\uyap_install_cache"

# Güvenli dizin tespiti (Doğrudan çalıştırma, ps1 dosyasından çağırma veya 'irm ... | iex' uyumlu)
if ($PSScriptRoot -and (Test-Path $PSScriptRoot)) {
    $ScriptDir = $PSScriptRoot
} elseif ($MyInvocation.MyCommand.Path -and (Test-Path $MyInvocation.MyCommand.Path)) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
} else {
    $ScriptDir = (Get-Location).Path
}

$RootDir = $null
if (Test-Path "$ScriptDir\..\..\platforms") {
    $RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
} elseif (Test-Path "$ScriptDir\platforms") {
    $RootDir = $ScriptDir
}

if (-not (Test-Path $CacheDir)) {
    New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null
}
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

# ------------------------------------------------------------------------------
# 1. Editör Dosyaları ve Betikler
# ------------------------------------------------------------------------------
Write-Host "`n[1/8] Editör dosyaları kopyalanıyor..." -ForegroundColor Yellow

$KaynakDirs = @("$ScriptDir\bin", "$ScriptDir")
if ($RootDir) { $KaynakDirs += "$RootDir\platforms\windows\bin" }
foreach ($kd in $KaynakDirs) {
    if ($kd -and (Test-Path $kd)) {
        Copy-Item -Path "$kd\*.bat","$kd\*.vbs" -Destination $InstallDir -Force -ErrorAction SilentlyContinue
    }
}

foreach ($j in @("uyap-modernizer.jar", "uyap-pcsc-agent.jar")) {
    $foundJar = $false
    $SearchDirs = @($ScriptDir, "$ScriptDir\..")
    if ($RootDir) { $SearchDirs += @("$RootDir\dist", "$RootDir\build") }
    foreach ($dir in $SearchDirs) {
        if ($dir -and (Test-Path $dir)) {
            $p = Join-Path $dir $j
            if (Test-Path $p) {
                Copy-Item -Path $p -Destination $InstallDir -Force
                $foundJar = $true
                break
            }
        }
    }
    if (-not $foundJar -and -not (Test-Path "$InstallDir\$j")) {
        Write-Host "  $j indiriliyor (GitHub)..." -ForegroundColor Yellow
        $jarUrl = "https://github.com/cnkzlyr/uyap-editor-modern/releases/download/v2.2.1/$j"
        curl.exe -fsSL "$jarUrl" -o "$InstallDir\$j"
    }
}

# ------------------------------------------------------------------------------
# 2. İkon ve Logo Dosyaları (uyapicon.ico & uyap_ki_icon.ico)
# ------------------------------------------------------------------------------
Write-Host "`n[2/8] Logo ve ikon varlıkları hazırlanıyor..." -ForegroundColor Yellow

$IconDirs = @(
    "$ScriptDir\icons",
    "$ScriptDir"
)
if ($RootDir) {
    $IconDirs += @("$RootDir\platforms\windows\icons", "$RootDir\platforms\windows")
}

foreach ($id in $IconDirs) {
    if ($id -and (Test-Path $id)) {
        Copy-Item -Path "$id\*.ico","$id\*.gif" -Destination $InstallDir -Force -ErrorAction SilentlyContinue
    }
}

# Eğer ikonlar hala yoksa GitHub raw deposundan indir
if (-not (Test-Path "$InstallDir\uyapicon.ico")) {
    Write-Host "  uyapicon.ico indiriliyor..." -ForegroundColor Yellow
    curl.exe -fsSL "https://raw.githubusercontent.com/cnkzlyr/uyap-editor-modern/main/platforms/windows/icons/uyapicon.ico" -o "$InstallDir\uyapicon.ico"
}
if (-not (Test-Path "$InstallDir\uyap_ki_icon.ico")) {
    Write-Host "  uyap_ki_icon.ico indiriliyor..." -ForegroundColor Yellow
    curl.exe -fsSL "https://raw.githubusercontent.com/cnkzlyr/uyap-editor-modern/main/platforms/windows/icons/uyap_ki_icon.ico" -o "$InstallDir\uyap_ki_icon.ico"
}

# ------------------------------------------------------------------------------
# 3. Java 14.0.2 (Paket veya İndirme)
# ------------------------------------------------------------------------------
Write-Host "`n[3/8] OpenJDK 14.0.2 kontrol ediliyor..." -ForegroundColor Yellow

$JavaDir = "$InstallDir\jdk-14.0.2"
$JavaSrc = "$ScriptDir\jdk-14.0.2"
if ((Test-Path "$JavaSrc\bin\javaw.exe") -and (-not (Test-Path "$JavaDir\bin\javaw.exe"))) {
    Copy-Item -Path $JavaSrc -Destination $InstallDir -Recurse -Force
    Write-Host "  Paketteki Java 14.0.2 kuruldu." -ForegroundColor Green
}

if (-not (Test-Path "$JavaDir\bin\javaw.exe")) {
    Write-Host "  OpenJDK 14.0.2 Windows x64 indiriliyor..." -ForegroundColor Yellow
    $JdkZip = "$CacheDir\openjdk-14.0.2_windows-x64_bin.zip"
    if (-not (Test-Path $JdkZip)) {
        $JdkUrl = "https://download.java.net/java/GA/jdk14.0.2/205943a0976c4ed48cb16f1043c5c647/12/GPL/openjdk-14.0.2_windows-x64_bin.zip"
        curl.exe -L $JdkUrl -o $JdkZip
    }
    Write-Host "  OpenJDK 14.0.2 arşivden çıkartılıyor..." -ForegroundColor Yellow
    Expand-Archive -Path $JdkZip -DestinationPath "$CacheDir\jdk_temp" -Force
    Copy-Item -Path "$CacheDir\jdk_temp\jdk-14.0.2" -Destination $InstallDir -Recurse -Force
}
Write-Host "  [OK] Java çalışma ortamı hazır." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 4. Resmi UYAP Kütüphaneleri (editor_lib.jar vb.)
# ------------------------------------------------------------------------------
Write-Host "`n[4/8] Resmi UYAP kütüphaneleri kontrol ediliyor..." -ForegroundColor Yellow

$FoundUyap = $false

# Önce paket içinde var mı kontrol et
if (Test-Path "$ScriptDir\editor_lib.jar") {
    Copy-Item -Path "$ScriptDir\*.jar" -Destination $InstallDir -Force -ErrorAction SilentlyContinue
    $FoundUyap = $true
}

# Kurulu resmi UYAP sürümlerini ara
$OfficialDirs = @(
    "C:\Uyap\Uyap Kelime Islemci",
    (Join-Path ${env:ProgramFiles(x86)} "UYAP\UYAPEditor"),
    (Join-Path $env:ProgramFiles "UYAP\UYAPEditor"),
    "C:\UYAPEditor",
    "C:\Program Files\Uyap Kelime Islemci",
    (Join-Path ${env:ProgramFiles(x86)} "Uyap Kelime Islemci")
)

# Registry üzerinde UYAP arama
$RegPaths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
)
foreach ($rp in $RegPaths) {
    try {
        Get-ItemProperty $rp -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match "UYAP|Kelime" } | ForEach-Object {
            if ($_.InstallLocation -and (Test-Path $_.InstallLocation)) {
                $OfficialDirs += $_.InstallLocation
            }
        }
    } catch {}
}

if (-not (Test-Path "$InstallDir\editor_lib.jar")) {
    foreach ($dir in $OfficialDirs) {
        if ($dir -and (Test-Path "$dir\editor_lib.jar")) {
            Write-Host "  Resmi UYAP kurulumu bulundu ($dir), kütüphaneler aktarılıyor..." -ForegroundColor Green
            Copy-Item -Path "$dir\*.jar" -Destination $InstallDir -Force -ErrorAction SilentlyContinue
            Copy-Item -Path "$dir\*.ico" -Destination $InstallDir -Force -ErrorAction SilentlyContinue
            Copy-Item -Path "$dir\*.gif" -Destination $InstallDir -Force -ErrorAction SilentlyContinue
            if (Test-Path "$dir\images") {
                Copy-Item -Path "$dir\images" -Destination $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
            }
            $FoundUyap = $true
            break
        }
    }
} else {
    $FoundUyap = $true
}

# Sistemde bulunamadıysa doğrudan resmi MSI'dan çek ve yinelemeli (recursive) ayıkla
if (-not $FoundUyap -and -not (Test-Path "$InstallDir\editor_lib.jar")) {
    Write-Host "  Resmi UYAP paketi Adalet Bakanlığı sunucusundan indiriliyor..." -ForegroundColor Yellow
    $MsiFile = "$CacheDir\uki.msi"
    if (-not (Test-Path $MsiFile)) {
        curl.exe -fsSL "https://rayp.adalet.gov.tr/resimler/2/dosya/UKI_V5.4.20.msi" -o $MsiFile
    }
    $MsiExtract = "$CacheDir\msi_out"
    if (-not (Test-Path "$MsiExtract\editor_lib.jar")) {
        New-Item -ItemType Directory -Path $MsiExtract -Force | Out-Null
        Write-Host "  MSI paketi açılıyor..." -ForegroundColor Yellow
        Start-Process -FilePath "msiexec.exe" -ArgumentList "/a `"$MsiFile`" /qn TARGETDIR=`"$MsiExtract`"" -Wait
    }
    # Tüm alt klasörleri de tarayarak kopyala
    Get-ChildItem -Path $MsiExtract -Recurse -File -Include "*.jar","*.ico","*.gif" -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $InstallDir -Force -ErrorAction SilentlyContinue
    }
}

if (Test-Path "$InstallDir\editor_lib.jar") {
    Write-Host "  [OK] Resmi UYAP kütüphaneleri hazır." -ForegroundColor Green
} else {
    Write-Host "  [UYARI] editor_lib.jar bulunamadı. Resmi UYAP kurulu değilse açılışta hata verebilir." -ForegroundColor DarkYellow
}

# ------------------------------------------------------------------------------
# 5. E-İmza Sürücüsü (akisp11.dll)
# ------------------------------------------------------------------------------
Write-Host "`n[5/8] E-İmza sürücü kütüphaneleri (AKİS) hazırlanıyor..." -ForegroundColor Yellow
if (-not (Test-Path "$InstallDir\akisp11.dll")) {
    $SysAkis = "$env:SystemRoot\System32\akisp11.dll"
    $SysAkis64 = "$env:SystemRoot\SysWOW64\akisp11.dll"
    if (Test-Path $SysAkis) {
        Copy-Item $SysAkis "$InstallDir\akisp11.dll" -Force
    } elseif (Test-Path $SysAkis64) {
        Copy-Item $SysAkis64 "$InstallDir\akisp11.dll" -Force
    } else {
        $AkisUrl = "https://raw.githubusercontent.com/ferhat-mousavi/kamusm-akis-signature/main/akis_lib/akisp11.dll"
        curl.exe -fsSL $AkisUrl -o "$InstallDir\akisp11.dll" -ErrorAction SilentlyContinue
    }
}
Write-Host "  [OK] E-imza sürücüsü hazır." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 6. Özgün Yerel Başlatıcıları (.exe) Derleme
# ------------------------------------------------------------------------------
Write-Host "`n[6/8] Yerel Windows Başlatıcıları (.exe) derleniyor..." -ForegroundColor Yellow

$CscPaths = @(
    "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)
$CscPath = $CscPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

$LauncherCs = "$InstallDir\Launcher.cs"
# Launcher.cs dosyasını sağla
$FoundCs = $false
foreach ($cand in @("$ScriptDir\src\Launcher.cs", "$ScriptDir\Launcher.cs", "$RootDir\platforms\windows\src\Launcher.cs")) {
    if (Test-Path $cand) {
        Copy-Item $cand $LauncherCs -Force
        $FoundCs = $true
        break
    }
}

if (-not $FoundCs) {
    # Launcher.cs'yi dahili şablondan oluştur
    $EmbeddedCs = @'
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

namespace UYAPLauncher
{
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
                string javaCmd = Path.Combine(baseDir, @"jdk-14.0.2\bin\javaw.exe");
                if (!File.Exists(javaCmd))
                {
                    string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                    string altJava = Path.Combine(localAppData, @"Programs\UYAP Editor Modern\jdk-14.0.2\bin\javaw.exe");
                    if (File.Exists(altJava)) javaCmd = altJava;
                    else
                    {
                        altJava = Path.Combine(localAppData, @"UYAPEditorModern\jdk-14.0.2\bin\javaw.exe");
                        if (File.Exists(altJava)) javaCmd = altJava;
                        else javaCmd = "javaw.exe";
                    }
                }

                string modernizerJar = Path.Combine(baseDir, "uyap-modernizer.jar");
                string pcscJar = Path.Combine(baseDir, "uyap-pcsc-agent.jar");
                StringBuilder agentOpts = new StringBuilder();
                if (File.Exists(modernizerJar)) agentOpts.AppendFormat("-javaagent:\"{0}\" ", modernizerJar);
                if (File.Exists(pcscJar)) agentOpts.AppendFormat("-javaagent:\"{0}\" ", pcscJar);

                string cpOpt;
                string editorLib = Path.Combine(baseDir, "editor_lib.jar");
                if (File.Exists(editorLib))
                {
                    cpOpt = string.Format("-cp \"{0}\\uyap-modernizer.jar;{0}\\*\"", baseDir);
                }
                else
                {
                    string[] candidateDirs = new string[] {
                        @"C:\Uyap\Uyap Kelime Islemci",
                        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), @"UYAP\UYAPEditor"),
                        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), @"UYAP\UYAPEditor"),
                        @"C:\UYAPEditor",
                        @"C:\Program Files\Uyap Kelime Islemci",
                        @"C:\Program Files (x86)\Uyap Kelime Islemci"
                    };
                    string foundDir = null;
                    foreach (string d in candidateDirs)
                    {
                        if (Directory.Exists(d) && File.Exists(Path.Combine(d, "editor_lib.jar")))
                        {
                            foundDir = d;
                            break;
                        }
                    }
                    if (foundDir != null)
                    {
                        cpOpt = string.Format("-cp \"{0}\\uyap-modernizer.jar;{0}\\*;{1}\\*\"", baseDir, foundDir);
                    }
                    else
                    {
                        MessageBox.Show("Resmi UYAP kütüphaneleri (editor_lib.jar) bulunamadı!\n\nLütfen 'install.ps1' kurulum betiğini çalıştırın veya resmi UYAP Editör'ü kurun.", "UYAP Editör Modern", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                        return;
                    }
                }

                string sysRoot = Environment.GetEnvironmentVariable("SystemRoot");
                if (string.IsNullOrEmpty(sysRoot)) sysRoot = @"C:\Windows";
                string pkcs11Opts = string.Format("-Djava.library.path=\"{0};{1}\\System32;{1}\\SysWOW64\"", baseDir, sysRoot);
                string fontOpts = "-Dawt.useSystemAAFontSettings=lcd -Dswing.aatext=true";
                string memOpts = "-Xms256m -Xmx1024m -XX:+UseG1GC -XX:+UseStringDeduplication";

                string userProfile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
                string ukiDir = Path.Combine(userProfile, ".uki");
                if (!Directory.Exists(ukiDir)) { try { Directory.CreateDirectory(ukiDir); } catch {} }

                #if TEMPLATE_MODE
                string editorType = "EDITOR_TYPE_TEMPLATE";
                #else
                string editorType = "EDITOR_TYPE_DOCUMENT";
                #endif

                StringBuilder sb = new StringBuilder();
                sb.Append(pkcs11Opts).Append(" ").Append(memOpts).Append(" ").Append(fontOpts).Append(" ");
                if (agentOpts.Length > 0) sb.Append(agentOpts.ToString());
                sb.Append(cpOpt).Append(" tr.com.havelsan.uyap.system.editor.common.WPAppManager \"getNewWPInstance\" ");

                if (args.Length > 0 && !string.IsNullOrEmpty(args[0]))
                {
                    string target = args[0].Trim('\"');
                    if (target.EndsWith(".usf", StringComparison.OrdinalIgnoreCase)) editorType = "EDITOR_TYPE_TEMPLATE";
                    else if (target.EndsWith(".udf", StringComparison.OrdinalIgnoreCase)) editorType = "EDITOR_TYPE_DOCUMENT";
                    sb.Append("\"").Append(editorType).Append("\" \"").Append(target).Append("\"");
                }
                else
                {
                    sb.Append("\"").Append(editorType).Append("\"");
                }

                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = javaCmd;
                psi.Arguments = sb.ToString();
                psi.WorkingDirectory = baseDir;
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;
                Process.Start(psi);
            }
            catch (Exception ex)
            {
                MessageBox.Show("UYAP Editör Modern başlatılamadı:\n\n" + ex.Message, "UYAP Editör Modern", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }
}
'@
    Set-Content -Path $LauncherCs -Value $EmbeddedCs -Encoding UTF8
}

$DokumanExe = "$InstallDir\UYAP Dokuman Editoru.exe"
$SablonExe = "$InstallDir\UYAP Sablon Editoru.exe"
$DocIco = "$InstallDir\uyapicon.ico"
$TplIco = "$InstallDir\uyap_ki_icon.ico"

if ($CscPath -and (Test-Path $LauncherCs)) {
    Write-Host "  UYAP Dokuman Editoru.exe derleniyor..." -ForegroundColor Yellow
    $iconArg = if (Test-Path $DocIco) { "/win32icon:`"$DocIco`"" } else { "" }
    & $CscPath /target:winexe $iconArg /out:"$DokumanExe" "$LauncherCs" | Out-Null

    Write-Host "  UYAP Sablon Editoru.exe derleniyor..." -ForegroundColor Yellow
    $tplIconArg = if (Test-Path $TplIco) { "/win32icon:`"$TplIco`"" } else { "" }
    & $CscPath /target:winexe /define:TEMPLATE_MODE $tplIconArg /out:"$SablonExe" "$LauncherCs" | Out-Null
    Write-Host "  [OK] Yerel .exe başlatıcıları başarıyla derlendi." -ForegroundColor Green
} else {
    Write-Host "  [BİLGİ] csc.exe bulunamadı; VBS başlatıcıları kullanılacak." -ForegroundColor DarkYellow
}

# ------------------------------------------------------------------------------
# 7. Başlat Menüsü ve Masaüstü Kısayolları (Logolu)
# ------------------------------------------------------------------------------
Write-Host "`n[7/8] Başlat Menüsü ve Masaüstü kısayolları oluşturuluyor..." -ForegroundColor Yellow

$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ProgramsPath = [Environment]::GetFolderPath("Programs")
$StartMenuAppDir = Join-Path $ProgramsPath "UYAP Editör Modern"
if (-not (Test-Path $StartMenuAppDir)) {
    New-Item -ItemType Directory -Path $StartMenuAppDir -Force | Out-Null
}

$Targets = @{
    "Dokuman" = @{
        "Name" = "UYAP Doküman Editörü Modern"
        "Exe"  = if (Test-Path $DokumanExe) { $DokumanExe } else { "wscript.exe" }
        "Args" = if (Test-Path $DokumanExe) { "" } else { """$InstallDir\dokuman.vbs""" }
        "Icon" = if (Test-Path $DocIco) { $DocIco } else { "" }
        "Desc" = "UYAP Doküman Editörü Modern (120Hz & E-İmza)"
    };
    "Sablon" = @{
        "Name" = "UYAP Şablon Editörü Modern"
        "Exe"  = if (Test-Path $SablonExe) { $SablonExe } else { "wscript.exe" }
        "Args" = if (Test-Path $SablonExe) { "" } else { """$InstallDir\sablon.vbs""" }
        "Icon" = if (Test-Path $TplIco) { $TplIco } else { "" }
        "Desc" = "UYAP Şablon Editörü Modern (120Hz & E-İmza)"
    }
}

foreach ($key in $Targets.Keys) {
    $t = $Targets[$key]
    
    # 1. Masaüstü Kısayolu
    $sDesktop = $WshShell.CreateShortcut((Join-Path $DesktopPath "$($t.Name).lnk"))
    $sDesktop.TargetPath = $t.Exe
    if ($t.Args) { $sDesktop.Arguments = $t.Args }
    if ($t.Icon) { $sDesktop.IconLocation = "$($t.Icon),0" }
    $sDesktop.WorkingDirectory = $InstallDir
    $sDesktop.Description = $t.Desc
    $sDesktop.Save()

    # 2. Başlat Menüsü (Doğrudan Programs köküne - Windows Arama'da anında görünür)
    $sMenuRoot = $WshShell.CreateShortcut((Join-Path $ProgramsPath "$($t.Name).lnk"))
    $sMenuRoot.TargetPath = $t.Exe
    if ($t.Args) { $sMenuRoot.Arguments = $t.Args }
    if ($t.Icon) { $sMenuRoot.IconLocation = "$($t.Icon),0" }
    $sMenuRoot.WorkingDirectory = $InstallDir
    $sMenuRoot.Description = $t.Desc
    $sMenuRoot.Save()

    # 3. Başlat Menüsü (UYAP Editör Modern klasörü içi)
    $sMenuFolder = $WshShell.CreateShortcut((Join-Path $StartMenuAppDir "$($t.Name).lnk"))
    $sMenuFolder.TargetPath = $t.Exe
    if ($t.Args) { $sMenuFolder.Arguments = $t.Args }
    if ($t.Icon) { $sMenuFolder.IconLocation = "$($t.Icon),0" }
    $sMenuFolder.WorkingDirectory = $InstallDir
    $sMenuFolder.Description = $t.Desc
    $sMenuFolder.Save()
}

# Kaldırma kısayolu ve scripti
$UninstallPs1 = "$InstallDir\uninstall.ps1"
$UninstallContent = @"
# UYAP Editör Modern Kaldırma Betiği
Write-Host "UYAP Editör Modern sistemden kaldırılıyor..." -ForegroundColor Yellow
`$InstallDir = "$InstallDir"
`$Desktop = [Environment]::GetFolderPath("Desktop")
`$Programs = [Environment]::GetFolderPath("Programs")

Remove-Item "`$Desktop\UYAP Doküman Editörü Modern.lnk" -Force -ErrorAction SilentlyContinue
Remove-Item "`$Desktop\UYAP Şablon Editörü Modern.lnk" -Force -ErrorAction SilentlyContinue
Remove-Item "`$Programs\UYAP Doküman Editörü Modern.lnk" -Force -ErrorAction SilentlyContinue
Remove-Item "`$Programs\UYAP Şablon Editörü Modern.lnk" -Force -ErrorAction SilentlyContinue
Remove-Item "`$Programs\UYAP Editör Modern" -Recurse -Force -ErrorAction SilentlyContinue

Remove-Item "HKCU:\Software\Classes\.udf" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "HKCU:\Software\Classes\.usf" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "HKCU:\Software\Classes\UYAP.Document.Modern" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "HKCU:\Software\Classes\UYAP.Template.Modern" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\UYAPEditorModern" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Kaldırma tamamlandı." -ForegroundColor Green
"@
Set-Content -Path $UninstallPs1 -Value $UninstallContent -Encoding UTF8

$sUninst = $WshShell.CreateShortcut((Join-Path $StartMenuAppDir "UYAP Editör Modern Kaldır.lnk"))
$sUninst.TargetPath = "powershell.exe"
$sUninst.Arguments = "-ExecutionPolicy Bypass -NoProfile -File `"$UninstallPs1`""
$sUninst.WorkingDirectory = $InstallDir
$sUninst.Description = "UYAP Editör Modern Programını Kaldır"
$sUninst.Save()

# Windows 'Kurulu Programlar' (Apps & Features) kaydı
$UninstRegKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\UYAPEditorModern"
if (-not (Test-Path $UninstRegKey)) {
    New-Item -Path $UninstRegKey -Force | Out-Null
}
Set-ItemProperty -Path $UninstRegKey -Name "DisplayName" -Value "UYAP Editör Modern" -Force
Set-ItemProperty -Path $UninstRegKey -Name "DisplayVersion" -Value "2.2.0" -Force
Set-ItemProperty -Path $UninstRegKey -Name "Publisher" -Value "Can Kızılyar" -Force
Set-ItemProperty -Path $UninstRegKey -Name "InstallLocation" -Value $InstallDir -Force
Set-ItemProperty -Path $UninstRegKey -Name "DisplayIcon" -Value "$DocIco,0" -Force
Set-ItemProperty -Path $UninstRegKey -Name "UninstallString" -Value "powershell.exe -ExecutionPolicy Bypass -NoProfile -File `"$UninstallPs1`"" -Force
Set-ItemProperty -Path $UninstRegKey -Name "URLInfoAbout" -Value "https://github.com/cnkzlyr/uyap-editor-modern" -Force

Write-Host "  [OK] Başlat Menüsü ve Masaüstü simgeleri oluşturuldu." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 8. .udf ve .usf Dosya İlişkilendirmesi (Kullanıcı Düzeyi - Yönetici İzni Gerekmez)
# ------------------------------------------------------------------------------
Write-Host "`n[8/8] .udf ve .usf dosya ilişkilendirmeleri yapılıyor..." -ForegroundColor Yellow

$DocOpenCmd = if (Test-Path $DokumanExe) { "`"$DokumanExe`" `"%1`"" } else { "wscript.exe `"$InstallDir\dokuman.vbs`" `"%1`"" }
$TplOpenCmd = if (Test-Path $SablonExe) { "`"$SablonExe`" `"%1`"" } else { "wscript.exe `"$InstallDir\sablon.vbs`" `"%1`"" }

# 1) .udf İlişkilendirmesi
$null = New-Item -Path "HKCU:\Software\Classes\.udf" -Value "UYAP.Document.Modern" -Force
$null = New-Item -Path "HKCU:\Software\Classes\.udf\OpenWithProgids" -Force
Set-ItemProperty -Path "HKCU:\Software\Classes\.udf\OpenWithProgids" -Name "UYAP.Document.Modern" -Value ([byte[]]@()) -Force
Set-ItemProperty -Path "HKCU:\Software\Classes\.udf" -Name "Content Type" -Value "application/udf" -Force

$null = New-Item -Path "HKCU:\Software\Classes\UYAP.Document.Modern" -Value "UYAP Dokümanı" -Force
$null = New-Item -Path "HKCU:\Software\Classes\UYAP.Document.Modern\DefaultIcon" -Value "$DocIco,0" -Force
$null = New-Item -Path "HKCU:\Software\Classes\UYAP.Document.Modern\shell\open\command" -Value $DocOpenCmd -Force

# 2) .usf İlişkilendirmesi
$null = New-Item -Path "HKCU:\Software\Classes\.usf" -Value "UYAP.Template.Modern" -Force
$null = New-Item -Path "HKCU:\Software\Classes\.usf\OpenWithProgids" -Force
Set-ItemProperty -Path "HKCU:\Software\Classes\.usf\OpenWithProgids" -Name "UYAP.Template.Modern" -Value ([byte[]]@()) -Force
Set-ItemProperty -Path "HKCU:\Software\Classes\.usf" -Name "Content Type" -Value "application/usf" -Force

$null = New-Item -Path "HKCU:\Software\Classes\UYAP.Template.Modern" -Value "UYAP Şablonu" -Force
$null = New-Item -Path "HKCU:\Software\Classes\UYAP.Template.Modern\DefaultIcon" -Value "$TplIco,0" -Force
$null = New-Item -Path "HKCU:\Software\Classes\UYAP.Template.Modern\shell\open\command" -Value $TplOpenCmd -Force

# 3) Applications listesi (Birlikte Aç menüsü için)
if (Test-Path $DokumanExe) {
    $null = New-Item -Path "HKCU:\Software\Classes\Applications\UYAP Dokuman Editoru.exe\shell\open\command" -Value $DocOpenCmd -Force
    $null = New-Item -Path "HKCU:\Software\Classes\Applications\UYAP Dokuman Editoru.exe\SupportedTypes" -Force
    Set-ItemProperty -Path "HKCU:\Software\Classes\Applications\UYAP Dokuman Editoru.exe\SupportedTypes" -Name ".udf" -Value "" -Force
}
if (Test-Path $SablonExe) {
    $null = New-Item -Path "HKCU:\Software\Classes\Applications\UYAP Sablon Editoru.exe\shell\open\command" -Value $TplOpenCmd -Force
    $null = New-Item -Path "HKCU:\Software\Classes\Applications\UYAP Sablon Editoru.exe\SupportedTypes" -Force
    Set-ItemProperty -Path "HKCU:\Software\Classes\Applications\UYAP Sablon Editoru.exe\SupportedTypes" -Name ".usf" -Value "" -Force
}

# 4) Varsa eski / çakışan Explorer UserChoice seçimlerini temizle
Remove-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.udf\UserChoice" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.usf\UserChoice" -Recurse -Force -ErrorAction SilentlyContinue

# Windows Shell / İkon Önbelleğini Yenile
try {
    $code = @'
    [System.Runtime.InteropServices.DllImport("shell32.dll")]
    public static extern void SHChangeNotify(int wEventId, int uFlags, IntPtr dwItem1, IntPtr dwItem2);
'@
    $type = Add-Type -MemberDefinition $code -Name "ShellNotification" -Namespace "Win32" -PassThru -ErrorAction SilentlyContinue
    if ($type) {
        $type::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)
    }
} catch {}

Write-Host "  [OK] .udf ve .usf dosyaları UYAP Editör Modern ile ilişkilendirildi." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 9. Profil ve Yapılandırma Dosyaları (.uki)
# ------------------------------------------------------------------------------
$UkiDir = "$env:USERPROFILE\.uki"
if (-not (Test-Path $UkiDir)) {
    New-Item -ItemType Directory -Path $UkiDir -Force | Out-Null
}

$ConfigDirs = @("$ScriptDir\config", "$ScriptDir")
if ($RootDir) { $ConfigDirs += "$RootDir\config" }
foreach ($cd in $ConfigDirs) {
    if ($cd -and (Test-Path "$cd\modernizer.properties")) {
        if (-not (Test-Path "$UkiDir\modernizer.properties")) {
            Copy-Item "$cd\modernizer.properties" "$UkiDir\" -Force
        }
        Copy-Item "$cd\modernizer.properties" "$InstallDir\" -Force
    }
    if (Test-Path "$cd\uyap.conf") {
        if (-not (Test-Path "$UkiDir\uyap.conf")) {
            Copy-Item "$cd\uyap.conf" "$UkiDir\" -Force
        }
        Copy-Item "$cd\uyap.conf" "$InstallDir\" -Force
    }
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host " [BAŞARILI] UYAP Editör Modern kurulumu tamamlandı!" -ForegroundColor Green
Write-Host " - Başlat Menüsü: 'UYAP Doküman Editörü Modern' olarak eklendi." -ForegroundColor Cyan
Write-Host " - Masaüstü: Logolu kısayollar oluşturuldu." -ForegroundColor Cyan
Write-Host " - Dosyalar: .udf ve .usf dosyaları doğrudan editörle açılacak." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
