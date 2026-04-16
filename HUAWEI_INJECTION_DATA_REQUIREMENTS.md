# Inyección Huawei - Análisis de Datos Requeridos

## 1. DATOS QUE TRAES DEL CSV (columnas obligatorias)

El CSV para inyección Huawei debe tener estas columnas:

| Columna | Origen | Descripción | Ejemplo |
|---------|--------|-------------|---------|
| **PON_DESTINO** | CSV (debe tener) | Puerto PON en la OLT donde irá la ONT | `gpon_olt-1/4/10` o `1/4/10` |
| **ID** o **HUAWEI_ONU_ID** o **ZTE_ONU_ID** | CSV (una de las tres) | Identificador numérico de la ONT (0-255) | `1`, `2`, `145` |
| **SN** | CSV (debe tener) | Serial Number de la ONT física | `ZTEGD6D13F10` o `HWTC459785B2` |
| **PPPoE_USER** | CSV (debe tener) | Usuario PPPoE (login del cliente) | `ibgallardo`, `pjcalderon` |
| **ONT_MODE** | CSV (debe tener) | Modo de provisión | `ROUTER` o `BRIDGE` |
| **ONT_MODEL** | CSV (debe tener) | Modelo de la ONT (desde BDCOM backup) | `EG8021V5`, `EG8141A5`, `HG8245H` |

**Nota:** 
- El código acepta flexibilidad en el nombre de la columna de ID:
 - Si existe columna `ID` → la usa
- Si existe `HUAWEI_ONU_ID` → la usa
 - Si existe `ZTE_ONU_ID` → la usa (como hiciste con ZTE)
- El modelo ONT define automáticamente qué perfiles de línea y servicio se usan

---

## 2. DATOS QUE YA TIENES EN .env (Perfiles & Tablas)

Estos se cargan automáticamente desde `.env` y se usan en todos los ONUs:

| Variable | Valor Actual | Uso |
|----------|-------------|-----|
| **HUAWEI_VLAN_ID** | `700` | VLAN para todas las ONTs |
| **HUAWEI_TRAFFIC_TABLE_UP** | `6` | Tabla de tráfico descendente (perfil) |
| **HUAWEI_TRAFFIC_TABLE_DOWN** | `6` | Tabla de tráfico ascendente (perfil) |
| **HUAWEI_LINE_PROF_ROUTER** | `10` | Profile ID de línea para ONTs en modo ROUTER |
| **HUAWEI_SRV_PROF_ROUTER** | `10` | Profile ID de servicio para ONTs en modo ROUTER |
| **HUAWEI_LINE_PROF_BRIDGE** | `20` | Profile ID de línea para ONTs en modo BRIDGE |
| **HUAWEI_SRV_PROF_BRIDGE** | `20` | Profile ID de servicio para ONTs en modo BRIDGE |
| Variable | Valor Actual | Uso |
|----------|-------------|-----|
| **HUAWEI_VLAN_ID** | `700` | VLAN para todas las ONTs |
| **HUAWEI_TRAFFIC_TABLE_UP** | `8` | Tabla de tráfico bajada (inbound) |
| **HUAWEI_TRAFFIC_TABLE_DOWN** | `9` | Tabla de tráfico subida (outbound) |
| **HUAWEI_ONT_MODE_PROFILES** | `EG8021V5:1:2,EG8141A5:1:1,HG8245H:1:4` | Mapeo modelo→(line_prof, srv_prof) |
| **HUAWEI_LINE_PROF_DEFAULT** | `6` | Perfil línea fallback (Generic_1_V700) |
| **HUAWEI_SRV_PROF_DEFAULT** | `3` | Perfil servicio fallback (Generic_1_V700) |

---

## 3. DATOS QUE DEBES CONFIRMAR CON EXACTITUD (ONT DUMMY en SmartOLT)

Estos datos vienen de la **ONT dummy** que creaste en SmartOLT. La OLT Huawei usará estos mismos IDs/perfiles.

### ✅ YA CONFIRMADO CON TU SALIDA DE OLT

Tu ONT dummy se provisiona con:
- **Line Profile**: 6 (Generic_1_V700)
- **Service Profile**: 3 (Generic_1_V700)
- **VLAN**: 700 ✓
- **Traffic Tables**: inbound=8, outbound=9

### Modelos Encontrados en tu OLT:
- **EG8021V5** → Line Profile 1, Service Profile 2
- **EG8141A5** → Line Profile 1, Service Profile 1
- **HG8245H** → Line Profile 1, Service Profile 4
- **Otros modelos** → Fallback a Line Profile 6, Service Profile 3 (Generic)

### 3.1 VLAN ID
La ONT dummy probablemente se provisiona en una VLAN específica.

