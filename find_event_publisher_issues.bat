@echo off
echo Searching for event_publisher initialization issues...
echo.

findstr /s /n /c:"event_publisher = get_event_publisher()" services\*.py

echo.
echo These files need to be fixed with lazy initialization
pause
