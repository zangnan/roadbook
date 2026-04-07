@echo off
chcp 65001 >nul
echo ========================================
echo  RoadBook - Build Script
echo ========================================
echo.

:: Use Python 3.11
set PYTHON=C:\Users\zangnan\AppData\Local\Programs\Python\Python311\python.exe

:: Check Python exists
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found at: %PYTHON%
    echo Please check your Python 3.11 installation
    pause
    exit /b 1
)

:: Install dependencies
echo [1/4] Installing dependencies...
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo.

:: Build
echo [2/4] Building desktop app (this may take a few minutes)...
%PYTHON% -m PyInstaller roadbook.spec --clean
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
