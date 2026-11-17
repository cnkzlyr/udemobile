; UYAP Evrak Yöneticisi — Windows kurulum betiği (Inno Setup 6)
; Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.
;
; Derleme:  iscc packaging\windows\uyap_evrak.iss   (önce PyInstaller ile dist\UYAPEvrak oluşturulmalı)
; Kurulum yönetici yetkisi istemez (kullanıcı klasörüne kurulur); Python, Java (JRE), Pillow, pypdf,
; requests, websocket ve tüm bağımlılıklar paketin içindedir. Ayrı bir şey kurmak gerekmez.

#define AppName "UYAP Evrak Yöneticisi"
#define AppVersion "3.0.0"
#define AppPublisher "Av. Can KIZILYAR"
#define AppExe "UYAPEvrak.exe"

[Setup]
AppId={{6C2E7B0A-3F2D-4C1E-9B7A-5A1E0C0D0E01}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppCopyright=© 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.
VersionInfoCompany={#AppPublisher}
VersionInfoCopyright=© 2026 Av. Can KIZILYAR
VersionInfoDescription={#AppName} Kurulum
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\UYAPEvrak
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\..\dist
OutputBaseFilename=UYAPEvrak-{#AppVersion}-Windows-Kurulum
SetupIconFile=..\..\assets\uyap_evrak.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\..\LICENSE
ShowLanguageDialog=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Kısayollar:"
Name: "sagtik"; Description: "Dosyalara sağ tık > ""PDF'e dönüştür (UYAP)"" menüsünü ekle (.udf .tif .tiff .docx .doc .rtf .odt .jpg .png)"; GroupDescription: "Bütünleştirme:"

[Files]
Source: "..\..\dist\UYAPEvrak\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "© Av. Can KIZILYAR"
Name: "{group}\UYAP Evrak — Komut satırı"; Filename: "{app}\UYAPEvrakKonsol.exe"; Parameters: "--cli"
Name: "{group}\Kaldır"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\UYAPEvrakKonsol.exe"; Parameters: "--sag-tik-kur"; Flags: runhidden; Tasks: sagtik
Filename: "{app}\{#AppExe}"; Description: "{#AppName} uygulamasını başlat"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\UYAPEvrakKonsol.exe"; Parameters: "--sag-tik-kaldir"; Flags: runhidden; RunOnceId: "SagTikKaldir"
