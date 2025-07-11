@echo off
REM Windows setup script for Pi-ScreenTV
setlocal enabledelayedexpansion

echo [INFO] Setting up Pi-ScreenTV on Windows...

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

echo [STEP 1] Creating Python virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)

echo [STEP 2] Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies
    pause
    exit /b 1
)

echo [STEP 3] Creating required directories...
if not exist "videos" mkdir videos
if not exist "logs" mkdir logs
if not exist "images" mkdir images

echo [STEP 4] Testing Python application...
python -m py_compile app.py
if errorlevel 1 (
    echo [ERROR] Python application has syntax errors
    pause
    exit /b 1
)

echo [SUCCESS] Installation complete!
echo You can now run the application with: python app.py
echo The web interface will be available at: http://localhost:5000
pause