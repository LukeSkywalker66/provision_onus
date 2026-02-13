# TR-069 Wizard - Documentación Técnica

## 📋 Descripción General

**TR-069 Wizard** (anteriormente "ProvisionOnus") es una aplicación de escritorio que automatiza el provisionamiento de ONUs (Optical Network Units) en equipos OLT (Optical Line Terminals) Huawei y ZTE. La herramienta importa datos desde archivos CSV exportados de SmartOLT y configura automáticamente las ONUs con parámetros de red y TR-069 (ACS) mediante comandos OMCI/CLI.

**Caso de uso:** Provisionar múltiples ONUs para conectar con un servidor ACS (Auto Configuration Server) de TR-069 automáticamente.

---

## 🏗️ Arquitectura y Componentes

### Flujo General
```
CSV (SmartOLT) 
    ↓
[csv_logic.py] - Parsea y valida
    ↓
[app.py - SessionManager] - Maneja conexiones SSH con reconexión automática
    ↓
[ssh_client.py] - Conecta a OLT vía Netmiko/SSH
    ↓
[omci.py] - Ejecuta comandos OMCI en la OLT
    ↓
[gui.py] - Interfaz Tkinter para usuario final
```

---

## 📁 Estructura de Archivos

### **1. `app.py` - Orquestador Principal**

**Responsabilidades:**
- Punto de entrada de la aplicación
- Gestión de sesiones SSH con reconexión automática (`SessionManager`)
- Coordinación del flujo de procesamiento
- Logging y persistencia de checkpoints

**Clases principales:**

#### `SessionManager`
Maneja la conexión SSH a cada OLT con características avanzadas:

```python
SessionManager(
    olt_name: str,           # Nombre de la OLT (ej: "OLTHUAWEI")
    connect_fn,              # Función para conectar
    close_fn,                # Función para desconectar
    logger,                  # Callback para logs
    threshold=200,           # ONU número en que reconectarse
    delay=2,                 # Segundos de espera entre desconexión/reconexión
    retries=3,               # Reintentos de conexión
    backoff=5,               # Delay exponencial entre reintentos
    post_connect_hook=None   # Hook para ejecutar tras cada conexión
)
```

**Funciones clave:**
- `load_checkpoint()` - Carga contador desde archivo (recuperación ante fallos)
- `save_checkpoint()` - Guarda progreso cada 10 ONUs
- `open()` - Establece conexión con reintentos automáticos
- `increment_and_rotate()` - Incrementa contador y reconecta cada N ONUs
- `close()` - Cierra conexión de forma segura

**Checkpoint:**
- Se almacenan en `checkpoints/<nombre_olt>.ckp`
- Permite resumir procesamiento si la aplicación falla

---

### **2. `gui.py` - Interfaz de Usuario (Tkinter)**

**Componentes:**
- Selector de archivo CSV
- Checkboxes de opciones:
  - "eliminar wan pppoe" - Limpia configuración WAN anterior
  - "crear wan ip" - Configura IP DHCP en management VLAN
  - "eliminar serviceport (vlan150)" - Elimina puertos de servicio
- Área de logs con colores
- Progreso dinámico con ETA

**Métodos importantes:**
```python
write_log(msg)           # Escribe en log con color según tipo: [ERROR], [WARN], [OK], [INFO]
update_progress(done, total, avg, eta)  # Actualiza barra de progreso y ETA
browse()                 # Abre diálogo para seleccionar CSV
error(title, msg)        # Muestra ventana de error
```

---

### **3. `csv_logic.py` - Parseo de Datos**

**Función principal:**
```python
parse_smartolt_csv(path: str) -> list[dict]
```

**Columnas requeridas en CSV:**
| Columna | Tipo | Descripción |
|---------|------|-------------|
| OLT | string | Nombre de la OLT (debe estar en `OLT_MAP` de config.py) |
| Board | int | Número de slot/placa |
| Port | int | Puerto GPON |
| Allocated ONU | int | ID de la ONU (1-64) |
| Service port VLAN | int | VLAN de servicio |

**Columnas opcionales:**
| Columna | Descripción |
|---------|-------------|
| Onu Type | Tipo de ONU (ej: "GPON ONU") |
| Name | Usuario PPPoE |

**Validación:**
- Valida tipos de datos (int, string)
- Salta filas corruptas sin abortar
- Normaliza espacios en blanco

---

### **4. `ssh_client.py` - Capa de Conexión SSH**

**Librería:** Netmiko (soporte multi-vendor)

```python
connect_olt(ip, user, password, port) -> ConnectHandler
```

