@echo off
echo Clearing Python cache files (fast version)...
echo.

:: Only clear cache in specific directories (not venv, node_modules, etc.)
echo Clearing services cache...
if exist "services\__pycache__" rd /s /q "services\__pycache__"

echo Clearing utils cache...
if exist "utils\__pycache__" rd /s /q "utils\__pycache__"

echo Clearing blueprints cache...
if exist "blueprints\__pycache__" rd /s /q "blueprints\__pycache__"

echo Clearing restx_api cache...
if exist "restx_api\__pycache__" rd /s /q "restx_api\__pycache__"

echo Clearing database cache...
if exist "database\__pycache__" rd /s /q "database\__pycache__"

echo Clearing broker cache...
if exist "broker\__pycache__" rd /s /q "broker\__pycache__"

echo Clearing root cache...
if exist "__pycache__" rd /s /q "__pycache__"

echo.
echo ✓ Cache cleared successfully!
echo.
echo Now restart your Flask application.
echo.
pause
