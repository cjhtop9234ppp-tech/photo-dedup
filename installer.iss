; 중복 사진 정리 도구 (PhotoDedup) - Inno Setup 설치 스크립트
; 빌드: "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" installer.iss

#define MyAppName "중복 사진 정리 도구 (PhotoDedup)"
#define MyAppVersion "1.1.4"
#define MyAppExeName "PhotoDedup.exe"

[Setup]
AppId={{8F1E9C2E-7B3A-4C5D-9E1F-2A6B8C4D7E10}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\PhotoDedup
DefaultGroupName=PhotoDedup
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=PhotoDedup_Setup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "contextmenu"; Description: "탐색기에서 zip 파일 우클릭 시 ""중복 사진 정리 도구로 열기"" 메뉴 추가 (zip의 기본 열기 동작은 바뀌지 않습니다)"; GroupDescription: "탐색기 통합"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; zip의 기본(더블클릭) 연결 프로그램은 그대로 두고, 우클릭 메뉴에 항목만 추가한다.
Root: HKCR; Subkey: "SystemFileAssociations\.zip\shell\PhotoDedup"; ValueType: string; ValueName: ""; ValueData: "중복 사진 정리 도구로 열기"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCR; Subkey: "SystemFileAssociations\.zip\shell\PhotoDedup"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: contextmenu
Root: HKCR; Subkey: "SystemFileAssociations\.zip\shell\PhotoDedup\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: contextmenu

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
