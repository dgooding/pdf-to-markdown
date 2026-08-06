@echo off
setlocal enabledelayedexpansion
color 0A
title PDF to Markdown Converter - Ultra Portable Edition
cd /d "%~dp0"

REM ============================================================================
REM PDF to Markdown Converter - Ultra-Portable Bundle
REM Self-contained, error-proof launcher with built-in validation
REM ============================================================================

echo.
echo  PDF to Markdown Converter - Starting...
echo.

REM Check app structure
if not exist "app.py" (
    color 0C
    echo  ERROR: app.py not found. Make sure you have the complete app folder.
    echo  This file should be in the same directory as LAUNCH.bat
    pause
    exit /b 1
)
if not exist "convert_to_md.py" (
    color 0C
    echo  ERROR: convert_to_md.py not found. Make sure you have the complete app folder.
    pause
    exit /b 1
)
if not exist "wheelhouse" (
    color 0C
    echo  ERROR: wheelhouse folder not found. Dependencies missing!
    echo  Make sure the wheelhouse folder is in the same directory as this script.
    pause
    exit /b 1
)

REM Check Python installation
py --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo  ERROR: Python not found or not in PATH
    echo.
    echo  SOLUTION: Install Python 3.9 from:
    echo  https://www.python.org/downloads/release/python-3913/
    echo.
    echo  During installation, IMPORTANT:
    echo  1. Download: Windows x86-64 executable installer
    echo  2. CHECK the box: "Add Python to PATH"
    echo  3. Click Install Now
    echo.
    echo  After installation completes, run this script again.
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2 delims= " %%v in ('py --version 2^>^&1') do set PYVER=%%v
if not "!PYVER:~0,1!"=="3" (
    color 0C
    echo  ERROR: Wrong Python version detected: !PYVER!
    echo.
    echo  This app requires Python 3.9 EXACTLY
    echo  You have: !PYVER!
    echo.
    echo  SOLUTION:
    echo  - If you have multiple Python versions, uninstall the other ones
    echo  - Download Python 3.9 from: https://www.python.org/downloads/release/python-3913/
    echo  - During install, CHECK: "Add Python to PATH"
    pause
    exit /b 1
)
if not "!PYVER:~2,1!"=="9" (
    color 0C
    echo  ERROR: Wrong Python version detected: !PYVER!
    echo.
    echo  This app requires Python 3.9 EXACTLY
    echo  You have: !PYVER!
    echo.
    echo  WHY? The bundled packages ^(numpy, pandas, etc^) are compiled for Python 3.9
    echo  They will NOT work on Python 3.8, 3.10, 3.11, or 3.12
    echo.
    echo  SOLUTION: Download Python 3.9 from:
    echo  https://www.python.org/downloads/release/python-3913/
    pause
    exit /b 1
)

echo  ✓ Python 3.9 found: !PYVER!

REM Check if dependencies already installed
if exist ".installed" (
    echo  ✓ Dependencies already installed
    goto :start
)

REM First-run: Install dependencies
echo.
echo  First-run setup: Installing dependencies offline...
echo  This may take 30-60 seconds on first launch only.
echo.

py -m pip install --no-index --find-links=wheelhouse -r requirements.txt
if errorlevel 1 (
    color 0C
    echo.
    echo  ERROR: Dependency installation failed
    echo.
    echo  COMMON CAUSES:
    echo  1. Wrong Python version ^(must be 3.9 exactly^)
    echo  2. Windows 32-bit Python ^(need 64-bit^)
    echo  3. Corrupted wheelhouse folder
    echo.
    echo  SOLUTIONS:
    echo  - Verify Python version: py --version
    echo  - Reinstall Python 3.9 64-bit from: https://www.python.org/downloads/release/python-3913/
    echo  - If you modified this folder, restore from backup
    pause
    exit /b 1
)

echo installed>.installed
echo  ✓ Dependencies installed successfully!

REM ============================================================================
REM Server startup
REM ============================================================================
:start
echo.
echo  ============================================================================
echo  Starting PDF to Markdown Converter
echo  ============================================================================
echo.
echo  Web Server: http://127.0.0.1:8000
echo  Browser:   Opening automatically in 4 seconds...
echo.
echo  USAGE:
echo  1. Click "Choose File" to upload a PDF or DOCX file
echo  2. Click "Convert"
echo  3. Preview the Markdown result in the browser
echo  4. Download the Markdown or publish it to the searchable site
echo.
echo  CONVERSION STYLE:
echo  - PDF files use a visual-first conversion path with extracted text in Markdown
echo  - DOCX files preserve text and embedded visuals for MkDocs-ready output
echo.
echo  ============================================================================
echo  TROUBLESHOOTING:
echo  ============================================================================
echo.
echo  If port 8000 is already in use:
echo  1. Close any other apps using port 8000
echo  2. Edit LAUNCH.bat, change "8000" to "8001" or "8002"
echo.
echo  If browser doesn't open:
echo  1. Manually visit: http://127.0.0.1:8000
echo.
echo  If conversion fails:
echo  1. Make sure your file is not corrupted
echo  2. Try a different PDF or DOCX file
echo  3. Re-run conversion and review the packaged output
echo.
echo  To stop the server:
echo  1. Press CTRL+C in this window
echo.
echo  ============================================================================
echo.

REM Open browser (non-blocking)
start /b powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep 4; Start-Process 'http://127.0.0.1:8000'" 2>nul

REM Check if port is already in use (only LISTENING state = real conflict)
netstat -ano 2>nul | findstr ":8000 " | findstr "LISTENING" >nul
if not errorlevel 1 (
    color 0C
    echo  WARNING: Port 8000 is already in use by another process!
    echo  SOLUTION: Close the other app or change the port number in LAUNCH.bat
    echo.
)

REM Start server
color 02
py -m uvicorn app:app --host 127.0.0.1 --port 8000

color 0A
echo.
echo  Server stopped.
echo.
pause
