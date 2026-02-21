@echo off
REM OpenAlgo Kafka Integration Fixer - Windows Batch File

echo.
echo ============================================================
echo OPENALGO KAFKA INTEGRATION FIXER
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
if not exist "services" (
    echo ERROR: services directory not found!
    echo Please run this script from the openalgo-stream directory.
    echo.
    echo Usage:
    echo   cd C:\workspace\openalgo-stream
    echo   .\fix_kafka_integration.bat
    echo.
    pause
    exit /b 1
)

REM Check if fix script exists
if not exist "fix_kafka_integration.py" (
    echo ERROR: fix_kafka_integration.py not found!
    echo Please make sure the fix script is in the current directory.
    echo.
    pause
    exit /b 1
)

REM Run the fix script
echo Running Kafka integration fixer...
echo.
python fix_kafka_integration.py

echo.
echo ============================================================
echo Script completed!
echo ============================================================
echo.
pause
