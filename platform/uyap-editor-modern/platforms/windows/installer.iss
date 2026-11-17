; ==============================================================================
; UYAP Editör Modern - Inno Setup Kurulum Senaryosu
; Geliştirici: Can Kızılyar (github.com/cnkzlyr/uyap-editor-modern)
; ==============================================================================

#define MyAppName "UYAP Editör Modern"
#define MyAppVersion "2.2.0"
#define MyAppPublisher "Can Kızılyar"
#define MyAppURL "https://github.com/cnkzlyr/uyap-editor-modern"
#define MyAppExeName "UYAP Dokuman Editoru.exe"
#define MyAppTemplateExeName "UYAP Sablon Editoru.exe"

[Setup]
AppId={{E68A91F2-3485-4E7B-A319-1B86F2C1A801}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\UYAP Editor Modern
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\..\dist
OutputBaseFilename=UYAP-Editor-Modern-Setup-v{#MyAppVersion}
SetupIconFile=staging\uyapicon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64 arm64
ArchitecturesInstallIn64BitMode=x64 arm64
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ChangesAssociations=yes
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "fileassoc"; Description: ".udf ve .usf dosyalarını UYAP Editör Modern ile ilişkilendir"; GroupDescription: "Dosya İlişkilendirmeleri:"

[Files]
; Ana Uygulama Dosyaları
Source: "staging\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\{#MyAppTemplateExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\uyap-modernizer.jar"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\uyap-pcsc-agent.jar"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\editor_lib.jar"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\editor_lib2.jar"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\editor_utility.jar"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\editor_laf.jar"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\jai_hvl.jar"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\jdom.jar"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\updater.jar"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\akisp11.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\uyapicon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\uyap_ki_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\dokuman_editor_splash_screen_animated.gif"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\sablon_editor_splash_screen_animated.gif"; DestDir: "{app}"; Flags: ignoreversion

; Alternatif Başlatıcılar
Source: "staging\dokuman.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\dokuman.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\sablon.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\sablon.vbs"; DestDir: "{app}"; Flags: ignoreversion

; Yapılandırma Dosyaları
Source: "..\..\config\modernizer.properties"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\config\uyap.conf"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\config\modernizer.properties"; DestDir: "{%USERPROFILE}\.uki"; Flags: ignoreversion onlyifdoesntexist
Source: "..\..\config\uyap.conf"; DestDir: "{%USERPROFILE}\.uki"; Flags: ignoreversion onlyifdoesntexist

; Gömülü OpenJDK 14.0.2
Source: "staging\jdk-14.0.2\*"; DestDir: "{app}\jdk-14.0.2"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Başlat Menüsü
Name: "{group}\UYAP Doküman Editörü Modern"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\uyapicon.ico"; Comment: "UYAP Doküman Editörü Modern (120Hz & E-İmza)"
Name: "{group}\UYAP Şablon Editörü Modern"; Filename: "{app}\{#MyAppTemplateExeName}"; IconFilename: "{app}\uyap_ki_icon.ico"; Comment: "UYAP Şablon Editörü Modern (120Hz & E-İmza)"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Masaüstü
Name: "{autodesktop}\UYAP Doküman Editörü Modern"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\uyapicon.ico"; Tasks: desktopicon; Comment: "UYAP Doküman Editörü Modern (120Hz & E-İmza)"
Name: "{autodesktop}\UYAP Şablon Editörü Modern"; Filename: "{app}\{#MyAppTemplateExeName}"; IconFilename: "{app}\uyap_ki_icon.ico"; Tasks: desktopicon; Comment: "UYAP Şablon Editörü Modern (120Hz & E-İmza)"

[Registry]
; .udf İlişkilendirmesi
Root: HKA; Subkey: "Software\Classes\.udf"; ValueType: string; ValueName: ""; ValueData: "UYAP.Document.Modern"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\.udf"; ValueType: string; ValueName: "Content Type"; ValueData: "application/udf"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\.udf\OpenWithProgids"; ValueType: none; ValueName: "UYAP.Document.Modern"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\UYAP.Document.Modern"; ValueType: string; ValueName: ""; ValueData: "UYAP Dokümanı"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\UYAP.Document.Modern\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\uyapicon.ico,0"; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\UYAP.Document.Modern\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".udf"; ValueData: ""; Tasks: fileassoc

; .usf İlişkilendirmesi
Root: HKA; Subkey: "Software\Classes\.usf"; ValueType: string; ValueName: ""; ValueData: "UYAP.Template.Modern"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\.usf"; ValueType: string; ValueName: "Content Type"; ValueData: "application/usf"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\.usf\OpenWithProgids"; ValueType: none; ValueName: "UYAP.Template.Modern"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\UYAP.Template.Modern"; ValueType: string; ValueName: ""; ValueData: "UYAP Şablonu"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\UYAP.Template.Modern\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\uyap_ki_icon.ico,0"; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\UYAP.Template.Modern\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppTemplateExeName}"" ""%1"""; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppTemplateExeName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppTemplateExeName}"" ""%1"""; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppTemplateExeName}\SupportedTypes"; ValueType: string; ValueName: ".usf"; ValueData: ""; Tasks: fileassoc

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
