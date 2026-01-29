@echo off
chcp 65001 >nul
title Nexus AI - Service Stopper

echo.
echo ========================================================
echo     Nexus AI - Service Stopper
echo ========================================================
echo.

:: Stop backend processes (node/tsx)
echo [*] Stopping backend service...
taskkill /F /IM "node.exe" /FI "WINDOWTITLE eq Nexus AI Backend*" 2>nul
if errorlevel 1 (
    echo     No running backend service found
) else (
    echo     Backend service stopped
)

:: Stop frontend processes (node)
echo [*] Stopping frontend service...
taskkill /F /IM "node.exe" /FI "WINDOWTITLE eq Nexus AI Frontend*" 2>nul
if errorlevel 1 (
    echo     No running frontend service found
) else (
    echo     Frontend service stopped
)

:: More aggressive stop: kill processes by port
echo.
echo [*] Checking port usage...

:: Check port 3001 (backend)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3001 ^| findstr LISTENING') do (
    echo     Found port 3001 occupied by process %%a, terminating...
    taskkill /F /PID %%a 2>nul
)

:: Check port 3000 (frontend, possibly)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    echo     Found port 3000 occupied by process %%a, terminating...
    taskkill /F /PID %%a 2>nul
)

:: Check port 5173 (Vite default port)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    echo     Found port 5173 occupied by process %%a, terminating...
    taskkill /F /PID %%a 2>nul
)

echo.
echo ========================================================
echo   All services stopped
echo ========================================================
echo.
pause
