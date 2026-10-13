# RoadWatch Windows Start Script (PowerShell)
$ErrorActionPreference = "Stop"
Set-Location -Path (Join-Path $PSScriptRoot "..")

$PythonExe = Join-Path ".venv" "Scripts" "python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Error "Virtual environment not found. Please run .\scripts\setup.ps1 first."
}

if (-not (Test-Path "frontend\dist\index.html")) {
    Write-Host "Frontend build not found. Building now..."
    Push-Location frontend
    npm ci
    npm run build
    Pop-Location
}

$Port = if ($env:PORT) { $env:PORT } else { "8011" }
if (-not $env:YOLO_CONFIG_DIR) { $env:YOLO_CONFIG_DIR = Join-Path $PWD "data\yolo" }
if (-not $env:MPLCONFIGDIR) { $env:MPLCONFIGDIR = Join-Path $PWD "data\matplotlib" }

Write-Host "Starting RoadWatch at http://127.0.0.1:$Port"
& $PythonExe -m uvicorn backend.app.main:app --host 127.0.0.1 --port $Port
