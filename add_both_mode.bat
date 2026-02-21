@echo off
REM OpenAlgo - Add BOTH Mode Support

echo.
echo ============================================================
echo OPENALGO - ADD BOTH MODE SUPPORT
echo ============================================================
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
if not exist "utils" (
    echo ERROR: utils directory not found!
    echo Please run this script from the openalgo-stream directory.
    echo.
    pause
    exit /b 1
)

REM Check if script exists
if not exist "add_both_mode.py" (
    echo ERROR: add_both_mode.py not found!
    echo.
    pause
    exit /b 1
)

REM Run the script
python add_both_mode.py

echo.
echo ============================================================
echo Script completed!
echo ============================================================
pause
