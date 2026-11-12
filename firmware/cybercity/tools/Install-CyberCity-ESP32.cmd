@echo off
setlocal
title LabTech Cyber City - ESP32 Firmware Installer
cd /d "%~dp0"
echo LabTech Cyber City - ESP32 Firmware Setup
echo Extract the ZIP fully, connect your ESP32 with USB, and close Thonny.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-CyberCity-ESP32.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" (
  echo Installation was not completed. Review the error above.
) else (
  echo Setup finished. Use the MicroPython console to start device_startup.run().
)
echo.
pause
exit /b %RESULT%
