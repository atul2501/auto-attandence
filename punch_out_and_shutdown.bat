@echo off
title Punching out...
echo Punching out, please wait. PC will shut down after this.
cd /d "%~dp0"
python punch.py out
if errorlevel 1 (
    echo.
    echo PUNCH OUT FAILED - check punch.log. PC will NOT shut down.
    pause
    exit /b 1
)
shutdown /s /t 5
