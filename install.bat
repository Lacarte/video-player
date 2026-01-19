@echo off
REM ===================================
REM Video Player - Context Menu Installer
REM Adds "Play Course" to Windows Explorer folder context menu
REM Supports multiple instances (different ports)
REM ===================================

REM Check for admin privileges
net session >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

REM Get absolute script directory (remove trailing backslash)
SET "SCRIPT_DIR=%~dp0"
SET "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo.
echo ===================================
echo   VIDEO PLAYER - INSTALLER
echo ===================================
echo.
echo Location: %SCRIPT_DIR%
echo.

REM Add registry entries for folder icon context menu (right-click on folder)
echo Installing context menu entry for folder icons...
reg add "HKCR\Directory\shell\PlayCourse" /ve /d "Play Course" /f >nul
reg add "HKCR\Directory\shell\PlayCourse" /v "Icon" /d "%SystemRoot%\System32\shell32.dll,176" /f >nul
reg add "HKCR\Directory\shell\PlayCourse\command" /ve /d "cmd.exe /c \"\"%SCRIPT_DIR%\runner.bat\" \"%%V\"\"" /f >nul

REM Add registry entries for folder background context menu (right-click inside folder)
echo Installing context menu entry for folder background...
reg add "HKCR\Directory\Background\shell\PlayCourse" /ve /d "Play Course" /f >nul
reg add "HKCR\Directory\Background\shell\PlayCourse" /v "Icon" /d "%SystemRoot%\System32\shell32.dll,176" /f >nul
reg add "HKCR\Directory\Background\shell\PlayCourse\command" /ve /d "cmd.exe /c \"\"%SCRIPT_DIR%\runner.bat\" \"%%V\"\"" /f >nul

IF %ERRORLEVEL% EQU 0 (
    echo.
    echo ===================================
    echo   SUCCESS!
    echo ===================================
    echo.
    echo Context menu installed successfully.
    echo.
    echo HOW TO USE:
    echo   1. Right-click any folder containing videos
    echo   2. Select "Play Course"
    echo   3. Browser will open with the video player
    echo.
    echo FEATURES:
    echo   - Multiple instances supported (different courses)
    echo   - Auto port selection (8002-8020)
    echo   - Progress saved in browser
    echo.
) ELSE (
    echo.
    echo ERROR: Failed to install context menu.
    echo Error code: %ERRORLEVEL%
    echo.
)

pause
