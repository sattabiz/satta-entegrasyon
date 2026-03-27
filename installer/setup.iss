#define MyAppName "Satta Entegrasyon"
#define MyAppExeName "SattaEntegrasyon.exe"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "Satta"
#define MyAppDirName "SattaEntegrasyon"
#define MyOutputBaseFilename "SattaEntegrasyon-Setup"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Satta\{#MyAppDirName}
DefaultGroupName={#MyAppName}
OutputDir=Output
OutputBaseFilename={#MyOutputBaseFilename}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek görevler:"; Flags: unchecked

[Types]
Name: "full"; Description: "Ana Kurulum"
Name: "custom"; Description: "Özel Kurulum"; Flags: iscustom

[Components]
Name: "main"; Description: "Ana uygulama dosyaları"; Types: full custom; Flags: fixed
Name: "connector\logo"; Description: "Logo Connector"; Types: full custom; Flags: exclusive
Name: "connector\sap"; Description: "SAP Connector"; Types: custom; Flags: exclusive
Name: "connector\canias"; Description: "Canias Connector"; Types: custom; Flags: exclusive

[Files]
Source: "..\dist\SattaEntegrasyon\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: main

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} uygulamasını başlat"; Flags: nowait postinstall skipifsilent

[Code]
function GetSelectedConnector(): String;
begin
  if WizardIsComponentSelected('connector\logo') then
    Result := 'logo'
  else if WizardIsComponentSelected('connector\sap') then
    Result := 'sap'
  else if WizardIsComponentSelected('connector\canias') then
    Result := 'canias'
  else
    Result := '';
end;

procedure WriteRuntimeConfig();
var
  UserDataDir: String;
  RuntimeConfigPath: String;
  JsonText: String;
  SelectedConnector: String;
begin
  SelectedConnector := GetSelectedConnector();

  UserDataDir := ExpandConstant('{localappdata}\Satta\{#MyAppDirName}');
  if not DirExists(UserDataDir) then
    ForceDirectories(UserDataDir);

  RuntimeConfigPath := UserDataDir + '\runtime_config.json';

  if SelectedConnector = '' then
    JsonText :=
      '{'#13#10 +
      '  "active_connector": "",'#13#10 +
      '  "installed_connectors": []'#13#10 +
      '}'
  else
    JsonText :=
      '{'#13#10 +
      '  "active_connector": "' + SelectedConnector + '",'#13#10 +
      '  "installed_connectors": ["' + SelectedConnector + '"]'#13#10 +
      '}';

  SaveStringToFile(RuntimeConfigPath, JsonText, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    WriteRuntimeConfig();
end;