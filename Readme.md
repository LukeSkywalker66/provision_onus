
# TR-069 Wizard

Aplicación de escritorio para provisionar ONUs en OLTs Huawei y ZTE con configuración automática de TR-069 (ACS).

## 🚀 Quick Start (Nueva PC)

### **Opción 1: PowerShell (Recomendado en Windows 10+)**
```powershell
# Clonar repositorio
git clone https://github.com/LukeSkywalker66/provision_onus.git
cd provision_onus

# Ejecutar setup automático
.\setup.ps1

# Activar venv para futuras sesiones
.\venv\Scripts\Activate.ps1

# Ejecutar aplicación
python app.py
```

### **Opción 2: CMD (Windows 7/8)**
```cmd
REM Clonar repositorio
git clone https://github.com/LukeSkywalker66/provision_onus.git
cd provision_onus

REM Ejecutar setup automático
setup.bat

REM Ejecutar aplicación
python app.py
```

### **Opción 3: Manual**
```powershell
# Crear venv
python -m venv venv

# Activar venv
.\venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
python app.py
```

## 📋 Requisitos Previos

- **Python 3.8+** (descargar desde https://www.python.org/)
- **Git** (para clonar repositorio)
- Windows 7 o superior

## 📦 Compilar Ejecutable Standalone

Una vez que el entorno está configurado:

```powershell
# Instalar PyInstaller (opcional, solo si quieres compilar)
pip install pyinstaller

# Compilar ejecutable
pyinstaller ProvisionOnus.spec

# Resultado: dist\tr069_wizard.exe (no requiere Python en máquina destino)
```

## 📖 Documentación

Consultar [DOCUMENTACION.md](DOCUMENTACION.md) para:
- Arquitectura y componentes
- Guía de uso completa
- Configuración de OLTs
- Casos de uso y ejemplos
- Solución de problemas

## 🔧 Estructura del Proyecto

```
provision_onus/
├── app.py                    # Aplicación principal + GUI
├── gui.py                    # Interfaz Tkinter
├── omci.py                   # Comandos OMCI/CLI
├── ssh_client.py             # Conexión SSH (Netmiko)
├── csv_logic.py              # Parseo de CSVs
├── config.py                 # Configuración de OLTs
├── setup.ps1                 # Script setup (PowerShell)
├── setup.bat                 # Script setup (CMD)
├── requirements.txt          # Dependencias Python
├── ProvisionOnus.spec        # Configuración PyInstaller
├── DOCUMENTACION.md          # Documentación técnica
└── logs/                     # Logs de ejecución
```

## 🎯 Funcionalidades

✅ Provisionar ONUs con configuración TR-069 automática  
✅ Validación de ONUs ya configuradas (skip automático)  
✅ Soporte multi-OLT (Huawei + ZTE)  
✅ Reconexión automática cada 200 ONUs  
✅ Recuperación ante fallos (checkpoints)  
✅ Interfaz gráfica intuitiva  
✅ Logs detallados con timestamps  
✅ Ejecutable standalone (sin dependencias externas)  

## 🐛 Troubleshooting

### "Python corromper PATH"
```powershell
# Reiniciar terminal o usar ruta completa
C:\Python312\python.exe -m venv venv
```

### "pip: comando no encontrado"
```powershell
# Usar módulo de Python
python -m pip install -r requirements.txt
```

### "Permission denied" (PowerShell)
```powershell
# Ejecutar como administrador o cambiar política:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 📞 Soporte

Para agregar nuevas OLTs o personalizar configuración, editar:
- `config.py` - OLT_MAP, ACS, EXEC, OLT_COMMANDS
- `DOCUMENTACION.md` - Ejemplos y configuración

## 📝 Versión Actual

**v2026-02-14 - Ejecutable tr069_wizard.exe**
- Validación de TR-069 configurado
- Logging mejorado con PPPoE user
- Manejo correcto de paginación OMCI

---

*Última actualización: 2026-02-16*
