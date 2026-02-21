@echo off
REM OpenAlgo Password Reset Utility - Windows Batch File
REM This script launches the password reset utility

echo.
echo ========================================
echo OpenAlgo Password Reset Utility
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python 3.11+ and try again.
    echo.
    pause
    exit /b 1
)

REM Check if we're in the correct directory
if not exist "reset_password.py" (
    echo ERROR: reset_password.py not found!
    echo Please run this script from the openalgo-stream directory.
    echo.
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist ".env" (
    echo WARNING: .env file not found!
    echo Please make sure the .env file exists with DATABASE_URL configured.
    echo.
    pause
    exit /b 1
)

REM Run the reset script
echo Starting password reset utility...
echo.
python reset_password.py

echo.
echo ========================================
echo Script completed!
echo ========================================
pause
