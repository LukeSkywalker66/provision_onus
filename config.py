"""
TR-069 Wizard - Configuración desde Variables de Entorno

Este módulo carga todas las configuraciones desde un archivo .env
para evitar hardcodear credenciales sensibles.

IMPORTANTE: El archivo .env se crea desde .env.example y no debe commiterse a git.
"""

import os
import re
from typing import Dict, List, Tuple
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


def _load_mikrotik_config(node_number):
    """
    Carga configuración de un nodo MikroTik API desde variables de entorno.

    Busca:
    - MIKROTIK_{N}_NAME: Nombre amigable del nodo
    - MIKROTIK_{N}_IP: Dirección IP o hostname
    - MIKROTIK_{N}_USER: Usuario API
    - MIKROTIK_{N}_PASSWORD: Password API
    - MIKROTIK_{N}_PORT: Puerto API (default: 8728)
    """
    prefix = f"MIKROTIK_{node_number}"
    name = os.getenv(f"{prefix}_NAME")

    if not name:
        return None

    return {
        "ip": os.getenv(f"{prefix}_IP"),
        "user": os.getenv(f"{prefix}_USER"),
        "password": os.getenv(f"{prefix}_PASSWORD"),
        "port": int(os.getenv(f"{prefix}_PORT", 8728)),
    }


# Construir OLT_MAP dinámicamente desde .env
# Soporta hasta 9 OLTs (OLT_1_NAME, OLT_2_NAME, ..., OLT_9_NAME)
OLT_MAP = {}
for i in range(1, 10):
    config = _load_olt_config(i)
    if config:
        olt_name = os.getenv(f"OLT_{i}_NAME")
        OLT_MAP[olt_name] = config

# OLT objetivo para módulo de inyección Huawei (preaprovisionamiento)
HUAWEI_INJECTION_OLT_NAME = os.getenv("HUAWEI_INJECTION_OLT_NAME", "OLT-LasTapias-HW").strip()


# Construir MIKROTIK_MAP dinámicamente desde .env
# Soporta hasta 9 nodos (MIKROTIK_1_NAME, ..., MIKROTIK_9_NAME)
MIKROTIK_MAP = {}
for i in range(1, 10):
    node = _load_mikrotik_config(i)
    if node:
        node_name = os.getenv(f"MIKROTIK_{i}_NAME")
        MIKROTIK_MAP[node_name] = node

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

