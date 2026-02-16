@echo off
REM ============================================================================
REM TR-069 Wizard - Setup Script para Windows CMD
REM ============================================================================
REM Este script configura el entorno virtual e instala dependencias
REM Uso: setup.bat
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo ========================================
echo TR-069 Wizard - Setup
echo ========================================
echo.

REM Verificar si Python está instalado
echo [*] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no está instalado o no está en PATH
    echo Descargue e instale Python desde: https://www.python.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [OK] !PYTHON_VERSION!

REM Opción: Limpiar entorno anterior
if "%1"=="--clean" (
    echo [*] Limpiando venv anterior...
    if exist venv (
        rmdir /s /q venv
        echo [OK] venv eliminado
    )
)

REM Crear venv
echo [*] Creando entorno virtual...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] No se pudo crear el entorno virtual
    pause
    exit /b 1
)
echo [OK] venv creado

REM Activar venv
echo [*] Activando venv...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] No se pudo activar el venv
    pause
    exit /b 1
)
echo [OK] venv activado

REM Actualizar pip
echo [*] Actualizando pip...
python -m pip install --upgrade pip -q
echo [OK] pip actualizado

REM Instalar dependencias
echo [*] Instalando dependencias (esto puede tardar 1-2 minutos)...
if exist requirements.txt (
    pip install -r requirements.txt -q
) else if exist Requirements.txt (
    pip install -r Requirements.txt -q
) else (
    echo [ERROR] No se encuentra requirements.txt o Requirements.txt
    pause
    exit /b 1
)
if errorlevel 1 (
    echo [ERROR] No se pudieron instalar las dependencias
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas

REM Verificar instalación
echo [*] Verificando instalación...
python -c "import pandas, netmiko, tkinter" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Algunas librerías podrían estar faltando
) else (
    echo [OK] Todas las librerías principales están disponibles
)

echo.
echo ========================================
echo SETUP COMPLETADO EXITOSAMENTE
echo ========================================
echo.
echo Próximos pasos:
echo 1. El venv ya está activado en esta terminal
echo 2. Ejecutar la aplicación: python app.py
echo 3. O compilar el ejecutable: pyinstaller ProvisionOnus.spec
echo.
echo Para futuras sesiones:
echo   venv\Scripts\activate.bat
echo.
pause
