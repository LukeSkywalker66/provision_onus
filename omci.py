import time
import re
from config import ACS, EXEC, OLT_COMMANDS

BUSY_PATTERNS = [
    "It will take several minutes to",
    "The percentage of saved data on",
    "Failure: System is busy",
]


def get_onus_with_tr069_bulk(conn, olt_name, logger):
    """
    Consulta masiva a la OLT para obtener todas las ONUs que YA tienen TR-069 configurado.
    
    Ejecuta 'display service-port all' y parsea el resultado para identificar
    ONUs con service-ports en VLAN TR-069 (típicamente VLAN 150).
    
    Retorna:
        set de tuplas (slot, port, onu_id) para ONUs que YA tienen TR-069
        ejemplo: {(0, 0, 5), (0, 1, 12), ...}
    
    Compatible: Huawei OLTs
    """
    try:
        if olt_name == "ZTE C600":
            logger("[INFO] Prefiltrado masivo no soportado para ZTE C600")
            return set()
        
        logger(f"[INFO] Consultando ONUs con TR-069 en {olt_name}...")
        
        # Enviar comando masivo
        out = validate_omci_output(conn, "display service-port all", logger)
        
        # Parsear service-ports para encontrar ONUs con TR-069
        # Formato típico de línea:
        # SP-ID  VlanId    PortType  P/S/P             OntId  GemPort  UsMEID  DsMEID
        # 1      150       ETH       0/0/0             0      2        -       -
        # 2      150       ETH       0/0/1             5      3        -       -
        
        onus_tr069 = set()
        
        # Buscar líneas que contengan VLAN 150 (típico para TR-069)
        for line in out.splitlines():
            # Saltar líneas vacías, encabezados y separadores
            if not line.strip() or "SP-ID" in line or "---" in line or "More" in line:
                continue
            
            # Parsear línea: buscar patrón con VLAN 150 y puerto GPON
            # Ejemplo: "1      150       ETH       0/0/0             0      2        -       -"
            match = re.search(
                r'^\s*\d+\s+150\s+\w+\s+(\d+)/(\d+)/(\d+)\s+(\d+)',  # VLAN150 + P/S/P + OntId
                line
            )
            if match:
                slot = int(match.group(1))
                subport = int(match.group(2))
                phyport = int(match.group(3))
                onu_id = int(match.group(4))
                
                # Agregar tupla identificadora
                onus_tr069.add((slot, subport, onu_id))
                logger(f"  → ONU {onu_id} en puerto {slot}/{subport}/{phyport} con VLAN150 (TR-069)")
        
        logger(f"[INFO] Total ONUs con TR-069 detectadas: {len(onus_tr069)}")
        return onus_tr069
    
    except Exception as e:
        logger(f"[WARN] Error en prefiltrado masivo: {e} (continuando con validación individual)")
        return set()


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

                # Desactivar paginacion para capturar todo el output de una vez
                validate_omci_output(conn, "screen-length 0 temporary", logger)

                # Usar send_command_timing() en lugar de send_command() para evitar problemas
                # con detección de prompt. Este método espera un tiempo fijo en vez de buscar el prompt.
                cmd = f"display ont info {port} {onu_id}"
                logger(f"Enviando comando: {cmd}")
                
                # send_command_timing() espera un tiempo fijo (default ~1s, ajustable con delay_factor)
                # y retorna todo lo que recibió. Más predecible que esperar el prompt.
                out = conn.send_command_timing(cmd, delay_factor=2)
                
                # MANEJO DE PAGINACIÓN: Si el output contiene "More" o "Press", 
                # significa que hay más páginas. Enviar espacios hasta capturar todo.
                max_iterations = 20  # Límite de seguridad
                iteration = 0
                while any(indicator in out for indicator in ["---- More", "Press 'Q'", "Press to continue"]):
                    iteration += 1
                    if iteration > max_iterations:
                        break
                    
                    conn.write_channel(" ")  # Enviar espacio para continuar
                    time.sleep(0.5)  # Breve pausa para que el OLT envíe más datos
                    more_output = conn.read_channel()  # Leer la siguiente página
                    out += more_output  # Concatenar al output total
                
            finally:
                # Salir de la interfaz GPON para no afectar el flujo principal
                try:
                    validate_omci_output(conn, "quit", logger)
                except Exception:
                    pass

            # Parsear output para buscar el campo TR069 server profile ID
            # Compatible con múltiples formatos según fabricante/versión:
            # - Huawei (Villa Dolores 2): "TR069 server profile ID      : 2"
            # - Huawei (OLTHUAWEI): "tr069-server-profile_1        : 1" o "tr069-server-profile_2        : 2"
            import re

            # Intentar primera regex: "TR069 server profile ID" (formato estándar)
            match = re.search(
                r"TR069\s+(?:server\s+)?profile\s+ID\s*[:=]\s*(\d+)",
                out,
                re.IGNORECASE,
            )
            
            # Si no encuentra, intentar con guiones: "tr069-server-profile_1" o "tr069-server-profile_2"
            if not match:
                match = re.search(
                    r"tr069-server-profile_[12]\s*[:=]\s*(\d+)",
                    out,
                    re.IGNORECASE,
                )
            
            # Si aún no encuentra, buscar cualquier combinación flexible de TR069 + profile + número
            if not match:
                match = re.search(
                    r"tr069[^:]*(?:profile|profile_id|profileid)[^:]*[:=]\s*(\d+)",
                    out,
                    re.IGNORECASE,
                )
            
            if match:
                profile_id = int(match.group(1))
                logger(f"[SKIP] ONU {onu_id} ya tiene TR-069 configurado (ProfileId {profile_id})")
                return True

            # Si no encontramos el campo, asumimos que no está configurada
            logger(f"[INFO] ONU {onu_id} sin TR-069 configurado, se procesará")
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
