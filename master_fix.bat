@echo off
REM OpenAlgo - Master Fix Script
REM This runs ALL fixes in the correct order

echo.
echo ============================================================
echo OPENALGO - MASTER FIX (ALL SERVICES, ALL MODES)
echo ============================================================
echo.
echo This will:
echo   1. Fix ALL services for event publishing
echo   2. Test all three modes (SOCKETIO, KAFKA, BOTH)
echo   3. Test all APIs
echo.
echo Press Ctrl+C to cancel, or
pause

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

REM Check directory
if not exist "services" (
    echo ERROR: Run from openalgo-stream directory!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo STEP 1: FIXING ALL SERVICES
echo ============================================================
echo.
python fix_all_services.py

if errorlevel 1 (
    echo.
    echo ERROR: Service fix failed!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo STEP 2: TESTING ALL MODES
echo ============================================================
echo.
python test_event_modes.py

if errorlevel 1 (
    echo.
    echo WARNING: Some mode tests failed
    echo Check the output above
)

echo.
echo ============================================================
echo STEP 3: TESTING ALL APIS
echo ============================================================
echo.
python test_all_apis.py

echo.
echo ============================================================
echo ✅ MASTER FIX COMPLETE!
echo ============================================================
echo.
echo 📋 Next steps:
echo.
echo 1. Edit .env to choose your mode:
echo    ORDER_EVENT_MODE='SOCKETIO'  - UI only
echo    ORDER_EVENT_MODE='KAFKA'     - External systems only
echo    ORDER_EVENT_MODE='BOTH'      - Both (RECOMMENDED)
echo.
echo 2. Restart OpenAlgo:
echo    python app.py
echo.
echo 3. Test your chosen mode:
echo    - SOCKETIO: Check browser console
echo    - KAFKA: Check Kafka consumer
echo    - BOTH: Check both!
echo.
pause
