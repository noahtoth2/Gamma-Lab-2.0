@echo off
title Gamma Lab

echo Launching Gamma Lab...
echo.

REM ==========================================
REM CHECK SYSTEM PYTHON VERSION
REM ==========================================

for /f "tokens=2 delims= " %%v in ('python -V 2^>nul') do set PYV=%%v

for /f "tokens=1-3 delims=." %%a in ("%PYV%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
    set PY_PATCH=%%c
)

if "%PY_MAJOR%"=="" (
    echo [ERROR] Python not found. Install Python 3.11 or newer.
    pause
    exit /b
)

echo Python detected: %PY_MAJOR%.%PY_MINOR%.%PY_PATCH%

REM Require Python >= 3.11
if %PY_MAJOR% LSS 3 (
    echo [ERROR] Python 3.11 or newer is required.
    pause
    exit /b
)

if %PY_MAJOR%==3 if %PY_MINOR% LSS 11 (
    echo [ERROR] Python 3.11 or newer is required.
    pause
    exit /b
)

echo Python version OK.
echo.

REM ==========================================
REM ALWAYS INSTALL DEPENDENCIES
REM ==========================================

echo Installing/Checking dependencies...
pip install --upgrade pip
pip install -r requirements.txt
echo Dependencies up to date.
echo.

REM ==========================================
REM RUN APPLICATION
REM ==========================================

echo Running Gamma Lab...
python main.py
echo.

