@echo off
REM ===================================
REM Video Player Runner
REM Supports multiple instances via dynamic port selection
REM ===================================

REM Configuration - get script dir BEFORE enabling delayed expansion
SET "SCRIPT_DIR=%~dp0"
SET "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
SET "BASE_PORT=8002"
SET "MAX_PORT=8020"

REM ===================================
REM Detect Target Directory
REM Handle special characters like ! and ~ in paths
REM ===================================
SET "TARGET_DIR=%~1"
IF "%TARGET_DIR%"=="" SET "TARGET_DIR=%CD%"

REM Verify path exists
IF NOT EXIST "%TARGET_DIR%\." (
    echo.
    echo ===================================
    echo   ERROR: Folder not found
    echo ===================================
    echo.
    echo Path: %TARGET_DIR%
    echo.
    pause
    exit /b 1
)

REM Now enable delayed expansion for port finding
SETLOCAL EnableDelayedExpansion

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
SET "VENV_PYTHON=%SCRIPT_DIR%\.venv\Scripts\python.exe"

echo.
echo Script dir: %SCRIPT_DIR%
echo.

REM Use .venv if it exists, otherwise use system python
IF EXIST "%VENV_PYTHON%" (
    echo Using virtual environment: %VENV_PYTHON%
    echo.
    "%VENV_PYTHON%" "%SCRIPT_DIR%\server.py" --port %PORT% --path "%TARGET_DIR%"
) ELSE (
    echo Virtual environment not found at: %VENV_PYTHON%
    echo Using system Python...
    echo.
    python "%SCRIPT_DIR%\server.py" --port %PORT% --path "%TARGET_DIR%"
)

REM ===================================
REM Server Stopped or Error
REM ===================================
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ===================================
    echo   ERROR: Server failed to start
    echo   Error code: %ERRORLEVEL%
    echo ===================================
    echo.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Server stopped.
echo.

ENDLOCAL
exit /b 0
