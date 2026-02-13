import time
from config import ACS, EXEC, OLT_COMMANDS

BUSY_PATTERNS = [
    "It will take several minutes to",
    "The percentage of saved data on",
    "Failure: System is busy",
]


def execute_command(conn, cmd, logger, log_prefix="Enviando comando"):
    """
    Ejecuta un comando y loguea automáticamente la ejecución y resultado.
    Centraliza el patrón repetido: log antes → execute → log salida.
    
    Args:
        conn: Conexión Netmiko
        cmd: Comando a ejecutar
        logger: Función de logging
        log_prefix: Prefijo para el log inicial (default: "Enviando comando")
    
    Returns:
        Output del comando (stripped)
    """
    logger(f"{log_prefix}: {cmd}")
    out = validate_omci_output(conn, cmd, logger)
    logger(out.strip())
    return out


def provision_onu(conn, olt_name, slot, port, onu_id, onu_type, pppoe_user, vlan, logger, eliminar_wan_pppoe=False, crear_wan_ip=False):
    """
    Ejecuta los comandos OMCI/TR-069 necesarios para registrar la ONU en el ACS.
    Soporta OLTs Huawei (Villa Dolores 2, OLT(San_Jose), OLTHUAWEI) y ZTE C600.
    
    Flujo:
    - Huawei: Entra a GPON, ejecuta comandos según flags (crear_wan_ip, eliminar_wan_pppoe), sale
    - ZTE: Flujo específico, sin GPON mode
    """
    logger(f"[{olt_name}] GPON {slot}/{port} ONU {onu_id} → {onu_type} PPPoE:{pppoe_user} - VLAN:{vlan}")
    try:
        if olt_name != "ZTE C600":
            # FLUJO HUAWEI: Entrar a GPON, ejecutar comandos, salir
            return _provision_huawei_onu(
                conn, olt_name, slot, port, onu_id, pppoe_user, vlan, logger,
                crear_wan_ip=crear_wan_ip,
                eliminar_wan_pppoe=eliminar_wan_pppoe
            )
        else:
            # FLUJO ZTE: Comando específico
            return _provision_zte_onu(conn, olt_name, slot, port, onu_id, logger)

    except Exception as e:
        logger(f"[ERROR] ONU {slot}/{port}:{onu_id} en {olt_name}: {e}. {ACS['pppoe_user']} | {ACS['pppoe_password']} | {vlan} | {ACS['prioridad']}")
        try:
            validate_omci_output(conn, "quit", logger)
        except Exception:
            pass
        return False


def _provision_huawei_onu(conn, olt_name, slot, port, onu_id, pppoe_user, vlan, logger, crear_wan_ip=False, eliminar_wan_pppoe=False):
    """
    Provisiona una ONU en OLT Huawei (Villa Dolores 2, OLT(San_Jose), OLTHUAWEI).
    Ejecuta flujo específico según flags crear_wan_ip y eliminar_wan_pppoe.
    """
    try:
        cmd_dict = OLT_COMMANDS.get(olt_name, {})
        
        # Formato para los comandos (substitución de placeholders)
        fmt_args = {
            "slot": slot,
            "port": port,
            "onu_id": onu_id,
            "pppoe_user": ACS['pppoe_user'],
            "pppoe_password": ACS['pppoe_password'],
            "vlan": vlan,
            "prioridad": ACS['prioridad']
        }

        if crear_wan_ip:
            # RUTA A: Crear WAN IP (DHCP en VLAN 150)
            cmds = cmd_dict.get("crear_wan_ip", {})
            
            # Crear service-port en VLAN 150
            execute_command(conn, cmds["service_port"].format(**fmt_args), logger)
            
            # Entrar a GPON
            execute_command(conn, cmds["interface_gpon"].format(**fmt_args), logger)
            
            # Configurar IP DHCP
            execute_command(conn, cmds["ipconfig"].format(**fmt_args), logger)
            
            # Configurar TR-069
            execute_command(conn, cmds["tr069"].format(**fmt_args), logger)
        else:
            # RUTA B: Crear WAN PPPoE (o limpiar)
            # Entrar a GPON es obligatorio
            cmds_pppoe = cmd_dict.get("crear_wan_pppoe", {})
            execute_command(conn, cmds_pppoe["interface_gpon"].format(**fmt_args), logger)

            if eliminar_wan_pppoe:
                # SUBRUTA B1: Eliminar WAN PPPoE anterior
                cmds_delete = cmd_dict.get("eliminar_wan_pppoe", {})
                
                # Villa Dolores 2 tiene un paso extra: desasignar wan-config
                if olt_name == "Villa Dolores 2" and "undo_wan_config" in cmds_delete:
                    execute_command(conn, cmds_delete["undo_wan_config"].format(**fmt_args), logger)
                
                # Todos eliminan ipconfig
                execute_command(conn, cmds_delete["undo_ipconfig"].format(**fmt_args), logger)
            else:
                # SUBRUTA B2: Crear WAN PPPoE nueva
                # Configurar PPPoE
                execute_command(conn, cmds_pppoe["ipconfig"].format(**fmt_args), logger)
                
                # Villa Dolores 2 requiere asignar wan-config
                if olt_name == "Villa Dolores 2" and "wan_config" in cmds_pppoe:
                    execute_command(conn, cmds_pppoe["wan_config"].format(**fmt_args), logger)
                
                # Configurar TR-069 (todos)
                execute_command(conn, cmds_pppoe["tr069"].format(**fmt_args), logger)

        # Salir de GPON (común a todos los flujos Huawei)
        validate_omci_output(conn, "quit", logger)
        logger("[.] Salió de la interfaz GPON - OK")
        time.sleep(EXEC["delay_between_onus"])
        logger(f"[OK] ONU {onu_id} en {olt_name}")
        return True

    except Exception as e:
        logger(f"[ERROR] Flujo Huawei para ONU {onu_id} en {olt_name}: {e}")
        raise


