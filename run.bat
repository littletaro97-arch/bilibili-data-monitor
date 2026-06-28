@echo off
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$c = Get-NetTCPConnection -LocalPort 7860 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if ($c) { exit 10 }"
if "%ERRORLEVEL%"=="10" (
    echo Port 7860 is already in use.
    echo If this app is already running, open http://127.0.0.1:7860/
    start http://127.0.0.1:7860/
    pause
    exit /b 0
)

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo .venv not found. Using system Python.
)

start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "for ($i = 0; $i -lt 30; $i++) { try { Invoke-WebRequest -Uri 'http://127.0.0.1:7860/' -UseBasicParsing -TimeoutSec 1 | Out-Null; Start-Process 'http://127.0.0.1:7860/'; exit 0 } catch { Start-Sleep -Seconds 1 } }"
python -m app.main
pause
