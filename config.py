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
}