**¿Qué debes verificar?**
```
service-port vlan XXX gpon 1/4/10 ont 1 gemport 1 multi-service user-vlan XXX ...
```
El valor `XXX` = tu `HUAWEI_VLAN_ID`

### 3.4 Tablas de Tráfico (Traffic Tables / QoS Profiles)
Las tablas se aplican con `rx-cttr` (recepción, bajada) y `tx-cttr` (transmisión, subida).

**¿Qué debes verificar?**
```
service-port vlan 700 gpon 1/4/10 ont 1 gemport 1 multi-service user-vlan 700 rx-cttr 6 tx-cttr 6
```
En este caso: `TRAFFIC_TABLE_UP=6`, `TRAFFIC_TABLE_DOWN=6` ✓

---

## 4. COMANDO QUE SE GENERARÁ POR CADA ONU DEL CSV

### Ejemplo ROUTER (desde CSV):
```
PON_DESTINO: gpon_olt-1/4/10
HUAWEI_ONU_ID: 1
SN: ZTEGD6D13F10
PPPoE_USER: ibgallardo
ONT_MODE: ROUTER
```

**Comandos generados:**
```
interface gpon 1/4
ont add 10 1 sn-auth ZTEGD6D13F10 omci ont-lineprofile-id 10 ont-srvprofile-id 10 desc "ibgallardo"
quit
service-port vlan 700 gpon 1/4/10 ont 1 gemport 1 multi-service user-vlan 700 rx-cttr 6 tx-cttr 6
```

### Ejemplo BRIDGE (desde CSV):
```
PON_DESTINO: gpon_olt-1/4/11
HUAWEI_ONU_ID: 2
SN: HWTC459785B2
PPPoE_USER: pjcalderon
ONT_MODE: BRIDGE
```

**Comandos generados:**
```
interface gpon 1/4
ont add 11 2 sn-auth HWTC459785B2 omci ont-lineprofile-id 20 ont-srvprofile-id 20 desc "pjcalderon"
ont port native-vlan 11 2 eth 1 vlan 700
quit
service-port vlan 700 gpon 1/4/11 ont 2 gemport 1 multi-service user-vlan 700 rx-cttr 6 tx-cttr 6
```

---

## 5. CHECKLIST: ¿QUÉ DATOS NECESITAS CONSEGUIR?

### ✅ YA TIENES (en `.env`):
- [x] HUAWEI_VLAN_ID
- [x] HUAWEI_TRAFFIC_TABLE_UP / DOWN
- [x] HUAWEI_LINE_PROF_ROUTER / BRIDGE
- [x] HUAWEI_SRV_PROF_ROUTER / BRIDGE

### ⚠️ DEBES VERIFICAR (desde ONT dummy en SmartOLT/OLT):
- [ ] Confirmar que los `LINE_PROF_*` actuales (10 y 20) existen y funcionan
- [ ] Confirmar que los `SRV_PROF_*` actuales (10 y 20) existen y funcionan
- [ ] Confirmar que las **tablas de tráfico 6** (rx-cttr, tx-cttr) son válidas
- [ ] Confirmar que la **VLAN 700** existe en la OLT
- [ ] Confirmar que la ONT dummy se provisionó correctamente y está up

### 📋 NECESITAS EN EL CSV (por cada ONT):
- [ ] PON_DESTINO (ejemplo: `gpon_olt-1/4/10`, `1/4/10`)
- [ ] ID / HUAWEI_ONU_ID / o ZTE_ONU_ID (número 0-255)
- [ ] SN (Serial Number exacto de la ONT física)
- [ ] PPPoE_USER (login del cliente)
- [ ] ONT_MODE (`ROUTER` o `BRIDGE`)

---

## 6. PRÓXIMOS PASOS

1. **Conecta a la OLT Huawei por SSH y ejecuta:**
   ```
   display ont autofind all
   display service-port 1
   display gpon onu-lineprofile all
   display gpon onu-srvprofile all
   display vlan
   ```
   Esto te mostrará qué perfiles existen realmente.

2. **Verifica el running-config de la ONT dummy:**
   ```
   display current-configuration gpon-onu ...
   ```
   Copia aquí los perfiles exactos que SmartOLT asignó.

3. **Actualiza `.env` con los valores reales** si difieren de los actuales (10, 20, 6, 700).

4. **Prepara el CSV** con los datos de tus ONTs (PON_DESTINO, SN, ID, PPPoE_USER, ONT_MODE).

5. **Prueba con dry-run** antes de ejecutar real:
   ```
   ✓ Modo Simulación activado
   ✓ Revisar los comandos en el log
   ✓ Verificar que tengan sentido
   ✓ Ejecutar real si todo se ve correcto
   ```
