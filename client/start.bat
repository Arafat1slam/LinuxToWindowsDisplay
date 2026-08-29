@echo off
setlocal

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python is not installed or not on PATH.
    pause
    exit /b 1
)

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

certutil -hashfile requirements.txt MD5 > .requirements_hash_new
fc .requirements_hash .requirements_hash_new >nul 2>nul
if %errorlevel% neq 0 (
    echo Installing requirements...
    python -m pip install -r requirements.txt
    copy .requirements_hash_new .requirements_hash >nul
)
del .requirements_hash_new

where gst-inspect-1.0.exe >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: gst-inspect-1.0.exe not found on PATH.
    echo Please see DEVELOPMENT.md §3 for GStreamer installation instructions.
    pause
    exit /b 1
)

set PYTHONPATH=%cd%\..\common;%PYTHONPATH%

python -m screenlink_client %*

if %errorlevel% neq 0 (
    pause
)
