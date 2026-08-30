@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel% neq 0 (
    echo Python Launcher py is not installed or not on PATH.
    pause
    exit /b 1
)

if not exist .venv (
    echo Creating virtual environment...
    py -3.9 -m venv .venv
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
    if exist "C:\gstreamer\1.0\msvc_x86_64\bin\gst-inspect-1.0.exe" (
        set "PATH=C:\gstreamer\1.0\msvc_x86_64\bin;%PATH%"
    ) else if exist "C:\Program Files\gstreamer\1.0\msvc_x86_64\bin\gst-inspect-1.0.exe" (
        set "PATH=C:\Program Files\gstreamer\1.0\msvc_x86_64\bin;%PATH%"
    ) else (
        echo Error: gst-inspect-1.0.exe not found on PATH.
        echo Please see DEVELOPMENT.md §3 for GStreamer installation instructions.
        pause
        exit /b 1
    )
)

if exist "C:\gstreamer\1.0\msvc_x86_64\lib\site-packages\gi" (
    set "PYTHONPATH=C:\gstreamer\1.0\msvc_x86_64\lib\site-packages;%PYTHONPATH%"
) else if exist "C:\Program Files\gstreamer\1.0\msvc_x86_64\lib\site-packages\gi" (
    set "PYTHONPATH=C:\Program Files\gstreamer\1.0\msvc_x86_64\lib\site-packages;%PYTHONPATH%"
)

set PYTHONPATH=%cd%\..\common;%PYTHONPATH%

python -m screenlink_client %*

if %errorlevel% neq 0 (
    pause
)
