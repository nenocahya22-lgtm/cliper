@echo off
title VideoClipse Server
cd /d "%~dp0"

:: Deteksi Python
if exist "C:\Users\USER\AppData\Local\Programs\Python\Python314\python.exe" (
    set PYTHON="C:\Users\USER\AppData\Local\Programs\Python\Python314\python.exe"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python tidak ditemukan. Install Python dulu.
        pause
        exit /b 1
    )
    set PYTHON=python
)

echo ====================================
echo  VideoClipse Server - Starting...
echo ====================================
echo.
echo Log file: server.log
echo Akses: http://localhost:8501
echo To stop: taskkill /f /im python*
echo.

:: Redirect output ke log file, jalankan di background
%PYTHON% -m streamlit run app.py --server.headless true > server.log 2>&1

:: Buka browser
timeout /t 5 /nobreak >nul
start http://localhost:8501
