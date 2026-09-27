@echo off
:: Universal build script: works on local SSDs, external disks, and network/SMB shares.
setlocal
cd /d "%~dp0"

echo ===================================================
echo   Building Hololive Dreams-Auto Standalone Package
echo ===================================================

echo [1/3] Checking for running instances...
taskkill /IM "Hololive-Dreams-Auto.exe" /F >nul 2>&1

set "PY_CMD=python"
if not "%~1"=="" if exist "%~1" set "PY_CMD=%~1"
if "%PY_CMD%"=="python" if defined PYTHON_EXE if exist "%PYTHON_EXE%" set "PY_CMD=%PYTHON_EXE%"
if "%PY_CMD%"=="python" if defined VIRTUAL_ENV if exist "%VIRTUAL_ENV%\Scripts\python.exe" set "PY_CMD=%VIRTUAL_ENV%\Scripts\python.exe"
if "%PY_CMD%"=="python" if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PY_CMD=%CONDA_PREFIX%\python.exe"
if "%PY_CMD%"=="python" if exist ".venv\Scripts\python.exe" set "PY_CMD=.venv\Scripts\python.exe"
if "%PY_CMD%"=="python" if exist "venv\Scripts\python.exe" set "PY_CMD=venv\Scripts\python.exe"

echo [2/3] Compiling executable on local temp drive (using %PY_CMD%)...
"%PY_CMD%" -m PyInstaller -y --workpath "%TEMP%\pyi_build" --distpath "%TEMP%\pyi_dist" "Hololive Dreams-Auto.spec"
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
    echo [WARNING] Robocopy sync reported error code %ERRORLEVEL%. If Hololive-Dreams-Auto.exe is open, close it and re-run.
)

endlocal