**Configuración Netmiko:**
- `device_type: "huawei"` - OLTs Huawei
- `global_cmd_verify: False` - Evita esperas innecesarias
- `session_log: "session.txt"` - Registra interacción completa
- `fast_cli: False` - Modo estándar (más confiable)

**Función:**
```python
close_olt(conn) -> None
```
Cierra conexión de forma segura sin excepciones.

---

### **5. `omci.py` - Comandos OMCI/CLI**

**Funciones principales:**

#### `provision_onu()`
Configura una ONU individual con parámetros de TR-069.

```python
provision_onu(
    conn,                    # Conexión Netmiko
    olt_name: str,          # Nombre OLT
    slot: int,              # Slot GPON
    port: int,              # Puerto GPON
    onu_id: int,            # ID ONU
    onu_type: str,          # Tipo ONU
    pppoe_user: str,        # Usuario PPPoE
    vlan: int,              # VLAN de servicio
    logger,                 # Función de log
    eliminar_wan_pppoe=False,
    crear_wan_ip=False
)
```

**Flujo de configuración (Huawei):**

Si `crear_wan_ip=True`:
1. Crea service-port en VLAN 150 (management)
2. Configura IP DHCP en la ONU
3. Asigna perfil TR-069

Si `crear_wan_ip=False`:
- Si `eliminar_wan_pppoe=True`: Elimina configuración WAN anterior
- Configura PPPoE con credenciales de ACS
- Asigna perfil TR-069

**Configuración específica por OLT:**
```
Villa Dolores 2     → profile-id 2
OLT(San_Jose)       → profile-id 1
OLTHUAWEI           → profile-id 1
ZTE C600            → Comandos alternativos (pon-onu-mng)
```

#### `rollback_onu_serviceport()`
Elimina service-ports asociados a una ONU en VLAN específica.

```python
rollback_onu_serviceport(
    conn,
    olt_name: str,
    slot: int,
    port: int,
    onu_id: int,
    vlan: int,
    logger
) -> bool
```

**Proceso:**
1. Consulta service-ports: `display service-port port 0/slot/port ont onu_id`
2. Filtra por VLAN
3. Elimina cada service-port con `undo service-port <id>`

#### `validate_omci_output()`
Ejecuta comandos con manejo de OLT ocupada y reintentos.

```python
validate_omci_output(conn, cmd, logger, max_retries=10) -> str
```

**Características:**
- Detecta patrones de "OLT ocupada" (backup en progreso)
- Reintenta automáticamente cada 200 segundos
- Maneja prompts de confirmación
- Retorna output del comando o lanza excepción tras N fallos

**Patrones de OLT ocupada:**
```
"It will take several minutes to..."
"The percentage of saved data on..."
"Failure: System is busy"
```

---

### **6. `config.py` - Configuración y Mapeos**

**OLT_MAP:** Mapea nombres SmartOLT a credenciales reales

```python
OLT_MAP = {
    "Villa Dolores 2": {
        "ip": "10.11.104.5",
        "user": "smartoltusr",
        "password": "6058gef6",
        "fabricante": "huawei",
        "port": 22,
    },
    # ... más OLTs
}
```

**ACS:** Parámetros TR-069 comunes

```python
ACS = {
    "ip": "http://138.59.172.24",
    "port": 7547,
    "pppoe_user": "tr069",
    "pppoe_password": "123",
    "user": "miCpeUser",
    "password": "Passw0rdACS!23#",
    "prioridad": 0,  # VLAN CoS (0-7)
}
```

**EXEC:** Parámetros de ejecución

```python
EXEC = {
    "batch_size": 50,              # Tamaño de lote
    "delay_between_onus": 0.2,     # Espera entre ONUs (segundos)
    "delay_between_onus_largo": 200,  # Espera OLT ocupada (segundos)
}
```

---

## 🔄 Flujo de Ejecución Detallado

### 1. **Inicio**
```
main() → crea GUI Tkinter
```

### 2. **Usuario selecciona opciones**
- CSV: `SmartOLT_onus_list_2026-01-13_15_19_39.376604.csv`
- Checkboxes: eliminar_wan_pppoe, crear_wan_ip, rollback_serviceport
- Clic en "Ejecutar"

### 3. **Validación CSV**
```
parse_smartolt_csv()
  → Lee CSV con pandas
  → Valida columnas requeridas
  → Normaliza tipos y espacios
  → Retorna lista de dicts
```

### 4. **Agrupación por OLT**
```python
by_olt = {
    "Villa Dolores 2": [onu1, onu2, ...],
    "OLTHUAWEI": [onu3, onu4, ...],
}
```

### 5. **Para cada OLT:**

