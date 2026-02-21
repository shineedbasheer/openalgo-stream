@echo off
REM OpenAlgo BOTH Mode Diagnostic Tool

echo.
echo ============================================================
echo OPENALGO BOTH MODE DIAGNOSTIC
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    pause
    exit /b 1
)

REM Run diagnostic
python diagnose_both_mode.py

echo.
echo ============================================================
pause