def _provision_zte_onu(conn, olt_name, slot, port, onu_id, logger):
    """
    Provisiona una ONU en OLT ZTE C600.
    Flujo completamente diferente: comando único sin GPON mode.
    """
    try:
        cmd = f"pon-onu-mng gpon_onu-1/{slot}/{port}:{onu_id}"
        logger(f"Enviando comando: {cmd}")
        out = validate_omci_output(conn, cmd, logger)
        logger(out.strip())

        validate_omci_output(conn, "quit", logger)
        logger("[.] Salió de la interfaz GPON - OK")
        time.sleep(EXEC["delay_between_onus"])
        logger(f"[OK] ONU {onu_id} en {olt_name}")
        return True

    except Exception as e:
        logger(f"[ERROR] Flujo ZTE para ONU {onu_id} en {olt_name}: {e}")
        raise

def rollback_onu_serviceport(conn, olt_name, slot, port, onu_id, vlan, logger):
    """
    Busca y elimina los service-port asociados a una ONU en la VLAN indicada.
    """
    try:
        cmd = f"display service-port port 0/{slot}/{port} ont {onu_id}"
        out = validate_omci_output(conn, cmd, logger)
        logger(out)

        # Parsear service-ports desde línea fija
        service_ports = []
        lines = out.splitlines()

        # Asumimos que los datos empiezan en la línea 8 (índice 7)
        for line in lines[8:]:
            line = line.strip()
            if not line or line.startswith("----") or line.startswith("Total"):
                break  # Fin del bloque útil

            parts = line.split()
            if len(parts) >= 2 and parts[1] == "150":  # Validación fija por VLAN
                service_ports.append(parts[0])  # ID del service-port

        if not service_ports:
            logger(f"[WARN] No se encontró service-port con VLAN {vlan} para ONU {onu_id}")
            return False

        for sp_id in service_ports:
            cmd = f"undo service-port {sp_id}"
            out = validate_omci_output(conn, cmd, logger)
            logger(f"[OK] Eliminado service-port {sp_id}, VLAN 150 para ONU {onu_id}")
        return True

    except Exception as e:
        logger(f"[ERROR] Rollback ONU {slot}/{port}:{onu_id} en {olt_name}: {e}")
        return False



