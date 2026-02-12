@echo off
echo ============================================
echo   Video Player - Environment Setup
echo ============================================
echo.

:: Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Create virtual environment
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)

echo.

:: Activate virtual environment and install requirements
echo Installing dependencies...
call .venv\Scripts\activate.bat
pip install -r requirements.txt

echo.
echo ============================================
echo   Setup complete!
echo ============================================
echo.
echo To start the server, run:
echo   .venv\Scripts\activate.bat
echo   python server.py --path "C:\path\to\your\course"
echo.
pause
