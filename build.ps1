# Automated Build Script for Hololive Dreams-Auto
# Universal script: works seamlessly on local SSDs, external disks, and network/SMB shares.
param(
    [string]$PythonPath = ""
)
$ErrorActionPreference = "Stop"

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  Building Hololive Dreams-Auto Standalone Package" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# 1. Terminate any running instances
Write-Host "[1/3] Checking for running instances..." -ForegroundColor Yellow
Stop-Process -Name "Hololive-Dreams-Auto" -Force -ErrorAction SilentlyContinue

# 2. Detect Python interpreter (prefer active virtualenv or project venv)
$py = "python"
if ($PythonPath -and (Test-Path $PythonPath -ErrorAction SilentlyContinue)) {
    $py = $PythonPath
} elseif ($env:PYTHON_EXE -and (Test-Path $env:PYTHON_EXE -ErrorAction SilentlyContinue)) {
    $py = $env:PYTHON_EXE
} elseif ($env:VIRTUAL_ENV -and (Test-Path "$env:VIRTUAL_ENV\Scripts\python.exe" -ErrorAction SilentlyContinue)) {
    $py = "$env:VIRTUAL_ENV\Scripts\python.exe"
} elseif ($env:CONDA_PREFIX -and (Test-Path "$env:CONDA_PREFIX\python.exe" -ErrorAction SilentlyContinue)) {
    $py = "$env:CONDA_PREFIX\python.exe"
} elseif (Test-Path ".venv\Scripts\python.exe" -ErrorAction SilentlyContinue) {
    $py = ".venv\Scripts\python.exe"
} elseif (Test-Path "venv\Scripts\python.exe" -ErrorAction SilentlyContinue) {
    $py = "venv\Scripts\python.exe"
}

# Verify chosen python has PyInstaller; otherwise probe py launcher for an environment with PyInstaller
$oldEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $py -c "import PyInstaller" >$null 2>&1
if ($LASTEXITCODE -ne 0 -and (Get-Command py -ErrorAction SilentlyContinue)) {
    foreach ($ver in @("-3.14", "-3.13", "-3.12", "-3.11", "-3.10")) {
        $candidate = & py $ver -c "import sys, PyInstaller; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $candidate) {
            $py = "$candidate".Trim()
            break
        }
    }
}
$ErrorActionPreference = $oldEap

# 3. Compile via PyInstaller using local temp drive
Write-Host "[2/3] Compiling executable on local temp drive (using $py)..." -ForegroundColor Yellow
& $py -m PyInstaller -y --workpath "$env:TEMP\pyi_build" --distpath "$env:TEMP\pyi_dist" "Hololive Dreams-Auto.spec"

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[ERROR] PyInstaller compilation failed with exit code $LASTEXITCODE." -ForegroundColor Red
    exit $LASTEXITCODE
}

# 4. Synchronize to dist/
Write-Host "[3/3] Synchronizing release files to dist\Hololive-Dreams-Auto\..." -ForegroundColor Yellow
if (-not (Test-Path "dist")) { New-Item -ItemType Directory -Path "dist" | Out-Null }
robocopy "$env:TEMP\pyi_dist\Hololive-Dreams-Auto" "dist\Hololive-Dreams-Auto" /MIR /XF config.json log.txt debug_log.txt /XD logs debug /R:2 /W:1 | Out-Null

if ($LASTEXITCODE -le 7) {
    Write-Host "`n===================================================" -ForegroundColor Green
    Write-Host "  BUILD SUCCESSFUL!" -ForegroundColor Green
    Write-Host "  Output: dist\Hololive-Dreams-Auto\Hololive-Dreams-Auto.exe" -ForegroundColor Green
    Write-Host "===================================================" -ForegroundColor Green
} else {
    Write-Warning "Robocopy sync exited with code $LASTEXITCODE. If Hololive-Dreams-Auto.exe is currently running, please close it and re-run."
}
