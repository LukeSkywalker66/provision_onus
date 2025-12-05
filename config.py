# Mapea el nombre de OLT del CSV de SmartOLT a IP y credenciales reales
OLT_MAP = {
    "Villa Dolores 2": {
        "ip": "10.11.104.5",
        "user": "smartoltusr",
        "password": "6058gef6",
        "fabricante": "huawei",
        "port": 22,  # Nat en el mikrotik
    },
    "OLT(San_Jose)": {
        "ip": "138.59.175.11",
        "user": "smartoltusr",
        "password": "6058gef6",
        "fabricante": "huawei",
        "port": 1230,  # Nat en el mikrotik
    },
    "OLTHUAWEI": {
        "ip": "138.59.175.17",
        "user": "smartolt",
        "password": "6058gef6",
        "fabricante": "huawei",
        "port": 2322,  # Nat en el mikrotik
    },
    "ZTE C600": {
        "ip": "138.59.175.11",
        "user": "usmartolt",
        "password": "785423Gbn%",
        "fabricante": "zte",
        "port": 1230,  # Nat en el mikrotik
    },
    # Agrega más OLTs aquí
}

# Parámetros TR-069/ACS comunes
ACS = {
    "ip": "http://138.59.172.24",
    "port": 7547,
    "pppoe_user": "tr069",
    "pppoe_password": "123",
    "user": "miCpeUser",
    "password": "Passw0rdACS!23#",
    "prioridad": 0,  # Prioridad de VLAN (0-7)
}

# Ajustes de ejecución
EXEC = {
    "batch_size": 50,   # tamaño de lote
    "delay_between_onus": 0.2,  # segundos
    "delay_between_onus_largo": 200,  # segundos
}
