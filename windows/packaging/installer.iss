#define AppVersion "0.11.1"
#define PackageVersion "0.11.1.1"

[Setup]
AppId={{C3C19C03-7F8E-48E4-95F3-B497EB0C6AE6}
AppName=B站数据监控
AppVersion={#AppVersion}
AppVerName=B站数据监控 {#AppVersion}（电脑版）
VersionInfoVersion={#PackageVersion}
DefaultDirName={localappdata}\Programs\BilibiliMonitor
DefaultGroupName=B站数据监控
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=no
OutputDir=..\releases\v0.11.1-installer.1
OutputBaseFilename=BilibiliMonitor-v0.11.1-installer.1-windows-x64-setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayName=B站数据监控（电脑版）
UninstallDisplayIcon={app}\BilibiliMonitor.exe
CloseApplications=yes
RestartApplications=no
InfoBeforeFile=install-guide.txt

[Languages]
Name: "chinesesimp"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: unchecked

[Files]
Source: "..\dist\BilibiliMonitor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install-guide.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\B站数据监控"; Filename: "{app}\BilibiliMonitor.exe"
Name: "{group}\卸载 B站数据监控"; Filename: "{uninstallexe}"
Name: "{group}\使用与卸载说明"; Filename: "{app}\install-guide.txt"
Name: "{group}\用户数据目录"; Filename: "{localappdata}\BilibiliMonitor\runtime-data"
Name: "{autodesktop}\B站数据监控"; Filename: "{app}\BilibiliMonitor.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BilibiliMonitor.exe"; Description: "启动 B站数据监控"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeUninstall(): Boolean;
begin
  Result := True;
  if not UninstallSilent then
    Result := MsgBox('卸载将移除程序和快捷方式。数据库、配置、日志和导出文件将保留在：' + #13#10 + ExpandConstant('{localappdata}\BilibiliMonitor\runtime-data') + #13#10 + #13#10 + '请先关闭程序。是否继续卸载？', mbConfirmation, MB_YESNO) = IDYES;
end;
