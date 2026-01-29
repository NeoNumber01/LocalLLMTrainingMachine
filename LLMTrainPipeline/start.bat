@echo off
chcp 65001 >nul
title Nexus AI - Full Stack Launcher

echo.
echo ========================================================
echo     Nexus AI - Frontend/Backend One-Click Launcher (Enhanced)
echo ========================================================
echo.
echo   Startup Mode:
echo     [1] Development Mode   - Hot reload for both (for debugging)
echo     [2] Stable Mode        - No hot reload for backend (for eval/training)
echo     [3] Backend Only       - Start backend service only
echo     [4] Frontend Only      - Start frontend service only
echo.
set /p MODE=Select startup mode [1/2/3/4] (default=2): 
if "%MODE%"=="" set MODE=2

:: Get script directory
set "PROJECT_DIR=%~dp0"
echo.
echo Project directory: %PROJECT_DIR%
echo.

:: Check if backend directory exists
if not exist "%PROJECT_DIR%backend" (
    echo [Error] Cannot find backend directory!
    echo Please ensure the script is in the project root directory
    pause
    exit /b 1
)

:: ========== Backend Preparation ==========
if "%MODE%"=="4" goto :frontend_only

echo [Backend] Preparing...
cd /d "%PROJECT_DIR%backend"

if not exist "node_modules" (
    echo [Backend] Installing dependencies (first run may take a while)...
    call npm install
    if errorlevel 1 (
        echo [Error] Backend dependency installation failed!
        pause
        exit /b 1
    )
    echo [Backend] Dependencies installed
)

if not exist "node_modules\.prisma" (
    echo [Backend] Generating Prisma Client...
    call npx prisma generate
)

if not exist "prisma\dev.db" (
    echo [Backend] Initializing database...
    call npx prisma db push
    echo [Backend] Inserting seed data...
    call npx tsx src/db/seed.ts
)

:: ========== Start Backend ==========
echo [Backend] Starting service (port 3001)...
if "%MODE%"=="2" (
    echo [Backend] Using stable mode (no hot reload, suitable for long tasks)
    start "Nexus AI Backend [Stable]" cmd /k "cd /d "%PROJECT_DIR%backend" && echo Backend service starting [Stable Mode]... && npm run stable"
) else (
    echo [Backend] Using development mode (hot reload)
    start "Nexus AI Backend [Dev]" cmd /k "cd /d "%PROJECT_DIR%backend" && echo Backend service starting [Development Mode]... && npm run dev"
)

:: Wait for backend to start
echo [Backend] Waiting for service to start...
timeout /t 3 /nobreak >nul

:: Check if backend started successfully
curl -s http://localhost:3001/health >nul 2>&1
if errorlevel 1 (
    echo [Backend] Service still starting, please wait...
    timeout /t 5 /nobreak >nul
)

if "%MODE%"=="3" goto :backend_only

:frontend_only
:: ========== Frontend Preparation ==========
echo [Frontend] Preparing...
cd /d "%PROJECT_DIR%"

if not exist "node_modules" (
    echo [Frontend] Installing dependencies (first run may take a while)...
    call npm install
    if errorlevel 1 (
        echo [Error] Frontend dependency installation failed!
        pause
        exit /b 1
    )
    echo [Frontend] Dependencies installed
)

echo [Frontend] Starting development server...
start "Nexus AI Frontend" cmd /k "cd /d "%PROJECT_DIR%" && npm run dev -- --open"

:backend_only
echo.
echo ========================================================
echo   Startup Complete!
echo ========================================================
echo.
if not "%MODE%"=="4" (
    echo   Backend API:     http://localhost:3001
    echo   Swagger Docs:    http://localhost:3001/docs
    echo   Health Check:    http://localhost:3001/health
)
if not "%MODE%"=="3" (
    echo   Frontend:        Will open automatically in browser
)
echo.
if "%MODE%"=="2" (
    echo   [Stable Mode] Backend will not restart on file changes
    echo   Suitable for long-running evaluation or training tasks
)
echo.
echo   Closing this window will not stop the services
echo   Run stop.bat to stop all services
echo.
pause