# Parámetros API SmartOLT para movimientos de ONUs
SMARTOLT = {
    "base_url": os.getenv("SMARTOLT_BASEURL", "").strip(),
    "token": os.getenv("SMARTOLT_TOKEN", "").strip(),
    "olt_id": int(os.getenv("SMARTOLT_OLT_ID", "1")),
    "timeout": int(os.getenv("SMARTOLT_TIMEOUT", "20")),
    "retries": int(os.getenv("SMARTOLT_RETRIES", "3")),
    "retry_delay": float(os.getenv("SMARTOLT_RETRY_DELAY", "1.0")),
    "move_delay": float(os.getenv("SMARTOLT_MOVE_DELAY", "0.2")),
    "delete_delay": float(os.getenv("SMARTOLT_DELETE_DELAY", os.getenv("SMARTOLT_MOVE_DELAY", "0.2"))),
    "mode_update_delay": float(os.getenv("SMARTOLT_MODE_UPDATE_DELAY", os.getenv("SMARTOLT_MOVE_DELAY", "0.2"))),
    "authorize_delay": float(os.getenv("SMARTOLT_AUTHORIZE_DELAY", os.getenv("SMARTOLT_MOVE_DELAY", "0.2"))),
    "authorize_pon_type": os.getenv("SMARTOLT_AUTHORIZE_PON_TYPE", "gpon").strip().lower(),
    "authorize_gpon_channel": os.getenv("SMARTOLT_AUTHORIZE_GPON_CHANNEL", "gpon").strip().lower(),
    "authorize_epon_channel": os.getenv("SMARTOLT_AUTHORIZE_EPON_CHANNEL", "epon").strip().lower(),
    "authorize_vlan": os.getenv("SMARTOLT_AUTHORIZE_VLAN", "").strip(),
    "authorize_zone": os.getenv("SMARTOLT_AUTHORIZE_ZONE", "").strip(),
    "authorize_odb": os.getenv("SMARTOLT_AUTHORIZE_ODB", "").strip(),
    "authorize_address": os.getenv("SMARTOLT_AUTHORIZE_ADDRESS", "").strip(),
    "authorize_allow_without_board_port": os.getenv("SMARTOLT_AUTHORIZE_ALLOW_WITHOUT_BOARD_PORT", "false").strip().lower() in {"1", "true", "yes", "on"},
    "authorize_default_mode": os.getenv("SMARTOLT_AUTHORIZE_DEFAULT_MODE", "Routing").strip(),
    "authorize_upload_profile": os.getenv("SMARTOLT_AUTHORIZE_UPLOAD_PROFILE", "").strip(),
    "authorize_download_profile": os.getenv("SMARTOLT_AUTHORIZE_DOWNLOAD_PROFILE", "").strip(),
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


def _parse_csv_upper_set(raw_value: str):
    values = set()
    if not raw_value:
        return values
    for chunk in raw_value.split(","):
        item = chunk.strip().upper()
        if item:
            values.add(item)
    return values


def _parse_csv_upper_list(raw_value: str):
    values = []
    if not raw_value:
        return values
    for chunk in raw_value.split(","):
        item = chunk.strip().upper()
        if item:
            values.append(item)
    return values


def _parse_key_value_upper_map(raw_value: str):
    mapping = {}
    if not raw_value:
        return mapping
    for chunk in raw_value.split(","):
        item = chunk.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        k = key.strip().upper()
        v = value.strip().upper()
        if k and v:
            mapping[k] = v
    return mapping


def _parse_oui_vendor_overrides(raw_value: str):
    """
    Parsea tabla OUI -> vendor desde .env.

    Formato esperado:
    MAC_OUI_VENDOR_OVERRIDES=F4F26D=TP-LINK,CC32E5=TP-LINK

    Soporta separadores en OUI (:", "-", ".") y los normaliza a 6 hex.
    """
    mapping = {}
    if not raw_value:
        return mapping

    for chunk in raw_value.split(","):
        item = chunk.strip()
        if not item or "=" not in item:
            continue
        raw_oui, raw_vendor = item.split("=", 1)
        oui = re.sub(r"[^0-9A-Fa-f]", "", raw_oui or "").upper()
        vendor = (raw_vendor or "").strip().upper()
        if len(oui) >= 6 and vendor:
            mapping[oui[:6]] = vendor
    return mapping


def _parse_ont_vendor_prefixes(raw_value: str):
    """
    Parsea mapeo de prefijos de modelo ONT a vendor lógico.

    Formato esperado:
    ONT_VENDOR_PREFIXES=ZTE=ZTE,F=ZTE,HG=HUAWEI,HS=HUAWEI,EG=HUAWEI

    Retorna lista ordenada de tuplas (prefix, vendor), preservando prioridad.
    """
    pairs: List[Tuple[str, str]] = []
    if not raw_value:
        return pairs

    for chunk in raw_value.split(","):
        item = chunk.strip()
        if not item or "=" not in item:
            continue
        prefix, vendor = item.split("=", 1)
        p = prefix.strip().upper()
        v = vendor.strip().upper()
        if p and v:
            pairs.append((p, v))
    return pairs


ENABLE_MAC_VENDOR_BRIDGE_HEURISTIC = os.getenv(
    "ENABLE_MAC_VENDOR_BRIDGE_HEURISTIC",
    "true",
).strip().lower() in {"1", "true", "yes", "on"}

MAC_BRIDGE_VENDOR_KEYWORDS = _parse_csv_upper_set(
    os.getenv("MAC_BRIDGE_VENDOR_KEYWORDS", "TP-LINK,TPLINK")
)

MAC_BRIDGE_ONU_VENDOR_ALLOWLIST = _parse_csv_upper_set(
    os.getenv("MAC_BRIDGE_ONU_VENDOR_ALLOWLIST", "HUAWEI,ICON,ORANGE")
)

SN_VENDOR_PREFIX_MAP = _parse_key_value_upper_map(
    os.getenv("SN_VENDOR_PREFIX_MAP", "ZTE=ZTE,HWT=HUAWEI,TPL=TPLINK")
)

MAC_VENDOR_KEYWORD_MAP = _parse_key_value_upper_map(
    os.getenv(
        "MAC_VENDOR_KEYWORD_MAP",
        "ZTE=ZTE,HUAWEI=HUAWEI,TP-LINK=TPLINK,TPLINK=TPLINK,MERCUSYS=TPLINK,ICON=ICON,ORANGE=ORANGE",
    )
)

KNOWN_ROUTER_MODEL_PREFIXES = _parse_csv_upper_list(
    os.getenv("KNOWN_ROUTER_MODEL_PREFIXES", "ZTE,F,HG,HS,EG,IC,OR,TX,XN")
)

SN_MAC_MISMATCH_BRIDGE_SN_VENDORS = _parse_csv_upper_set(
    os.getenv("SN_MAC_MISMATCH_BRIDGE_SN_VENDORS", "HUAWEI,ICON,ORANGE")
)

BRIDGE_ONLY_MODELS = _parse_csv_upper_set(
    os.getenv(
        "BRIDGE_ONLY_MODELS",
        "EG8021V5,GP1704-2FC-S,GP1705-2G,IC425ETB,HG8310M,TX-6610,HG8010H,HG8240H",
    )
)


HUAWEI_MAC_VALIDATION_MODEL_PREFIXES = _parse_csv_upper_list(
    os.getenv(
        "HUAWEI_MAC_VALIDATION_MODEL_PREFIXES",
        "EG8141A5,IC405WSG,HG8245H,HG8245H5,IC410WSG",
    )
)

MAC_OUI_VENDOR_OVERRIDES = _parse_oui_vendor_overrides(
    os.getenv("MAC_OUI_VENDOR_OVERRIDES", "")
)

ONT_VENDOR_PREFIXES = _parse_ont_vendor_prefixes(
    os.getenv(
        "ONT_VENDOR_PREFIXES",
        "IC=ICON,OR=ORANGE,HG=HUAWEI,HS=HUAWEI,EG=HUAWEI,ZTE=ZTE,F=ZTE",
    )
)

TPLINK_DEFAULT_ONT_MODEL = os.getenv("TPLINK_DEFAULT_ONT_MODEL", "TPLINK").strip() or "TPLINK"
try:
    TPLINK_SSH_ONU_DELAY = float(os.getenv("TPLINK_SSH_ONU_DELAY", "0.3"))
except Exception:
    TPLINK_SSH_ONU_DELAY = 0.3
TPLINK_SSH_BACKEND = os.getenv("TPLINK_SSH_BACKEND", "plink").strip().lower() or "plink"
TPLINK_PLINK_PATH = os.getenv("TPLINK_PLINK_PATH", r"C:\Program Files\PuTTY\plink.exe").strip()
TPLINK_PLINK_ARGS = os.getenv("TPLINK_PLINK_ARGS", "-load tplink_legacy").strip()

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


def get_ont_vendor_for_model(ont_model: str):
    """
    Retorna vendor lógico (ej: ZTE/HUAWEI) según prefijo de modelo ONT.
    Si no encuentra match, retorna cadena vacía.
    """
    model = (ont_model or "").strip().upper()
    if not model:
        return ""
    for prefix, vendor in ONT_VENDOR_PREFIXES:
        if model.startswith(prefix):
            return vendor
    return ""


def get_vendor_from_sn(sn: str):
    """
    Infere vendor ONU por prefijo del SN (prioriza prefijos más largos).
    """
    serial = (sn or "").strip().upper()
    if not serial:
        return ""

    for prefix in sorted(SN_VENDOR_PREFIX_MAP.keys(), key=len, reverse=True):
        if serial.startswith(prefix):
            return SN_VENDOR_PREFIX_MAP[prefix]
    return ""


def get_vendor_from_mac_vendor_name(mac_vendor: str):
    """
    Normaliza nombre de fabricante de MAC a vendor lógico por keywords.
    """
    name = (mac_vendor or "").strip().upper()
    if not name:
        return ""

    for keyword, vendor in MAC_VENDOR_KEYWORD_MAP.items():
        if keyword in name:
            return vendor
    return ""


def is_known_router_model(ont_model: str):
    model = (ont_model or "").strip().upper()
    if not model:
        return False
    return any(model.startswith(prefix) for prefix in KNOWN_ROUTER_MODEL_PREFIXES if prefix)


def is_bridge_only_model(ont_model: str):
    model = (ont_model or "").strip().upper()
    if not model:
        return False
    return model in BRIDGE_ONLY_MODELS


def is_huawei_mac_validation_model(ont_model: str):
    """
    Retorna True para modelos que requieren validación adicional por MAC Huawei.

    Se evalúa por prefijos para cubrir variantes/sufijos de un mismo modelo.
    """
    model = (ont_model or "").strip().upper()
    if not model:
        return False
    return any(
        model.startswith(prefix)
        for prefix in HUAWEI_MAC_VALIDATION_MODEL_PREFIXES
        if prefix
    )


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
    "cmd_delay": float(os.getenv("HUAWEI_INJECTION_CMD_DELAY", "0.4")),
    "max_retries": int(os.getenv("HUAWEI_INJECTION_MAX_RETRIES", "10")),
    "forbidden_prompt_prefixes": _parse_csv_upper_list(
        os.getenv("HUAWEI_INJECTION_FORBIDDEN_PROMPT_PREFIXES", "VD2")
    ),
    "require_explicit_model_profile": os.getenv(
        "HUAWEI_REQUIRE_EXPLICIT_MODEL_PROFILE",
        "true",
    ).strip().lower() in {"1", "true", "yes", "on"},
}

# Mapeo de modelos ONT a perfiles (line_profile_id, service_profile_id)
_ONT_MODE_PROFILES = _parse_ont_mode_profiles(os.getenv("HUAWEI_ONT_MODE_PROFILES", ""))


def get_huawei_injection_params():
    """
    Retorna diccionario con parámetros de inyección Huawei desde config.

    Tipos:
    - vlan/traffic/profile: str
    - cmd_delay: float
    - max_retries: int
    - forbidden_prompt_prefixes: list[str]
    - require_explicit_model_profile: bool
    """
    return HUAWEI_INJECTION.copy()


def has_explicit_huawei_profile_for_model(ont_model: str) -> bool:
    """
    Indica si un modelo ONT tiene mapeo explícito en HUAWEI_ONT_MODE_PROFILES.
    """
    model = (ont_model or "").strip().upper()
    if not model:
        return False
    return model in _ONT_MODE_PROFILES


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
