[Setup]
AppName=Satta Entegrasyon Live
AppVersion=0.1.0
AppPublisher=Satta
DefaultDirName={autopf}\Satta\EntegrasyonLive
DefaultGroupName=Satta Entegrasyon Live
OutputDir=Output
OutputBaseFilename=SattaEntegrasyonLive-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\EntegrasyonLive.exe

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek görevler:"; Flags: unchecked

[Types]
Name: "full"; Description: "Tam kurulum"
Name: "custom"; Description: "Özel kurulum"; Flags: iscustom

[Components]
Name: "main"; Description: "Ana uygulama dosyaları"; Types: full custom; Flags: fixed
Name: "connector\logo"; Description: "Logo Connector"; Types: full custom; Flags: exclusive
Name: "connector\sap"; Description: "SAP Connector"; Types: custom; Flags: exclusive
Name: "connector\canias"; Description: "Canias Connector"; Types: custom; Flags: exclusive

[Files]
Source: "..\dist\EntegrasyonLive\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: main

[Icons]
Name: "{group}\Satta Entegrasyon Live"; Filename: "{app}\EntegrasyonLive.exe"
Name: "{autodesktop}\Satta Entegrasyon Live"; Filename: "{app}\EntegrasyonLive.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\EntegrasyonLive.exe"; Description: "Satta Entegrasyon Live uygulamasını başlat"; Flags: nowait postinstall skipifsilent

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

  UserDataDir := ExpandConstant('{localappdata}\Satta\EntegrasyonLive');
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