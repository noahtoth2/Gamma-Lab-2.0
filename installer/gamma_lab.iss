; Instalador de Gamma Lab (R39), para todo el equipo: pide administrador,
; instala en Program Files y registra la extensión .glab en HKLM.
#define NombreApp "Gamma Lab"
#define VersionApp "2.0.0"
#define Ejecutable "GammaLab.exe"

[Setup]
; No cambiar el AppId: es lo que hace que una versión nueva reemplace a la instalada.
AppId={{B7C2F6A4-3D1E-4B8A-9C57-6E0F2A1D4C93}
AppName={#NombreApp}
AppVersion={#VersionApp}
AppPublisher=Gamma Lab
DefaultDirName={autopf}\GammaLab
DefaultGroupName={#NombreApp}
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
SetupIconFile=..\assets\logos\app-logo.ico
UninstallDisplayIcon={app}\{#Ejecutable}
OutputDir=salida
OutputBaseFilename=GammaLab-Setup-{#VersionApp}
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\GammaLab\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#NombreApp}"; Filename: "{app}\{#Ejecutable}"
Name: "{group}\{cm:UninstallProgram,{#NombreApp}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#NombreApp}"; Filename: "{app}\{#Ejecutable}"; Tasks: desktopicon

[Registry]
; .glab -> tipo de archivo -> icono y comando: el doble clic ejecuta GammaLab.exe "ruta.glab"
Root: HKA; Subkey: "Software\Classes\.glab"; ValueType: string; ValueName: ""; ValueData: "GammaLab.Project"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\GammaLab.Project"; ValueType: string; ValueName: ""; ValueData: "Gamma Lab Project"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\GammaLab.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#Ejecutable},0"
Root: HKA; Subkey: "Software\Classes\GammaLab.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#Ejecutable}"" ""%1"""

[Run]
Filename: "{app}\{#Ejecutable}"; Description: "{cm:LaunchProgram,{#NombreApp}}"; Flags: nowait postinstall skipifsilent
