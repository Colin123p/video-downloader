; Inno-Setup-Skript fuer "Video Downloader Setup.exe"
; Installiert ohne Admin-Rechte fuer den aktuellen Benutzer.
#define AppName "Video Downloader"
#define AppVersion "1.0.2"
#define BuildDir GetEnv("VD_BUILD")

[Setup]
AppId={{6C2B8E4A-5D1F-4C8E-9A7B-3E2F1D0C9B8A}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Colin123p
AppPublisherURL=https://github.com/Colin123p/video-downloader
AppSupportURL=https://github.com/Colin123p/video-downloader/issues
InfoBeforeFile={#SourcePath}\privacy.txt
LicenseFile={#SourcePath}\..\LICENSE
DefaultDirName={localappdata}\Programs\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#SourcePath}\..\release
OutputBaseFilename=Video Downloader Setup
SetupIconFile={#SourcePath}\..\icon.ico
UninstallDisplayIcon={app}\{#AppName}.exe
UninstallDisplayName={#AppName}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern
ShowLanguageDialog=auto

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
de.AutoUpdate=Automatisch nach yt-dlp-Updates suchen (einmal am Tag bei GitHub)
en.AutoUpdate=Check for yt-dlp updates automatically (once a day on GitHub)
de.Updates=Updates:
en.Updates=Updates:

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autoupdate"; Description: "{cm:AutoUpdate}"; GroupDescription: "{cm:Updates}"

[Files]
Source: "{#BuildDir}\dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#BuildDir}\notices\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; AppUserModelID: "Colin123p.VideoDownloader"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; AppUserModelID: "Colin123p.VideoDownloader"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppName}.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\{#AppName}"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  Flag: String;
begin
  if CurStep = ssPostInstall then
  begin
    Flag := ExpandConstant('{userappdata}\{#AppName}\no-auto-update');
    ForceDirectories(ExtractFileDir(Flag));
    if WizardIsTaskSelected('autoupdate') then
      DeleteFile(Flag)
    else
      SaveStringToFile(Flag, '1', False);
  end;
end;
