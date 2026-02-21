@echo off
REM OpenAlgo - Complete Fix for All Three Event Modes

echo.
echo ============================================================
echo OPENALGO - COMPLETE FIX FOR ALL THREE MODES
echo ============================================================
echo.
echo This will fix and test SOCKETIO, KAFKA, and BOTH modes
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    pause
    exit /b 1
)

if not exist "services" (
    echo ERROR: services directory not found!
    echo Please run this from the openalgo-stream directory
    pause
    exit /b 1
)

python fix_all_modes.py

echo.
echo ============================================================
pause
