@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo   Building Hololive Dreams-Auto Standalone Package
echo ===================================================

echo [1/3] Checking for running instances...
taskkill /IM "Hololive-Dreams-Auto.exe" /F >nul 2>&1

echo [2/3] Compiling executable on local temp drive...
python -m PyInstaller -y --workpath "%TEMP%\pyi_build" --distpath "%TEMP%\pyi_dist" "Hololive Dreams-Auto.spec"
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b %ERRORLEVEL%
)

echo [3/3] Synchronizing release files to dist\Hololive-Dreams-Auto\...
if not exist "dist" mkdir "dist"
robocopy "%TEMP%\pyi_dist\Hololive-Dreams-Auto" "dist\Hololive-Dreams-Auto" /MIR /R:2 /W:1 >nul

:: Robocopy returns codes 0-7 on success
if %ERRORLEVEL% leq 7 (
    echo.
    echo ===================================================
    echo   BUILD SUCCESSFUL!
    echo   Output: dist\Hololive-Dreams-Auto\Hololive-Dreams-Auto.exe
    echo ===================================================
) else (
    echo.
    echo [WARNING] Robocopy sync reported error code %ERRORLEVEL%.
)

endlocal
