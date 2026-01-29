@echo off
chcp 65001 >nul
title Nexus AI - Stable Mode Quick Start

echo.
echo ========================================================
echo     Nexus AI - Quick Start (Stable Mode)
echo ========================================================
echo.
echo   Suitable for long-running evaluation/training tasks
echo   Backend will not restart on file changes
echo.

:: Get script directory
set "PROJECT_DIR=%~dp0"

:: Check backend directory
if not exist "%PROJECT_DIR%backend" (
    echo [Error] Cannot find backend directory!
    pause
    exit /b 1
)

:: ========== Start Backend (Stable Mode) ==========
echo [Backend] Preparing to start (Stable Mode)...
cd /d "%PROJECT_DIR%backend"

if not exist "node_modules" (
    echo [Backend] First run, installing dependencies...
    call npm install
)

if not exist "node_modules\.prisma" (
    echo [Backend] Generating Prisma Client...
    call npx prisma generate
)

if not exist "prisma\dev.db" (
    echo [Backend] Initializing database...
    call npx prisma db push
    call npx tsx src/db/seed.ts
)

echo [Backend] Starting service (Stable Mode)...
start "Nexus AI Backend [Stable]" cmd /k "cd /d "%PROJECT_DIR%backend" && npm run stable"

:: Wait for backend to start
timeout /t 3 /nobreak >nul

:: ========== Start Frontend ==========
echo [Frontend] Starting development server...
cd /d "%PROJECT_DIR%"

if not exist "node_modules" (
    echo [Frontend] First run, installing dependencies...
    call npm install
)

start "Nexus AI Frontend" cmd /k "cd /d "%PROJECT_DIR%" && npm run dev -- --open"

echo.
echo ========================================================
echo   Quick Start Complete! (Stable Mode)
echo ========================================================
echo.
echo   Backend: http://localhost:3001 (Stable Mode, no hot reload)
echo   Frontend: Will open automatically in browser
echo.
echo   Run stop.bat to stop all services
echo.
pause
