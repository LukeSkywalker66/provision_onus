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
            return _provision_zte_onu(conn, olt_name, slot, port, onu_id, pppoe_user, logger)

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
        logger(f"[OK] ONU {onu_id} ({pppoe_user}) en {olt_name}")
        return True

    except Exception as e:
        logger(f"[ERROR] Flujo Huawei para ONU {onu_id} ({pppoe_user}) en {olt_name}: {e}")
        raise


def _provision_zte_onu(conn, olt_name, slot, port, onu_id, pppoe_user, logger):
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
        logger(f"[OK] ONU {onu_id} ({pppoe_user}) en {olt_name}")
        return True

    except Exception as e:
        logger(f"[ERROR] Flujo ZTE para ONU {onu_id} ({pppoe_user}) en {olt_name}: {e}")
        raise

def rollback_onu_serviceport(conn, olt_name, slot, port, onu_id, vlan, pppoe_user, logger):
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
            logger(f"[WARN] No se encontró service-port con VLAN {vlan} para ONU {onu_id} ({pppoe_user})")
            return False

        for sp_id in service_ports:
            cmd = f"undo service-port {sp_id}"
            out = validate_omci_output(conn, cmd, logger)
            logger(f"[OK] Eliminado service-port {sp_id}, VLAN 150 para ONU {onu_id} ({pppoe_user})")
        return True

    except Exception as e:
        logger(f"[ERROR] Rollback ONU {slot}/{port}:{onu_id} ({pppoe_user}) en {olt_name}: {e}")
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
    Consulta la OLT vía OMCI usando "display ont info" y parsea el campo
    "TR069 server profile ID" cuando existe.

    Retorna True si ya está configurada, False si no.
    Compatible con OLTs Huawei. ZTE retorna False (sin soporte).
    """
    try:
        if olt_name != "ZTE C600":
            # Para OLTs Huawei - Consulta a la OLT (requiere estar en interface gpon 0/{slot})
            try:
                # Entrar a interface gpon
                gpon_cmd = f"interface gpon 0/{slot}"
                validate_omci_output(conn, gpon_cmd, logger)
                
                # display ont info tiene paginación (3-4 pantallas)
                cmd = f"display ont info {port} {onu_id}"
                
                # Enviar comando y esperar
                import time as time_module
                conn.write_channel(cmd + '\n')
                time_module.sleep(2)
                
                # Leer primera respuesta (puede ser prompt de confirmación)
                out = conn.read_channel()
                
                # Si es un prompt de confirmación (ej: "{ <cr> }:"), enviar Enter
                if "}:" in out or "{ <cr>" in out or len(out) < 50:
                    conn.write_channel('\n')
                    time_module.sleep(3)
                
                # Leer todo el output real con paginación
                max_iterations = 15
                for i in range(max_iterations):
                    chunk = conn.read_channel()
                    if chunk:
                        out += chunk
                        
                        # Detectar diferentes tipos de paginación
                        has_pagination = (
                            "---- More ----" in chunk or 
                            "  ---- More" in chunk or
                            "Press 'Q' to break" in chunk or
                            "press q to quit" in chunk.lower()
                        )
                        
                        if has_pagination:
                            conn.write_channel(" ")
                            time_module.sleep(2)
                        # Si vemos el prompt, terminamos
                        elif "]" in chunk[-50:]:
                            break
                    else:
                        time_module.sleep(0.5)
                
            finally:
                # Salir de la interfaz GPON para no afectar el flujo principal
                try:
                    validate_omci_output(conn, "quit", logger)
                except Exception:
                    pass

            # Parsear output para buscar el campo TR069 server profile ID
            # Ejemplo esperado:
            # "TR069 server profile ID      : 2"
            import re

            match = re.search(
                r"TR069\s+(?:server\s+)?profile\s+ID\s*[:=]\s*(\d+)",
                out,
                re.IGNORECASE,
            )
            if match:
                profile_id = int(match.group(1))
                logger(f"[SKIP] ONU {onu_id} ya tiene TR-069 con ProfileId {profile_id}")
                return True

            # Si no encontramos el campo, asumimos que no está configurada
            tr069_lines = [line.strip() for line in out.splitlines() if "tr069" in line.lower()]
            if tr069_lines:
                logger(f"[INFO] Lineas TR069 encontradas pero sin ProfileId: {' | '.join(tr069_lines)}")
            logger(f"[INFO] ONU {onu_id} no tiene TR-069 configurado (campo TR069 server profile ID ausente)")
            return False

        # Para ZTE C600 - no soportado por ahora
        logger("[INFO] Validación TR-069 no soportada para ZTE C600, procesando de todas formas")
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