#### a) Crear SessionManager
```python
mgr = SessionManager(
    olt_name,
    connect_olt,
    close_olt,
    ui.write_log,
    threshold=200,  # Reconectar cada 200 ONUs
    post_connect_hook=enter_config_mode
)
```

#### b) Cargar checkpoint (si existe)
```python
mgr.load_checkpoint()  # Ej: counter = 42 (ya se procesaron 42 ONUs)
```

#### c) Conectar a OLT
```python
mgr.open(ip, user, password, port)
  → Reintentos automáticos con backoff
  → Ejecuta post_connect_hook (enter_config_mode)
```

#### d) Entrar en modo configuración
```python
enter_config_mode(olt_name, conn, logger)
  # Huawei: enable → config
  # ZTE: configure terminal
```

#### e) Para cada ONU:
```python
if rollback_serviceport:
    rollback_onu_serviceport(...)
else:
    provision_onu(
        conn,
        olt_name,
        slot, port, onu_id, onu_type, pppoe_user, vlan,
        eliminar_wan_pppoe=X,
        crear_wan_ip=Y
    )
```

#### f) Después de cada ONU:
- Incrementar contador
- Guardar checkpoint cada 10 ONUs
- Si contador % 200 == 0: reconectar SSH
- Actualizar progress bar con ETA

#### g) Finalizarse
```python
mgr.save_checkpoint()
mgr.close()
```

### 6. **Logging**
- Archivo: `logs/ejecucion_YYYYMMDD-HHMMSS.log`
- Console: GUI con colores por tipo

---

## ⚙️ Parámetros de Reconexión

El `SessionManager` reconecta automáticamente cada N ONUs para evitar timeout/memory leak:

```python
RECONNECT_THRESHOLD = 200      # Reconectar cada 200 ONUs
RECONNECT_DELAY = 2            # Esperar 2 segundos
RECONNECT_RETRIES = 3          # 3 intentos de reconexión
RECONNECT_BACKOFF = 5          # Backoff de 5 segundos entre intentos
```

**Cálculo de reconexión:**
```python
if (counter % 200) == 0:
    close()
    sleep(2)
    open()  # Reintentar hasta 3 veces con backoff de 5s
```

---

## 🛠️ Configuración de ONUs por OLT

### **Villa Dolores 2 (Huawei)**

#### Crear WAN IP (crear_wan_ip=True)
```
service-port vlan 150 gpon 0/SLOT/PORT ont ONU gemport 2 multi-service \
  user-vlan 150 tag-transform translate \
  inbound traffic-table name SMARTOLT-VOIPMNG-10M \
  outbound traffic-table name SMARTOLT-VOIPMNG-10M

interface gpon 0/SLOT
ont ipconfig PORT ONU ip-index 0 dhcp vlan 150 priority 2
ont tr069-server-config PORT ONU profile-id 2
quit
```

#### Crear WAN PPPoE (crear_wan_ip=False)
```
interface gpon 0/SLOT
ont ipconfig PORT ONU pppoe user-account \
  username tr069 password 123 vlan VLAN priority 0
ont wan-config PORT ONU ip-index 0 profile-id 1
ont tr069-server-config PORT ONU profile-id 2
quit
```

### **OLT(San_Jose) / OLTHUAWEI (Huawei)**

Similares pero con parámetros ajustados:
- `traffic-table index 7` en lugar de nombres
- `profile-id 1` para TR-069

### **ZTE C600**

```
pon-onu-mng gpon_onu-1/SLOT/PORT:ONU
quit
```

---

## 📊 Estructura de Datos

### Registro CSV parseado
```python
{
    "olt_name": "Villa Dolores 2",
    "slot": 0,
    "port": 5,
    "onu_id": 62,
    "onu_type": "GPON ONU",
    "pppoe_user": "cliente_001",
    "vlan": 100
}
```

### Checkpoint
```
Archivo: checkpoints/OLTHUAWEI.ckp
Contenido: "150" (última ONU procesada)
```

### Log
```
[2026-01-13 15:22:30,123] INFO [+] Procesando 245 ONUs desde archivo.csv
[2026-01-13 15:22:31,456] INFO [OK] Conectado a Villa Dolores 2 (int 1)
[2026-01-13 15:22:33,789] INFO [Villa Dolores 2] GPON 0/5 ONU 62 → GPON ONU PPPoE:cliente_001 - VLAN:100
[2026-01-13 15:22:34,123] INFO [OK] ONU 62 en Villa Dolores 2
```

---

## 🔍 Casos de Uso Principales

### 1. **Provisionar ONUs nuevas con TR-069**
```
✓ Archivo CSV con ONUs
✓ Desmarcar "eliminar wan pppoe"
✓ Desmarcar "crear wan ip"
→ Configura PPPoE + TR-069 automáticamente
→ ONU informa al ACS tras reboot
```

