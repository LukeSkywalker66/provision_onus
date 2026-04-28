$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root 'venv\Scripts\python.exe'
$pyinstaller = Join-Path $root 'venv\Scripts\pyinstaller.exe'

if (-not (Test-Path $python)) {
    throw "No se encontro Python del venv en $python"
}

if (-not (Test-Path $pyinstaller)) {
    throw "No se encontro PyInstaller en $pyinstaller"
}

& $pyinstaller --clean --noconfirm ProvisionOnus.spec

Write-Host "Build finalizado. Ejecutable en: dist\ProvisionOnus.exe" -ForegroundColor Green
