@echo off
set SCRIPT_PATH=%~dp0gamma_lab.bat
set ICON_PATH=%~dp0assets\logos\app-logo.ico
set SHORTCUT_PATH=%USERPROFILE%\Desktop\Gamma Lab.lnk

powershell -command ^
"$ws = New-Object -ComObject WScript.Shell; ^
 $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); ^
 $s.TargetPath = '%SCRIPT_PATH%'; ^
 $s.WorkingDirectory = '%~dp0'; ^
 $s.IconLocation = '%ICON_PATH%'; ^
 $s.Save()"

@REM echo Acceso directo creado en el Escritorio con icono personalizado.
@REM pause
