@echo off
REM Fix ALL OpenAlgo Services for Event Publishing

echo.
echo ============================================================
echo OPENALGO - FIX ALL SERVICES
echo ============================================================
echo.
echo This will fix ALL services to support three event modes:
echo   - SOCKETIO (UI only)
echo   - KAFKA (External systems only)
echo   - BOTH (UI + External systems)
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

if not exist "services" (
    echo ERROR: services directory not found!
    pause
    exit /b 1
)

python fix_all_services.py

echo.
echo ============================================================
pause
