@echo off
title Deliverace Studio
echo ========================================================
echo   Starting Deliverace Studio...
echo ========================================================

:: Check if C:\Python314\python.exe exists
if exist "C:\Python314\python.exe" (
    echo Using C:\Python314\python.exe
    "C:\Python314\python.exe" main.py
    goto end
)

:: Check if py launcher works
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Using py launcher
    py main.py
    goto end
)

:: Check if python command works
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Using python
    python main.py
    goto end
)

echo.
echo [ERROR] Python was not found on your system PATH!
echo Please ensure Python is installed and accessible.
echo.

:end
pause
