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

# Comandos OMCI específicos por OLT
# Contiene información de profile-id y traffic-table por fabricante
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
    "OLTHUAWEI": {
        "traffic-table index": 7,
        "profile-id": 1,
        "wan-config enabled": False,
    },
    "ZTE C600": {
        "traffic-table index": None,
        "profile-id": None,
        "wan-config enabled": False,
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
