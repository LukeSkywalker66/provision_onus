# TR-069 Wizard - Documentación Técnica

## 📋 Descripción General

**TR-069 Wizard** es una aplicación de escritorio que automatiza el provisionamiento de ONUs (Optical Network Units) en equipos OLT (Optical Line Terminals) Huawei y ZTE. La herramienta importa datos desde archivos CSV exportados de SmartOLT y configura automáticamente las ONUs con parámetros de red y TR-069 (ACS) mediante comandos OMCI/CLI.

**Propósito:** Provisionar múltiples ONUs para conectar con un servidor ACS (Auto Configuration Server) de TR-069 automáticamente.

**Versión actual:** Ejecutable standalone `tr069_wizard.exe`

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
    ↓
[Logs + Checkpoints] - Rastreo de progreso
```

---

## 📁 Estructura de Archivos y Componentes

### **1. `app.py` - Orquestador Principal (328 líneas)**

**Responsabilidades:**
- Punto de entrada y configuración de GUI
- Gestión de sesiones SSH con reconexión automática (`SessionManager`)
- Coordinación del flujo de procesamiento de ONUs
- Logging y persistencia de checkpoints para recuperación ante fallos

**Clases principales:**

#### `SessionManager`
Maneja la conexión SSH a cada OLT con características avanzadas para robustez:

```python
SessionManager(
    olt_name: str,           # Nombre de la OLT (ej: "Villa Dolores 2")
    connect_fn,              # Función para conectar (connect_olt)
    close_fn,                # Función para desconectar (close_olt)
    logger,                  # Callback para logs (ui.write_log)
    threshold=200,           # Reconectar cada N ONUs procesadas
    delay=2,                 # Segundos de espera entre desconexión/reconexión
    retries=3,               # Reintentos de conexión ante fallo
    backoff=5,               # Delay en segundos entre reintentos (exponencial)
    post_connect_hook=None   # función a ejecutar tras cada conexión exitosa
)
```

**Métodos:**
- `load_checkpoint()` - Lee contador guardado desde archivo (.ckp)
- `save_checkpoint()` - Persiste contador de ONUs procesadas
- `open()` - Establece conexión SSH con reintentos automáticos
- `increment_and_rotate()` - Incrementa contador y reconecta cada N ONUs
- `close()` - Cierra conexión de forma segura

**Checkpoints:**
- Se almacenan en `checkpoints/<olt_name>.ckp`
- Permite resumir procesamiento desde punto de fallo
- Actualizado cada 10 ONUs procesadas

---

### **2. `gui.py` - Interfaz de Usuario (82 líneas)**

**Componentes:**
- Selector de archivo CSV (diálogo nativo)
- Checkboxes de opciones:
  - `eliminar_wan_pppoe` - Limpia configuración WAN anterior antes de provisionar
  - `crear_wan_ip` - Configura IP DHCP en management VLAN 150
  - `rollback_serviceport` - Elimina service-ports en lugar de provisionar
  - `skip_tr069_configured` - Salta ONUs que ya tienen TR-069 configurado
- Área de logs con colores por tipo de mensaje
- Progreso dinámico con ETA en tiempo real

**Métodos:**
```python
write_log(msg)              # Escribe en área de logs con formato [TIPO]
update_progress(done, total, avg, eta)  # Actualiza barra y contador
browse()                    # Abre selector de archivo CSV
error(title, msg)           # Muestra ventana popup de error
```

**Codificación de log:**
- `[ERROR]` → Rojo (problemas que detienen el flujo)
- `[WARN]` → Naranja (advertencias)
- `[OK]` → Verde (éxito)
- `[INFO]` → Blanco (información general)
- `[SKIP]` → Cyan (ONU saltada)

---

### **3. `csv_logic.py` - Parseo de Datos**

**Función principal:**
```python
parse_smartolt_csv(path: str) -> list[dict]
```

Transforma CSV de SmartOLT en lista de diccionarios con parámetros de ONU.

**Columnas requeridas en CSV:**
| Columna | Tipo | Descripción |
|---------|------|-------------|
| OLT | string | Nombre OLT (debe existir en `OLT_MAP` de config.py) |
| Board | int | Número de slot/placa GPON |
| Port | int | Puerto GPON (0-4 típicamente) |
| Allocated ONU | int | ID de la ONU (1-64) |
| Service port VLAN | int | VLAN de servicio en SmartOLT |

**Columnas opcionales:**
| Columna | Descripción |
|---------|-------------|
| Onu Type | Tipo de ONU (informativo) |
| Name | Identificador o usuario PPPoE |

**Proceso de validación:**
- Verifica tipo de dato (int vs string)
- Salta filas corruptas sin abortar ejecución
- Normaliza espacios en blanco
- Agrupa por OLT para procesamiento eficiente

---

### **4. `ssh_client.py` - Capa de Conexión SSH**

**Librería:** Netmiko (soporte multi-vendor)

```python
connect_olt(ip: str, user: str, password: str, port: int) -> ConnectHandler
close_olt(conn: ConnectHandler) -> None
```

**Configuración Netmiko:**
- `device_type: "huawei"` - Detecta automáticamente OLTs Huawei
- `global_cmd_verify: False` - Evita verificación de eco de comandos
- `session_log: "session.txt"` - Archivo de audit completo
- `fast_cli: False` - Modo estándar para confiabilidad

**Característica de cierre seguro:**
- `close_olt()` no lanza excepciones, es idempotente

---

### **5. `omci.py` - Comandos OMCI/CLI (343 líneas)**

**Funciones principales:**

#### `provision_onu()`
Configura una ONU individual con parámetros de TR-069.

```python
provision_onu(
    conn,                    # Conexión Netmiko
    olt_name: str,          # Nombre OLT para lookup de config
    slot: int,              # Slot GPON
    port: int,              # Puerto GPON
    onu_id: int,            # ID ONU (1-64)
    onu_type: str,          # Tipo ONU
    pppoe_user: str,        # Usuario PPPoE (mostrado en logs)
    vlan: int,              # VLAN de servicio
    logger,                 # Función de log (ui.write_log)
    eliminar_wan_pppoe=False,  # Limpia WAN anterior
    crear_wan_ip=False         # Configura DHCP
)
```

**Dispatcher a flujos específicos:**
- Huawei: Llama `_provision_huawei_onu()`
- ZTE: Llama `_provision_zte_onu()`

#### `_provision_huawei_onu()`
Implementación específica para OLTs Huawei (Diagrama de flujo):

```
Entrar interface gpon 0/{slot}
  ↓