def validate_omci_output(conn, cmd, logger, max_retries=10):
    """
    Ejecuta un comando OMCI, maneja:
    - OLT ocupada (reintenta con delay)
    - Prompt de confirmación de filtros (envía Enter extra)
    """
    for attempt in range(max_retries):
        try:
            out = conn.send_command_timing(cmd)
            output = out.strip()

            # Caso 1: OLT ocupada
            if any(output.startswith(p) for p in BUSY_PATTERNS):
                logger(f"[WARN] OLT ocupada al ejecutar '{cmd}', reintentando en {EXEC['delay_between_onus_largo']}s (intento {attempt+1}/{max_retries})")
                time.sleep(EXEC["delay_between_onus_largo"])
                continue

            # Caso 2: prompt de confirmación de filtros
            if output.endswith("}:"):
                logger(f"[INFO] El comando '{cmd}' espera confirmación <cr>, enviando Enter extra...")
                extra = conn.send_command_timing("\n")
                output += "\n" + extra.strip()

            return output

        except Exception as e:
            logger(f"[ERROR] Fallo al ejecutar '{cmd}': {e}")
            time.sleep(5)
            continue

    raise RuntimeError(f"Comando '{cmd}' no pudo ejecutarse tras {max_retries} intentos")


def check_onu_tr069_profile(conn, olt_name, slot, port, onu_id, logger):
    """
    Verifica si una ONU ya tiene un profile TR-069 asignado.
    Consulta la OLT vía OMCI: display ont tr069-server-config PORT ONU_ID
    Parsea el output para extraer el ProfileId y validar si es válido.
    
    Retorna True si ya está configurada, False si no.
    Compatible con OLTs Huawei. ZTE retorna False (sin soporte).
    """
    try:
        if olt_name != "ZTE C600":
            # Para OLTs Huawei - Consulta a la OLT
            cmd = f"display ont tr069-server-config {port} {onu_id}"
            out = validate_omci_output(conn, cmd, logger)
            
            # Parsear output para buscar un ProfileId asignado
            # Formato esperado en Huawei: línea con "ProfileId" o "profile" seguido de ":", ": ", "=", etc.
            # Ejemplo: "ProfileId : 2" o "Profile ID: 1" o similar
            
            # Buscar patrón: "profile" (case-insensitive) seguido de "id" y luego ":" o "="
            # y capturar el número después
            import re
            
            # Patrones posibles en output Huawei
            patterns = [
                r'ProfileId\s*[:=]\s*(\d+)',      # ProfileId : 1 o ProfileId=1
                r'Profile\s+ID\s*[:=]\s*(\d+)',   # Profile ID : 1
                r'profile-id\s+(\d+)',             # profile-id 1
                r'profile\s+id\s*[:=]\s*(\d+)',   # profile id : 1 (case-insensitive)
            ]
            
            for pattern in patterns:
                match = re.search(pattern, out, re.IGNORECASE)
                if match:
                    profile_id = int(match.group(1))
                    # Validar que sea un ProfileId válido (1 o 2 para Huawei)
                    if profile_id in [1, 2]:
                        logger(f"[SKIP] ONU {onu_id} ya tiene TR-069 con ProfileId {profile_id}")
                        return True
                    else:
                        logger(f"[WARN] ONU {onu_id} tiene TR-069 con ProfileId inusual: {profile_id}")
                        return True  # Igualmente consideramos que está configurada
            
            # Si no encontramos ProfileId, asumimos que no está configurada
            logger(f"[INFO] ONU {onu_id} no tiene TR-069 configurado (sin ProfileId encontrado)")
            return False
            
        else:
            # Para ZTE C600 - no soportado por ahora
            logger(f"[INFO] Validación TR-069 no soportada para ZTE C600, procesando de todas formas")
            return False
            
    except Exception as e:
        # Si el comando falla, logueamos pero asumimos no configurado
        # (una ONU sin TR-069 puede causar error en display)
        logger(f"[INFO] No se pudo consultar TR-069 de ONU {onu_id}: {e} (asumiendo no configurado)")
        return False


# def validate_omci_output(conn, cmd, logger):
#     """
#     Ejecuta un comando OMCI, valida si la OLT está ocupada (backup),
#     espera y reintenta si es necesario.
#     """
#     while True:
#         out = conn.send_command_timing(cmd)
#         output = out.strip()
#         if (
#             output.startswith("It will take several minutes to")
#             or output.startswith("The percentage of saved data on")
#             or output.startswith("Failure: System is busy")
#         ):
#             logger("El sistema se encuentra ocupado, reintentando en 3 minutos")
#             time.sleep(EXEC["delay_between_onus_largo"])
#             continue  # Reintenta el comando
#         return output
