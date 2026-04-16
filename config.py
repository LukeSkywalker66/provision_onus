"""
TR-069 Wizard - Configuración desde Variables de Entorno

Este módulo carga todas las configuraciones desde un archivo .env
para evitar hardcodear credenciales sensibles.

IMPORTANTE: El archivo .env se crea desde .env.example y no debe commiterse a git.
"""

import os
from dotenv import load_dotenv

# Cargar variables de .env (si existe, sino usa valores por defecto)
load_dotenv()


def _load_olt_config(olt_number):
    """
    Carga configuración de un OLT desde variables de entorno.
    
    Busca:
    - OLT_{N}_NAME: Nombre que aparece en CSV de SmartOLT
    - OLT_{N}_IP: Dirección IP o hostname
    - OLT_{N}_USER: Usuario SSH
    - OLT_{N}_PASSWORD: Password SSH
    - OLT_{N}_PORT: Puerto SSH (default: 22)
    - OLT_{N}_VENDOR: Fabricante (huawei | zte)
    """
    prefix = f"OLT_{olt_number}"
    name = os.getenv(f"{prefix}_NAME")
    
    if not name:
        return None  # Este número de OLT no está configurado
    
    return {
        "ip": os.getenv(f"{prefix}_IP"),
        "user": os.getenv(f"{prefix}_USER"),
        "password": os.getenv(f"{prefix}_PASSWORD"),
        "port": int(os.getenv(f"{prefix}_PORT", 22)),
        "fabricante": os.getenv(f"{prefix}_VENDOR", "huawei"),
    }


# Construir OLT_MAP dinámicamente desde .env
# Soporta hasta 9 OLTs (OLT_1_NAME, OLT_2_NAME, ..., OLT_9_NAME)
OLT_MAP = {}
for i in range(1, 10):
    config = _load_olt_config(i)
    if config:
        olt_name = os.getenv(f"OLT_{i}_NAME")
        OLT_MAP[olt_name] = config

# Parámetros TR-069 / ACS desde .env
ACS = {
    "ip": os.getenv("ACS_IP", "http://138.59.172.24"),
    "port": int(os.getenv("ACS_PORT", 7547)),
    "pppoe_user": os.getenv("ACS_PPPOE_USER", "tr069"),
    "pppoe_password": os.getenv("ACS_PPPOE_PASSWORD", "123"),
    "user": os.getenv("ACS_USER", "miCpeUser"),
    "password": os.getenv("ACS_PASSWORD", "Passw0rdACS!23#"),
    "prioridad": int(os.getenv("ACS_PRIORITY", 0)),
}

# Parámetros de ejecución desde .env
EXEC = {
    "batch_size": int(os.getenv("BATCH_SIZE", 50)),
    "delay_between_onus": float(os.getenv("DELAY_BETWEEN_ONUS", 0.2)),
    "delay_between_onus_largo": int(os.getenv("DELAY_BETWEEN_ONUS_LONG", 200)),
}


def _parse_mode_overrides(raw_value: str):
    """
    Parsea regla de overrides por prefijo de modelo desde .env.

    Formato esperado:
    MIGRATION_MODE_OVERRIDES=ZTE=ROUTER,HWTC=BRIDGE
    """
    overrides = {}
    if not raw_value:
        return overrides

    for chunk in raw_value.split(","):
        item = chunk.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        model_prefix = key.strip().upper()
        mode = value.strip().upper()
        if not model_prefix:
            continue
        if mode not in {"ROUTER", "BRIDGE"}:
            continue
        overrides[model_prefix] = mode

    return overrides


MIGRATION_MODE_OVERRIDES = _parse_mode_overrides(os.getenv("MIGRATION_MODE_OVERRIDES", ""))


def get_mode_override_for_model(ont_model: str):
    """
    Retorna ROUTER/BRIDGE si hay override por prefijo de modelo.
    Si no hay regla, retorna cadena vacía.
    """
    model = (ont_model or "").strip().upper()
    if not model:
        return ""

    for prefix, mode in MIGRATION_MODE_OVERRIDES.items():
        if model.startswith(prefix):
            return mode
    return ""


