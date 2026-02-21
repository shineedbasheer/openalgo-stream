@echo off
echo Clearing Python cache files...

:: Delete all __pycache__ directories
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"

:: Delete all .pyc files
del /s /q *.pyc 2>nul

echo.
echo Cache cleared successfully!
echo.
echo Please restart your Flask application now.
echo.
pause
