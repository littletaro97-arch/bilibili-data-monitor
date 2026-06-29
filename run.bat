@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m app.launcher
) else (
    echo .venv not found. Using system Python.
    python -m app.launcher
)
