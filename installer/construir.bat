@echo off
rem Construye el instalador de Gamma Lab (R39): congela la aplicación y la empaqueta.
rem Uso:  installer\construir.bat      (desde cualquier carpeta)
setlocal
set RAIZ=%~dp0..
cd /d "%RAIZ%"

echo [1/3] Congelando con PyInstaller...
set PYTHONPATH=%RAIZ%\installer\precarga;%PYTHONPATH%
python -m PyInstaller installer\gamma_lab.spec --noconfirm --distpath installer\dist --workpath installer\build
if errorlevel 1 exit /b 1

echo [2/3] Prueba rapida del congelado...
python installer\prueba_congelado.py
if errorlevel 1 exit /b 1

echo [3/3] Empaquetando con Inno Setup...
set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
"%ISCC%" installer\gamma_lab.iss
if errorlevel 1 exit /b 1

echo Listo: installer\salida\
