@echo off
REM GigCover AI - Project Startup Script
REM This script starts all components of the GigCover platform

echo.
echo ========================================
echo   GigCover AI - Project Startup
echo ========================================
echo.

REM Check if all required directories exist
if not exist "gigcover-ai\backend" (
    echo ERROR: Backend directory not found
    exit /b 1
)

if not exist "gigcover-ai\frontend" (
    echo ERROR: Frontend directory not found
    exit /b 1
)

if not exist "gigcover_mobile" (
    echo ERROR: Mobile directory not found
    exit /b 1
)

echo [1/2] Starting Backend Server...
start cmd /k "cd gigcover-ai\backend && python app.py"
echo Backend starting on http://localhost:5000

timeout /t 2 /nobreak

echo.
echo [2/2] Starting Frontend Server...
start cmd /k "cd gigcover-ai\frontend && npm run dev"
echo Frontend starting on http://localhost:5173

echo.
echo ========================================
echo   Startup Complete!
echo ========================================
echo.
echo Web Dashboard:    http://localhost:5173
echo Backend API:      http://localhost:5000
echo.
echo Mobile APK:       gigcover_mobile\build\app\outputs\flutter-apk\app-debug.apk
echo.
echo Installation Command:
echo   adb install "gigcover_mobile\build\app\outputs\flutter-apk\app-debug.apk"
echo.
echo Press any key to continue...
pause