Si eliminar_wan_pppoe=True:
  → Ejecutar comando de eliminación de WAN
  ↓
Si crear_wan_ip=True:
  → Crear service-port en VLAN 150
  → Configurar IP DHCP
  ↓
Configurar PPPoE (tr069 user/password)
  ↓
Configurar TR-069 (profile-id según OLT)
  ↓
Salir interface gpon
  ↓
[OK] ONU XXXX (pppoe_user) en OLTNAME
```

**Comandos por OLT:**

**Villa Dolores 2:**
```
service-port vlan 150 gpon 0/{slot}/{port} ont {onu_id} gemport 2 multi-service \
  user-vlan 150 tag-transform translate \
  inbound traffic-table name SMARTOLT-VOIPMNG-10M \
  outbound traffic-table name SMARTOLT-VOIPMNG-10M

interface gpon 0/{slot}
ont ipconfig {port} {onu_id} ip-index 0 dhcp vlan 150 priority 2
ont tr069-server-config {port} {onu_id} profile-id 2
```

**OLT(San_Jose) / OLTHUAWEI:**
```
interface gpon 0/{slot}
ont tr069-server-config {port} {onu_id} profile-id 1
```

**Configuración PPPoE (común a todos):**
```
interface gpon 0/{slot}
ont ipconfig {port} {onu_id} pppoe user-account \
  username tr069 password 123 vlan {vlan} priority 0
```

#### `_provision_zte_onu()`
Implementación para OLT ZTE C600:

```python
pon-onu-mng gpon_onu-1/{slot}/{port}:{onu_id}
quit
```

#### `check_onu_tr069_profile()`
Valida si una ONU ya tiene TR-069 configurado (nuevo en v2026-02-14).

```python
check_onu_tr069_profile(
    conn,
    olt_name: str,
    slot: int,
    port: int,
    onu_id: int,
    logger
) -> bool
```

**Proceso:**
1. Entra en interface gpon
2. Ejecuta `display ont info {port} {onu_id}`
3. **Lee múltiples páginas** (paginación con "Press 'Q' to break")
4. Busca campo `TR069 server profile ID : {X}`
5. Retorna `True` si encontrado, `False` si no

**Manejo de paginación:**
- Detecta markers: `"---- More ----"`, `"Press 'Q' to break"`, etc.
- Envía espacio en blanco para avanzar página
- Itera hasta 15 veces para leer todo el output

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
    pppoe_user: str,
    logger
) -> bool
```

**Proceso:**
1. Consulta: `display service-port port 0/{slot}/{port} ont {onu_id}`
2. Parsea output buscando coincidencias con VLAN deseada
3. Para cada service-port: `undo service-port {sp_id}`
4. Log: `[OK] Eliminado service-port X, VLAN XXX para ONU YYYY (pppoe_user)`

