@echo off
chcp 65001 >nul
echo ========================================
echo  RoadBook v1.1.0 - Build Script (uv)
echo ========================================
echo.

:: 检查 uv
where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] uv not found.
    echo Install it first:  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    pause
    exit /b 1
)

:: 安装依赖（含 dev 组的 PyInstaller）
:: Python 版本由 .python-version 决定，uv 会自动下载，无需手工装 Python
echo [1/4] Installing dependencies...
uv sync
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo.

:: 打包
echo [2/4] Building desktop app (this may take a few minutes)...
uv run pyinstaller roadbook.spec --clean
if errorlevel 1 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)
echo.

:: Copy test photos to dist
echo [3/4] Copying test photos...
if exist "photo\for_test_only" (
    if not exist "dist\photo" mkdir "dist\photo"
    xcopy /Y /E "photo\for_test_only" "dist\photo\for_test_only\" >nul
    echo   Test photos copied
) else (
    echo   Warning: photo\for_test_only not found
)
echo.

:: Create .env with masked API keys
echo [4/4] Creating .env with masked API keys...
if exist ".env.example" (
    copy /Y ".env.example" "dist\.env" >nul
    echo   .env created with masked API keys
) else (
    echo   Warning: .env.example not found
)
echo.

:: Done
echo ========================================
echo  Build SUCCESS!
echo ========================================
echo.
echo Output: dist\roadbook.exe
echo.
echo Note:
echo   - .env has masked API keys (xxx) - replace with real keys for production
echo   - Test photos included in photo\for_test_only
echo.
pause
