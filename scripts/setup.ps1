# RoadWatch Windows Setup Script (PowerShell)
$ErrorActionPreference = "Stop"
Set-Location -Path (Join-Path $PSScriptRoot "..")

Write-Host "Setting up RoadWatch on Windows..."

# Create Python virtual environment if not already created
if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment in .venv..."
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv venv --python 3.12 .venv
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.12 -m venv .venv
    } else {
        python -m venv .venv
    }
}

$PythonExe = Join-Path ".venv" "Scripts" "python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Error "Python executable not found at $PythonExe. Please verify your Python installation."
}

# Install Python dependencies
Write-Host "Installing Python dependencies..."
if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv pip install --python $PythonExe -r requirements.txt
} else {
    & $PythonExe -m pip install -r requirements.txt
}

# Verify / ensure model checkpoint
Write-Host "Verifying model checkpoint..."
& $PythonExe scripts/download_model.py

# Install frontend dependencies and build production assets
Write-Host "Building frontend assets..."
Push-Location frontend
npm ci
npm run build
Pop-Location

Write-Host "Ready! Start the application with .\scripts\start.ps1"
