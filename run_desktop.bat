@echo off
chcp 65001 >nul
echo Starting RoadBook Desktop app (uv)...
echo.

where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] uv not found.
    echo Install it first:  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    pause
    exit /b 1
)

uv run src/desktop_app.py
pause