#### `validate_omci_output()`
Ejecuta comandos con retry automático para OLT ocupada.

```python
validate_omci_output(conn, cmd: str, logger, max_retries=10) -> str
```

**Características:**
- Detecta patrones de "OLT ocupada" (backup, reporte en ejecución)
- Reintenta automáticamente cada 200 segundos
- Lanza excepción después de N fallos (default: 10)
- Retorna output del comando

**Patrones detectados:**
```
"It will take several minutes to..."
"The percentage of saved data on..."
"Failure: System is busy"
```

---

### **6. `config.py` - Configuración General (120+ líneas)**

**Diccionarios principales:**

#### `OLT_MAP`
Mapea nombres SmartOLT a credenciales SSH reales.

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

#### `ACS`
Parámetros compartidos para configuración TR-069:

```python
ACS = {
    "ip": "http://138.59.172.24",        # Dirección del servidor ACS
    "port": 7547,                         # Puerto CWMP
    "pppoe_user": "tr069",                # Usuario TR-069 en ONU
    "pppoe_password": "123",              # Password TR-069
    "user": "miCpeUser",                  # Usuario Admin en ONU
    "password": "Passw0rdACS!23#",        # Password Admin
    "prioridad": 0,                       # CoS de VLAN (0-7)
}
```

#### `EXEC`
Parámetros dinámicos de ejecución:

```python
EXEC = {
    "batch_size": 50,                   # Tamaño de lote
    "delay_between_onus": 0.2,          # Espera estándar entre ONUs (segundos)
    "delay_between_onus_largo": 200,    # Espera ante OLT ocupada (segundos)
}
```

#### `OLT_COMMANDS`
Plantillas de comandos OMCI por OLT:

```python
OLT_COMMANDS = {
    "Villa Dolores 2": {
        "traffic-table name": "SMARTOLT-VOIPMNG-10M",
        "profile-id": 2,
        "wan-config enabled": True,
    },
    "OLT(San_Jose)": {
        "traffic-table index": 7,
        "profile-id": 1,
        "wan-config enabled": False,
    },
    # ... más OLTs
}
```

---

## 🔄 Flujo de Ejecución Detallado

### 1. **Inicio**
```
Ejecutable: tr069_wizard.exe
↓
main() en app.py
↓
Crea GUI Tkinter (gui.py)
```

### 2. **Usuario selecciona opciones**
- **Archivo CSV:** SmartOLT export
- **Checkboxes (opcionales):**
  - `skip_tr069_configured` - No reprovisionar ONUs ya configuradas
  - `eliminar_wan_pppoe` - Borra WAN anterior antes de provisionar
  - `crear_wan_ip` - Crea IP DHCP en VLAN 150
  - `rollback_serviceport` - Solo elimina puertos (no provisiona)

### 3. **Validación de CSV**
```
parse_smartolt_csv(path)
  ├─ Lee archivo con pandas
  ├─ Valida columnas requeridas
  ├─ Normaliza tipos (int, string)
  ├─ Salta filas corruptas sin abortar
  └─ Retorna lista de dicts
```

### 4. **Agrupación por OLT**
```python
by_olt = defaultdict(list)
# Ejemplo: {"Villa Dolores 2": [onu1, onu2, ...]}
```

### 5. **Para cada OLT:**

#### a) Crear SessionManager
#### b) Cargar checkpoint (recuperación ante fallos)
#### c) Conectar a OLT (con reintentos automáticos)
#### d) Ejecutar post_connect_hook (entrar en config mode)
#### e) Para cada ONU:
- Validar TR-069 si está habilitada esa opción
- Rollback O Provisioñar según checkbox
#### f) Actualizar progreso y checkpoints
#### g) Reconectar cada 200 ONUs

---

## ⚙️ Parámetros de Reconexión

El `SessionManager` mantiene la conexión SSH viva reciclándola cada N ONUs procesadas:

```python
RECONNECT_THRESHOLD = 200      # Reconectar cada 200 ONUs
RECONNECT_DELAY = 2            # Esperar 2s antes de reconectar
RECONNECT_RETRIES = 3          # 3 intentos máximo
RECONNECT_BACKOFF = 5          # Backoff exponencial: 5s, 10s, 15s...
```

**Motivo:** Evita timeout SSH y memory leak en OLTs tras conexión larga.

---

## 📊 Estructura de Datos

### CSV Parseado → Dict
```python
{
    "olt_name": "Villa Dolores 2",
    "slot": 1,
    "port": 0,
    "onu_id": 45,
    "onu_type": "EG8141A5",
    "pppoe_user": "Jcuello",
    "vlan": 140,
}
```