# ============================================================================
# Configuración para Inyección Huawei (PREPROVISIONAMIENTO)
# ============================================================================

def _parse_ont_mode_profiles(raw_value: str):
    """
    Parsea mapeo de modelos ONT a perfiles Huawei desde .env.
    
    Formato esperado:
    HUAWEI_ONT_MODE_PROFILES=EG8021V5:1:2,EG8141A5:1:1,HG8245H:1:4
    
    Retorna dict: {"EG8021V5": (1, 2), "EG8141A5": (1, 1), ...}
    """
    mapping = {}
    if not raw_value:
        return mapping
    
    for chunk in raw_value.split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        parts = chunk.split(":")
        if len(parts) != 3:
            continue
        
        ont_model = parts[0].strip().upper()
        try:
            line_prof = parts[1].strip()
            srv_prof = parts[2].strip()
            mapping[ont_model] = (line_prof, srv_prof)
        except (ValueError, IndexError):
            continue
    
    return mapping


HUAWEI_INJECTION = {
    "vlan_id": os.getenv("HUAWEI_VLAN_ID", "700"),
    "traffic_table_up": os.getenv("HUAWEI_TRAFFIC_TABLE_UP", "8"),
    "traffic_table_down": os.getenv("HUAWEI_TRAFFIC_TABLE_DOWN", "9"),
    "line_prof_default": os.getenv("HUAWEI_LINE_PROF_DEFAULT", "6"),
    "srv_prof_default": os.getenv("HUAWEI_SRV_PROF_DEFAULT", "3"),
}

# Mapeo de modelos ONT a perfiles (line_profile_id, service_profile_id)
_ONT_MODE_PROFILES = _parse_ont_mode_profiles(os.getenv("HUAWEI_ONT_MODE_PROFILES", ""))


def get_huawei_injection_params():
    """
    Retorna diccionario con parámetros básicos de inyección Huawei desde config.
    Todos los valores son strings para facilitar interpolación en CLI.
    """
    return HUAWEI_INJECTION.copy()


def get_huawei_profiles_for_ont_model(ont_model: str):
    """
    Busca los perfiles (line_profile_id, service_profile_id) para un modelo ONT específico.
    
    Si el modelo está en el mapeo -> retorna (line_prof, srv_prof)
    Si no -> retorna los perfiles default (fallback genérico)
    
    Args:
        ont_model: Modelo de la ONT (ej: "EG8021V5", "HG8245H")
    
    Returns:
        Tupla (line_profile_id, service_profile_id) como strings
    """
    model = (ont_model or "").strip().upper()
    
    # Buscar en el mapeo específico
    if model in _ONT_MODE_PROFILES:
        return _ONT_MODE_PROFILES[model]
    
    # Fallback: usar perfiles genéricos
    return (HUAWEI_INJECTION["line_prof_default"], HUAWEI_INJECTION["srv_prof_default"])


