; Inno Setup script for Windows Bar (UNVERIFIED: build on Windows with Inno Setup 6).
; Packages the PyInstaller output (dist\Windows Bar) into a per-user installer:
;   pyinstaller packaging\windowbar.spec --noconfirm
;   iscc packaging\windowbar.iss /DAppVersion=0.2.0
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{B7A5E3C4-6D2F-4C11-9E55-3F0A7D1C2B90}
AppName=Windows Bar
AppVersion={#AppVersion}
AppPublisher=gour4v97
AppPublisherURL=https://github.com/gour4v97/windowbar
DefaultDirName={localappdata}\Windows Bar
DefaultGroupName=Windows Bar
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=WindowsBar-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\Windows Bar.exe
LicenseFile=..\LICENSE

[Files]
Source: "..\dist\Windows Bar\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Windows Bar"; Filename: "{app}\Windows Bar.exe"
Name: "{userstartup}\Windows Bar"; Filename: "{app}\Windows Bar.exe"; Tasks: autostart

[Tasks]
Name: "autostart"; Description: "Start Windows Bar when I sign in"; Flags: unchecked

[Run]
Filename: "{app}\Windows Bar.exe"; Description: "Launch Windows Bar"; Flags: nowait postinstall skipifsilent
; Settings in %APPDATA%\Windows Bar are intentionally left alone on uninstall.