### Checkpoint (archivo)
```
Ubicación: checkpoints/Villa_Dolores_2.ckp
Contenido: "150"
Significado: Última ONU procesada (ID 150)
```

### Log (file + GUI)
```
[2026-02-14 09:47:30] [OK] Conectado a Villa Dolores 2 (intent 1)
[2026-02-14 09:47:33] [OK] ONU 45 (Jcuello) en Villa Dolores 2
[2026-02-14 09:47:35] [SKIP] ONU 50 (agvilcazana) ya tiene TR-069 configurado, saltando
[2026-02-14 09:47:36] [ERROR] ONU 62 (admin) en Villa Dolores 2: Connection reset
```

---

## 📋 Casos de Uso Comunes

### **Caso 1: Provisionar ONUs nuevas con TR-069**
- ✓ Archivo CSV: ONUs a provisionar
- ✓ Marcar: "skip_tr069_configured"
- ✓ Desmarcar: otras opciones
- Resultado: ONUs configuradas + se conectan a ACS tras reboot

### **Caso 2: Crear interfaz de management DHCP**
- ✓ Archivo CSV
- ✓ Marcar: "crear_wan_ip"
- Resultado: IP DHCP en VLAN 150 + acceso directo a ONU

### **Caso 3: Limpiar WAN anterior**
- ✓ Archivo CSV
- ✓ Marcar: "eliminar_wan_pppoe"
- Resultado: WAN antigua eliminada, nueva PPPoE configurada

### **Caso 4: Rollback (solo eliminación)**
- ✓ Archivo CSV
- ✓ Marcar: "rollback_serviceport"
- Resultado: Service-ports eliminados, ONUs limpias

---

## 🐛 Manejo de Errores

### **OLT ocupada (Backup en progreso)**
```
Reintentos: automaticos hasta 10 veces
Delay: 200 segundos entre intentos
Log: [WARN] OLT ocupada al ejecutar '...', reintentando en 200s (intento 3/10)
```

### **Conexión SSH falla**
```
Reintentos: hasta 3 veces
Backoff: 5s, 10s, 15s exponencial
Log: [ERROR] No se pudo conectar a OLT después de 3 intentos
```

### **CSV inválido**
```
Resultado: Ventana popup de error
Log: [ERROR] CSV inválido: Falta columna...
```

### **ONU individual falla**
```
Acción: Log de error + continúa con siguiente ONU
Log: [ERROR] ONU 45 (Jcuello) en Villa Dolores 2: Connection reset
```

---

## 📦 Dependencias

```
netmiko==4.6.0          # SSH a equipos de red
pandas==2.3.3           # Parseo CSV
paramiko==4.0.0         # SSH subyacente
cryptography==46.0.3    # Cifrado
```

---

## 🚀 Compilación a Ejecutable

```powershell
# Ejecutar compilación
pyinstaller ProvisionOnus.spec

# Resultado
dist\tr069_wizard.exe      # ← Ejecutable standalone
```

El ejecutable es **completamente independiente:**
- Incluye todas las librerías Python
- No requiere instalación de Python
- Funciona en máquinas sin desarrollo
- Puede portarse en pen drive

---

## 📁 Archivos Generados en Ejecución

```
logs/
  ejecucion_2026-02-14-094728.log    # Log detallado

checkpoints/
  Villa_Dolores_2.ckp               # Contador de ONUs
  OLTHUAWEI.ckp

session.txt                         # Trace SSH completo
```

---

## 🎯 Últimas Mejoras (v2026-02-14)

✅ Validación de ONUs con TR-069 ya configurado  
✅ Skip automático para evitar re-provisionar  
✅ Manejo correcto de paginación en "display ont info"  
✅ Logging mejorado: Incluye PPPoE user en cada mensaje  
✅ Executable standalone: `tr069_wizard.exe`  
✅ Reducción de debug spam  
✅ Refactorización de funciones OMCI (120 líneas)  

---

## 📞 Soporte

**Archivos principales:**
- [config.py](config.py) - OLT_MAP, ACS, EXEC, OLT_COMMANDS
- [app.py](app.py) - SessionManager + orquestador
- [omci.py](omci.py) - Comandos OMCI
- [gui.py](gui.py) - Interfaz Tkinter

**Para agregar OLT:** Editar `OLT_MAP` + `OLT_COMMANDS` en config.py

**Para cambiar ACS:** Editar diccionario `ACS` en config.py

---

*Documentación actualizada: 2026-02-14*  
*Versión: Ejecutable tr069_wizard.exe con validación TR-069*
