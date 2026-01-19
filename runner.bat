@echo off
SETLOCAL EnableDelayedExpansion

REM ===================================
REM Video Player Runner
REM Supports multiple instances via dynamic port selection
REM ===================================

REM Configuration
SET "SCRIPT_DIR=%~dp0"
SET "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
SET "BASE_PORT=8002"
SET "MAX_PORT=8020"

REM ===================================
REM Detect Target Directory
REM ===================================
SET "TARGET_DIR="
IF NOT "%~1"=="" (
    IF EXIST "%~1\." (
        REM Context menu mode - %1 is the folder path
        SET "TARGET_DIR=%~1"
    )
)

IF NOT DEFINED TARGET_DIR (
    REM Manual mode - use current directory
    SET "TARGET_DIR=%CD%"
)

REM ===================================
REM Find Available Port
REM ===================================
SET "PORT="

FOR /L %%P IN (%BASE_PORT%,1,%MAX_PORT%) DO (
    IF NOT DEFINED PORT (
        netstat -an 2>nul | find ":%%P" | find "LISTENING" >nul 2>&1
        IF ERRORLEVEL 1 (
            SET "PORT=%%P"
        )
    )
)

IF NOT DEFINED PORT (
    echo.
    echo ===================================
    echo   ERROR: No Free Port Available
    echo ===================================
    echo.
    echo All ports from %BASE_PORT% to %MAX_PORT% are in use.
    echo Please close some Video Player instances and try again.
    echo.
    pause
    exit /b 1
)

REM ===================================
REM Display Startup Info
REM ===================================
echo.
echo ===================================
echo   VIDEO PLAYER
echo ===================================
echo.
echo   Port:   %PORT%
echo   Course: %TARGET_DIR%
echo   URL:    http://localhost:%PORT%
echo.
echo ===================================
echo.
echo Press Ctrl+C to stop the server.
echo.

REM ===================================
REM Open Browser
REM ===================================
start "" "http://localhost:%PORT%"

REM ===================================
REM Start Server
REM ===================================
python "%SCRIPT_DIR%\server.py" --port %PORT% --path "%TARGET_DIR%"

REM ===================================
REM Server Stopped
REM ===================================
echo.
echo Server stopped.
echo.

ENDLOCAL
exit /b 0