# Comandos OMCI específicos por OLT y modo
# IMPORTANTE: Cada OLT tiene configuración única (profile-ids, traffic-tables, etc.)
OLT_COMMANDS = {
    "Villa Dolores 2": {
        "crear_wan_ip": {
            "service_port": "service-port vlan 150 gpon 0/{slot}/{port} ont {onu_id} gemport 2 multi-service user-vlan 150 tag-transform translate inbound traffic-table name SMARTOLT-VOIPMNG-10M outbound traffic-table name SMARTOLT-VOIPMNG-10M",
            "interface_gpon": "interface gpon 0/{slot}",
            "ipconfig": "ont ipconfig {port} {onu_id} ip-index 0 dhcp vlan 150 priority 2",
            "tr069_profile_id": 2,
            "tr069": "ont tr069-server-config {port} {onu_id} profile-id 2",
        },
        "eliminar_wan_pppoe": {
            "undo_wan_config": "undo ont wan-config {port} {onu_id} ip-index 0",
            "undo_ipconfig": "undo ont ipconfig {port} {onu_id} ip-index 0",
        },
        "crear_wan_pppoe": {
            "interface_gpon": "interface gpon 0/{slot}",
            "ipconfig": "ont ipconfig {port} {onu_id} pppoe user-account username {pppoe_user} password {pppoe_password} vlan {vlan} priority {prioridad}",
            "wan_config": "ont wan-config {port} {onu_id} ip-index 0 profile-id 1",
            "tr069_profile_id": 2,
            "tr069": "ont tr069-server-config {port} {onu_id} profile-id 2",
        },
    },
    "OLT(San_Jose)": {
        "crear_wan_ip": {
            "service_port": "service-port vlan 150 gpon 0/{slot}/{port} ont {onu_id} gemport 2 multi-service user-vlan 150 tag-transform translate inbound traffic-table index 7 outbound traffic-table index 7",
            "interface_gpon": "interface gpon 0/{slot}",
            "ipconfig": "ont ipconfig {port} {onu_id} ip-index 0 dhcp vlan 150 priority 2",
            "tr069_profile_id": 1,
            "tr069": "ont tr069-server-config {port} {onu_id} profile-id 1",
        },
        "eliminar_wan_pppoe": {
            "undo_ipconfig": "undo ont ipconfig {port} {onu_id} ip-index 0",
        },
        "crear_wan_pppoe": {
            "interface_gpon": "interface gpon 0/{slot}",
            "ipconfig": "ont ipconfig {port} {onu_id} pppoe user-account username {pppoe_user} password {pppoe_password} vlan {vlan} priority {prioridad}",
            "tr069_profile_id": 1,
            "tr069": "ont tr069-server-config {port} {onu_id} profile-id 1",
        },
    },
    "OLTHUAWEI": {
        "crear_wan_ip": {
            "service_port": "service-port vlan 150 gpon 0/{slot}/{port} ont {onu_id} gemport 2 multi-service user-vlan 150 tag-transform translate inbound traffic-table index 7 outbound traffic-table index 7",
            "interface_gpon": "interface gpon 0/{slot}",
            "ipconfig": "ont ipconfig {port} {onu_id} ip-index 0 dhcp vlan 150 priority 2",
            "tr069_profile_id": 1,
            "tr069": "ont tr069-server-config {port} {onu_id} profile-id 1",
        },
        "eliminar_wan_pppoe": {
            "undo_ipconfig": "undo ont ipconfig {port} {onu_id} ip-index 0",
        },
        "crear_wan_pppoe": {
            "interface_gpon": "interface gpon 0/{slot}",
            "ipconfig": "ont ipconfig {port} {onu_id} pppoe user-account username {pppoe_user} password {pppoe_password} vlan {vlan} priority {prioridad}",
            "tr069_profile_id": 1,
            "tr069": "ont tr069-server-config {port} {onu_id} profile-id 1",
        },
    },
    "ZTE C600": {
        "crear_wan_ip": {
            "interface_gpon": "interface gpon 0/{slot}",
            "ipconfig": "ont ipconfig {port} {onu_id} ip-index 0 dhcp vlan 150 priority 2",
            "tr069_profile_id": None,
            "tr069": None,
        },
        "eliminar_wan_pppoe": {
            "undo_ipconfig": "undo ont ipconfig {port} {onu_id} ip-index 0",
        },
        "crear_wan_pppoe": {
            "interface_gpon": "interface gpon 0/{slot}",
            "ipconfig": "ont ipconfig {port} {onu_id} pppoe user-account username {pppoe_user} password {pppoe_password} vlan {vlan} priority {prioridad}",
            "tr069_profile_id": None,
            "tr069": None,
        },
    },
}

# Log de configuración al importar
if __name__ != "__main__":
    # Solo imprimir cuando se importa, no cuando se ejecuta directamente
    if OLT_MAP:
        print(f"[CONFIG] Cargadas credenciales para {len(OLT_MAP)} OLT(s) desde .env")
    else:
        import warnings
        warnings.warn(
            "[CONFIG] No se encontraron OLTs en .env - "
            "Ejecuta: cp .env.example .env && edita .env con tus credenciales",
            RuntimeWarning
        )
