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

[Files]
Source: "..\dist\EntegrasyonLive\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Satta Entegrasyon Live"; Filename: "{app}\EntegrasyonLive.exe"
Name: "{autodesktop}\Satta Entegrasyon Live"; Filename: "{app}\EntegrasyonLive.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\EntegrasyonLive.exe"; Description: "Satta Entegrasyon Live uygulamasını başlat"; Flags: nowait postinstall skipifsilent