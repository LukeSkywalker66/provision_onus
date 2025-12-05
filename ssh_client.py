from netmiko import ConnectHandler

def connect_olt(ip, user, password, port):
    """Devuelve una sesión Netmiko ya elevada si es necesario."""
    dev = {
        "device_type": "huawei",
        "host": ip,
        "username": user,
        "password": password,
        "global_cmd_verify": False,   # <--- evita la espera del patrón
        "fast_cli": False,
        "session_log": "session.txt",  # opcional
        "port": port
    }
    conn = ConnectHandler(**dev)
    
    return conn

def close_olt(conn):
    try:
        conn.disconnect()
    except Exception:
        pass