### 2. **Crear interfaz de management DHCP**
```
✓ Archivo CSV
✓ Desmarcar "eliminar wan pppoe"
✓ Marcar "crear wan ip"
→ Configurar IP DHCP en VLAN 150
→ Útil para diagnóstico/acceso directo
```

### 3. **Limpiar configuración anterior**
```
✓ Archivo CSV
✓ Marcar "eliminar wan pppoe"
✓ Desmarcar "crear wan ip"
→ Elimina WAN antigua antes de configurar nueva
```

### 4. **Rollback de puertos de servicio**
```
✓ Archivo CSV
✓ Marcar "eliminar serviceport (vlan150)"
→ Elimina service-ports asociados a las ONUs
→ Útil para limpiar configuración manual
```

---

## 🐛 Manejo de Errores

### OLT Ocupada (Backup en progreso)
```
Detección: Output contiene patrones de BUSY
Acción: Reintenta hasta 10 veces cada 200 segundos
Log: [WARN] OLT ocupada al ejecutar '...', reintentando en 200s (intento X/10)
```

### Conexión SSH falla
```
Detección: Exception en connect_olt()
Acción: Reintentos con backoff exponencial (3 intentos, 5s delay)
Log: [WARN] Falló conexión a OLTHUAWEI (intent 1): Connection refused
Log: [ERROR] No se pudo conectar a OLTHUAWEI después de 3 intentos
```

### CSV inválido
```
Detección: Falta columna requerida o tipo incorrecto
Acción: Ventana popup de error + log
Log: [ERROR] CSV inválido: Falta columna requerida en CSV: Service port VLAN
```

### ONU falla a procesar
```
Detección: Exception en provision_onu()
Acción: Loguea error, continúa con siguiente ONU
Log: [ERROR] ONU 62/5:30 en Villa Dolores 2: Connection reset by peer...
```

---

## 📦 Dependencias

```
netmiko==4.6.0          # SSH a equipos de red (Huawei, ZTE, etc.)
pandas==2.3.3           # Parseo de CSV
paramiko==4.0.0         # SSH subyacente
PyYAML==6.0.3           # Configuración (usado por ntc_templates)
requests==2.32.5        # HTTP (soporte general)
cryptography==46.0.3    # Cifrado SSH
```

---

## 🚀 Compilación a Ejecutable

```powershell
# 1. Instalar PyInstaller
pip install pyinstaller

# 2. Ejecutar la compilación
pyinstaller ProvisionOnus.spec

# 3. Resultado
# → dist/ProvisionOnus/tr069_wizard.exe (ejecutable standalone)
```

**Spec (`ProvisionOnus.spec`):**
- Punto de entrada: `app.py`
- Nombre ejecutable: `tr069_wizard`
- Icono: `icons/cap.ico`
- Consola: Habilitada
- Compresión: UPX enabled

El ejecutable incluye **todas las dependencias** de Python y no requiere instalación de Python en la máquina destino.

---

## 📝 Archivos Generados en Ejecución

```
logs/
  ejecucion_20260113-152230.log   ← Log detallado de session

checkpoints/
  OLTHUAWEI.ckp                   ← Counter de ONUs procesadas
  Villa_Dolores_2.ckp
  OLT_San_Jose.ckp

session.txt                         ← Trace SSH de Netmiko
```

---

## 🎯 Mejoras Futuras Posibles

1. **Soporte multi-vendor expandido**
   - Agregar más fabricantes de OLT
   - Plantillas YAML específicas por fabricante

2. **Reintentos automáticos a nivel ONU**
   - Si una ONU falla, reintentar antes de pasar a la siguiente
   - Exponential backoff por ONU

3. **Estadísticas y reportes**
   - Resumen HTML post-ejecución
   - Tasa de éxito por OLT

4. **Base de datos**
   - Persistencia de histórico de ONUs
   - Seguimiento de cambios

5. **API REST**
   - Exponer funcionalidad sin GUI
   - Integración con sistemas externos

6. **Validación previa**
   - Verificar conectividad a OLTs antes de procesar
   - Pre-flight checks

---

## 📞 Soporte

**Archivo de configuración principal:** [config.py](config.py)
- Agregar OLTs: Añadir entrada en `OLT_MAP`
- Ajustar parámetros ACS: Editar diccionario `ACS`
- Tuning de ejecución: Modificar `EXEC`

**Logging detallado:**
- GUI: Área scrolleable con colores por tipo
- Archivo: `logs/ejecucion_*.log` con timestamps

---

*Documentación actualizada: 2026-01-30*
*Versión: Ejecutable TR-069 Wizard*
