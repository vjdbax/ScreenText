#define MyAppName "ScreenText Helper"
#define MyAppVersion "5.5.0"
#define MyAppPublisher "ScreenText Helper"
#define MyAppExeName "ScreenText_v5_5.exe"

[Setup]
AppId={{B5E3A7D0-4F2C-4E8A-9D1B-3C6F5A8E2D40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=D:\!!!stream\QWEN_program\OpenCode\ScreenText_v5_3\installer
OutputBaseFilename=ScreenText_v5_5_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile=D:\!!!stream\QWEN_program\OpenCode\ScreenText_v5_3\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "D:\!!!stream\QWEN_program\OpenCode\ScreenText_v5_3\dist\ScreenText_v5_5\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\!!!stream\QWEN_program\OpenCode\ScreenText_v5_3\dist\ScreenText_v5_5\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
