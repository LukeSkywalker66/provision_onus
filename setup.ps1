# ============================================================================
# TR-069 Wizard - Setup Script para Windows PowerShell
# ============================================================================
# Este script configura el entorno virtual y instala dependencias
# Uso: .\setup.ps1
# ============================================================================

param(
    [switch]$Clean = $false,
    [switch]$SkipActivate = $false
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TR-069 Wizard - Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar si Python está instalado
Write-Host "[*] Verificando Python..." -ForegroundColor Yellow
$pythonCheck = python --version 2>$null
if ($null -eq $pythonCheck) {
    Write-Host "[ERROR] Python no está instalado o no está en PATH" -ForegroundColor Red
    Write-Host "Descargue e instale Python desde: https://www.python.org/" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] $pythonCheck" -ForegroundColor Green

# Opción: Limpiar entorno anterior
if ($Clean) {
    Write-Host "[*] Limpiando venv anterior..." -ForegroundColor Yellow
    if (Test-Path "venv") {
        Remove-Item -Recurse -Force "venv"
        Write-Host "[OK] venv eliminado" -ForegroundColor Green
    }
}

# Crear venv
Write-Host "[*] Creando entorno virtual..." -ForegroundColor Yellow
python -m venv venv
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] No se pudo crear el entorno virtual" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] venv creado" -ForegroundColor Green

# Activar venv
Write-Host "[*] Activando venv..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] No se pudo activar el venv" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] venv activado" -ForegroundColor Green

# Actualizar pip
Write-Host "[*] Actualizando pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip -q
Write-Host "[OK] pip actualizado" -ForegroundColor Green

# Instalar dependencias
Write-Host "[*] Instalando dependencias (esto puede tardar 1-2 minutos)..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    # Si existe requirements.txt en minúsculas
    pip install -r requirements.txt -q
} elseif (Test-Path "Requirements.txt") {
    # Si existe Requirements.txt con mayúsculas
    pip install -r Requirements.txt -q
} else {
    Write-Host "[ERROR] No se encuentra requirements.txt o Requirements.txt" -ForegroundColor Red
    exit 1
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] No se pudieron instalar las dependencias" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Dependencias instaladas" -ForegroundColor Green

# Verificar instalación
Write-Host "[*] Verificando instalación..." -ForegroundColor Yellow
python -c "import pandas, netmiko, tkinter" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Todas las librerías principales están disponibles" -ForegroundColor Green
} else {
    Write-Host "[WARN] Algunas librerías podrían estar faltando" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "SETUP COMPLETADO EXITOSAMENTE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Próximos pasos:" -ForegroundColor Cyan
Write-Host "1. El venv ya está activado en esta terminal" -ForegroundColor White
Write-Host "2. Ejecutar la aplicación: python app.py" -ForegroundColor White
Write-Host "3. O compilar el ejecutable: pyinstaller ProvisionOnus.spec" -ForegroundColor White
Write-Host ""
Write-Host "Para futuras sesiones:" -ForegroundColor Cyan
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host ""
