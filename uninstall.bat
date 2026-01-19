@echo off
REM ===================================
REM Video Player - Context Menu Uninstaller
REM Removes "Play Course" from Windows Explorer context menu
REM ===================================

REM Check for admin privileges
net session >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo ===================================
echo   VIDEO PLAYER - UNINSTALLER
echo ===================================
echo.

REM Remove registry entries for folder icon context menu
echo Removing context menu entry from folder icons...
reg delete "HKCR\Directory\shell\PlayCourse" /f >nul 2>&1

REM Remove registry entries for folder background context menu
echo Removing context menu entry from folder background...
reg delete "HKCR\Directory\Background\shell\PlayCourse" /f >nul 2>&1

echo.
echo ===================================
echo   UNINSTALL COMPLETE
echo ===================================
echo.
echo Context menu entries have been removed.
echo.
echo NOTE: Your video progress is saved in the browser's
echo localStorage and will persist until you clear browser data.
echo.

pause
