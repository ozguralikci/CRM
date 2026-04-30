; Inno Setup script template for CRM

#define MyAppName "CRM"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "CRM"
#define MyAppExeName "CRM.exe"
#ifexist "assets\app.ico"
  #define MySetupIcon "assets\app.ico"
#endif

[Setup]
AppId={{F8BDAFA4-615D-4D20-9089-86A10B65F2A1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=release
OutputBaseFilename=CRM-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
#ifdef MySetupIcon
SetupIconFile={#MySetupIcon}
#endif
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaustu kisayolu olustur"; GroupDescription: "Ek kisayollar:"
Name: "startmenuicon"; Description: "Baslat menusu kisayolu olustur"; GroupDescription: "Ek kisayollar:"

[Files]
Source: "dist\CRM\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startmenuicon
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} uygulamasini baslat"; Flags: nowait postinstall skipifsilent
