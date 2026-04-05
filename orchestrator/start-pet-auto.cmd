@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0start-pet.ps1" -Mode auto
if errorlevel 1 (
  echo.
  echo STS2 pet auto start failed.
  echo Press any key to close this window.
  pause >nul
)
