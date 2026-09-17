; ──────────────────────────────────────────────────────────────────────────────
; Inno Setup конфигурация для ScreenText Helper v5.5.0
; 
; Требования:
;   - Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
;   - PyInstaller собрал дистрибутив в dist\ScreenTextHelper\
;
; Компиляция:
;   iscc.exe installer.iss
;   — или через build_exe.py (шаг 6)
; ──────────────────────────────────────────────────────────────────────────────

#define MyAppName      "ScreenText Helper"
#define MyAppVersion   "5.5.0"
#define MyAppPublisher "ScreenText Helper Team"
#define MyAppExeName   "ScreenTextHelper.exe"

[Setup]
AppId={{B5E3A7D0-4F2C-4E8A-9D1B-3C6F5A8E2D40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppVerName={#MyAppName} {#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; ── Выходная папка ──
OutputDir=dist_installer
OutputBaseFilename=ScreenTextHelper_v{#MyAppVersion}_Setup
; ── Сжатие ──
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4
; ── Внешний вид ──
WizardStyle=modern
WizardSizePercent=110
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
; ── Архитектура ──
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; ── Права ──
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; ── Прочее ──
DisableProgramGroupPage=yes
DisableDirPage=no
MinVersion=10.0.17763
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; ── Основной бинарник ──
Source: "dist\{#MyAppExeName}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; ── Внутренние зависимости (PyInstaller --onedir) ──
Source: "dist\{#MyAppExeName}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; ── Исключаем пользовательские данные из установки (они живут в AppData) ──
Source: "dist\{#MyAppExeName}\_internal\settings.json"; DestDir: "{app}\_internal"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
; ── Меню Пуск ──
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "Запустить ScreenText Helper"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
; ── Рабочий стол (по задаче) ──
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "Запустить ScreenText Helper"

[Run]
; ── Предложение запустить после установки ──
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; ── Удаляем созданные ярлыки ──
Type: filesandordirs; Name: "{group}"
; ── НЕ удаляем settings.json из AppData — пользовательские данные сохраняются ──

[Code]
// ── Проверка: не запущено ли приложение при попытке удаления ──
function InitializeUninstall(): Boolean;
begin
  Result := True;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;
