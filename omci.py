import time
from config import ACS, EXEC

BUSY_PATTERNS = [
    "It will take several minutes to",
    "The percentage of saved data on",
    "Failure: System is busy",
]


def provision_onu(conn, olt_name, slot, port, onu_id, onu_type, pppoe_user, vlan, logger, eliminar_wan_pppoe=False, crear_wan_ip=False):

    #Ejecuta los comandos OMCI/TR-069 necesarios para registrar la ONU en el ACS.
    #Ajusta estos comandos según tu CLI validada en VD2.
   
    logger(f"[{olt_name}] GPON {slot}/{port} ONU {onu_id} → {onu_type} PPPoE:{pppoe_user} - VLAN:{vlan}")
    try:
        if olt_name != "ZTE C600":
            
            if crear_wan_ip == True:
                match olt_name:
                    case "Villa Dolores 2":
                        # creando service port para vlan 150 de management
                        logger(f"Enviando comando: service-port vlan 150 gpon 0/{slot}/{port} ont {onu_id} gemport 2 multi-service user-vlan 150 tag-transform translate inbound traffic-table name SMARTOLT-VOIPMNG-10M outbound traffic-table name SMARTOLT-VOIPMNG-10M")
                        out = validate_omci_output(conn,f"service-port vlan 150 gpon 0/{slot}/{port} ont {onu_id} gemport 2 multi-service user-vlan 150 tag-transform translate inbound traffic-table name SMARTOLT-VOIPMNG-10M outbound traffic-table name SMARTOLT-VOIPMNG-10M", logger)
                        logger(out.strip())

                        #la placa de servicio en este caso es 0 dado solo hay una placa de servicio activa
                        #en caso de tener mas placas de servicio, hay que iterar por cada placa de servicio
                        logger(f"Enviando comando: interface gpon 0/{slot}")
                        out = validate_omci_output(conn,f"interface gpon 0/{slot}", logger)
                        logger(out.strip())
                        # creacion de la wan ip en la onu 
                        logger(f"Enviando comando: ont ipconfig {port} {onu_id} ip-index 0 dhcp vlan 150 priority 2")
                        out = validate_omci_output(conn,f"ont ipconfig {port} {onu_id} ip-index 0 dhcp vlan 150 priority 2", logger)
                        logger(out.strip())
                        # Configuración TR-069 donde el profile-id es 2
                        logger(f"Enviando comando: ont tr069-server-config {port} {onu_id} profile-id 2")
                        out = validate_omci_output(conn,f"ont tr069-server-config {port} {onu_id} profile-id 2", logger)
                        logger(out.strip())


                    case "OLT(San_Jose)":
                        # creando service port para vlan 150 de management
                        # EJ:
                        # service-port 18 vlan 150 gpon 0/0/5 ont 62 gemport 2 multi-service user-vlan 150 tag-transform translate inbound traffic-table index 7 outbound traffic-table index 7
                        logger(f"Enviando comando: service-port vlan 150 gpon 0/{slot}/{port} ont {onu_id} gemport 2 multi-service user-vlan 150 tag-transform translate inbound traffic-table index 7 outbound traffic-table index 7")
                        out = validate_omci_output(conn,f"service-port vlan 150 gpon 0/{slot}/{port} ont {onu_id} gemport 2 multi-service user-vlan 150 tag-transform translate inbound traffic-table index 7 outbound traffic-table index 7", logger)
                        logger(out.strip())

                        #la placa de servicio en este caso es 0 dado solo hay una placa de servicio activa
                        #en caso de tener mas placas de servicio, hay que iterar por cada placa de servicio
                        logger(f"Enviando comando: interface gpon 0/{slot}")
                        out = validate_omci_output(conn,f"interface gpon 0/{slot}", logger)
                        logger(out.strip())
                        # creacion de la wan ip en la onu 
                        logger(f"Enviando comando: ont ipconfig {port} {onu_id} ip-index 0 dhcp vlan 150 priority 2")
                        out = validate_omci_output(conn,f"ont ipconfig {port} {onu_id} ip-index 0 dhcp vlan 150 priority 2", logger)
                        logger(out.strip())
                        # Configuración TR-069 donde el profile-id es 2
                        logger(f"Enviando comando: ont tr069-server-config {port} {onu_id} profile-id 2")
                        out = validate_omci_output(conn,f"ont tr069-server-config {port} {onu_id} profile-id 1", logger)
                        logger(out.strip())
                    case "OLTHUAWEI":
                        # creando service port para vlan 150 de management
                        #EJ:
                        # service-port 949 vlan 150 gpon 0/1/7 ont 52 gemport 2 multi-service user-vlan  150 tag-transform translate inbound traffic-table index 7 outbound traffic-table index 7
                        logger(f"Enviando comando: service-port vlan 150 gpon 0/{slot}/{port} ont {onu_id} gemport 2 multi-service user-vlan 150 tag-transform translate inbound traffic-table index 7 outbound traffic-table index 7")
                        out = validate_omci_output(conn,f"service-port vlan 150 gpon 0/{slot}/{port} ont {onu_id} gemport 2 multi-service user-vlan 150 tag-transform translate inbound traffic-table index 7 outbound traffic-table index 7", logger)
                        logger(out.strip())

                        #la placa de servicio en este caso es 0 dado solo hay una placa de servicio activa
                        #en caso de tener mas placas de servicio, hay que iterar por cada placa de servicio
                        logger(f"Enviando comando: interface gpon 0/{slot}")
                        out = validate_omci_output(conn,f"interface gpon 0/{slot}", logger)
                        logger(out.strip())
                        # creacion de la wan ip en la onu 
                        logger(f"Enviando comando: ont ipconfig {port} {onu_id} ip-index 0 dhcp vlan 150 priority 2")
                        out = validate_omci_output(conn,f"ont ipconfig {port} {onu_id} ip-index 0 dhcp vlan 150 priority 2", logger)
                        logger(out.strip())
                        # Configuración TR-069 donde el profile-id es 2
                        logger(f"Enviando comando: ont tr069-server-config {port} {onu_id} profile-id 1")
                        out = validate_omci_output(conn,f"ont tr069-server-config {port} {onu_id} profile-id 1", logger)
                        logger(out.strip())
            else:
            
                #la placa de servicio en este caso es 0 dado solo hay una placa de servicio activa
                #en caso de tener mas placas de servicio, hay que iterar por cada placa de servicio
                logger(f"Enviando comando: interface gpon 0/{slot}")
                out = validate_omci_output(conn,f"interface gpon 0/{slot}", logger)
                logger(out.strip())

                if eliminar_wan_pppoe == True:
                    match olt_name:
                        case "Villa Dolores 2":
                            #desasignar perfil wan
                            logger(f"Enviando comando: undo ont wan-config {port} {onu_id} ip-index 0")
                            out = validate_omci_output(conn,f"undo ont wan-config {port} {onu_id} ip-index 0", logger)
                            logger(out.strip())
                            # eliminar wan pppoe previa
                            logger(f"Enviando comando: undo ont ipconfig {port} {onu_id} ip-index 0")
                            out = validate_omci_output(conn,f"undo ont ipconfig {port} {onu_id} ip-index 0", logger)
                            logger(out.strip())
                        case "OLT(San_Jose)":
                            # eliminar wan pppoe previa
                            logger(f"Enviando comando: undo ont ipconfig {port} {onu_id} ip-index 0")
                            out = validate_omci_output(conn,f"undo ont ipconfig {port} {onu_id} ip-index 0", logger)
                            logger(out.strip())
                        case "OLTHUAWEI":
                            # eliminar wan pppoe previa
                            logger(f"Enviando comando: undo ont ipconfig {port} {onu_id} ip-index 0")
                            out = validate_omci_output(conn,f"undo ont ipconfig {port} {onu_id} ip-index 0", logger)
                            logger(out.strip())
                else:
                    
                    # match olt_name:
                    #     case "Villa Dolores 2":
                    #         # eliminar wan pppoe previa
                    #         logger(f"Enviando comando: undo ont ipconfig {port} {onu_id} ip-index 0")
                    #         out = validate_omci_output(conn,f"undo ont ipconfig {port} {onu_id} ip-index 0", logger)
                    #         logger(out.strip())
                    #     case "OLT(San_Jose)":
                    #         # eliminar wan pppoe previa
                    #         logger(f"Enviando comando: undo ont ipconfig {port} {onu_id} ip-index 0")
                    #         out = validate_omci_output(conn,f"undo ont ipconfig {port} {onu_id} ip-index 0", logger)
                    #         logger(out.strip())
                    #     case "OLTHUAWEI":
                    #         # eliminar wan pppoe previa
                    #         logger(f"Enviando comando: undo ont ipconfig {port} {onu_id} ip-index 0")
                    #         out = validate_omci_output(conn,f"undo ont ipconfig {port} {onu_id} ip-index 0", logger)
                    #         logger(out.strip())

                    # limpiar wan tr069 previa
                    # logger(f"Enviando comando: undo ont ipconfig {port} {onu_id} ip-index 0")
                    # out = validate_omci_output(conn,f"undo ont ipconfig {port} {onu_id} ip-index 0", logger)
                    # logger(out.strip())
                    # creacion de la wan en la onu 
                    logger(f"Enviando comando: ont ipconfig {port} {onu_id} pppoe user-account username {ACS['pppoe_user']} password {ACS['pppoe_password']} vlan {vlan} priority {ACS['prioridad']}")
                    out = validate_omci_output(conn,f"ont ipconfig {port} {onu_id} pppoe user-account username {ACS['pppoe_user']} password {ACS['pppoe_password']} vlan {vlan} priority {ACS['prioridad']}", logger)
                    logger(out.strip())
                
                    #sólo si la olt es Villa Dolores 2
                    match olt_name:
                        case "Villa Dolores 2":
                            #Asignar perfil wan
                            logger(f"Enviando comando: ont wan-config {port} {onu_id} ip-index 0 profile-id 1")
                            out = validate_omci_output(conn,f"ont wan-config {port} {onu_id} ip-index 0 profile-id 1", logger)
                            logger(out.strip())

                            # Configuración TR-069 donde el profile-id es 2
                            logger(f"Enviando comando: ont tr069-server-config {port} {onu_id} profile-id 2")
                            out = validate_omci_output(conn,f"ont tr069-server-config {port} {onu_id} profile-id 2", logger)
                            logger(out.strip())

                        case "OLT(San_Jose)":
                            # Configuración TR-069 donde el profile-id es 1
                            logger(f"Enviando comando: ont tr069-server-config {port} {onu_id} profile-id 1")
                            out = validate_omci_output(conn,f"ont tr069-server-config {port} {onu_id} profile-id 1", logger)
                            logger(out.strip())

                        case "OLTHUAWEI":
                            # Configuración TR-069 donde el profile-id es ??
                            logger(f"Enviando comando: ont tr069-server-config {port} {onu_id} profile-id 1")
                            out = validate_omci_output(conn,f"ont tr069-server-config {port} {onu_id} profile-id 1", logger)
                            logger(out.strip())

                    #enviar reboot a la onu para forzar el inform el ac server
                    #logger(f"Enviando comando: ont reset {port} {onu_id}")
                    #out = validate_omci_output(conn,f"ont reset {port} {onu_id}", logger)
                    #logger(out.strip())
                    
                    #confirma con Y
                    #logger(f"Enviando comando: y")
                    #out = validate_omci_output(conn,f"y", logger)
                    #logger(out.strip())
                    #logger(f"Ont  {port} {onu_id} reiniciada")
            #salir de la interfaz gpon
            validate_omci_output(conn,"quit", logger)
            logger("[.] Salió de la interfaz GPON - OK")
            time.sleep(EXEC["delay_between_onus"])
            logger(f"[OK] ONU {onu_id} en {olt_name}")
            return True
        else:
            # Para ZTE C600, usa comandos específicos
            #Ejecutar pon-onu-mng gpon_onu-1/1/1:1
            logger(f"pon-onu-mng gpon_onu-1/{slot}/{port}:{onu_id}")
            out = validate_omci_output(conn,f"pon-onu-mng gpon_onu-1/{slot}/{port}:{onu_id}", logger)
            logger(out.strip())


            validate_omci_output(conn,"quit", logger)
            logger("[.] Salió de la interfaz GPON - OK")
            time.sleep(EXEC["delay_between_onus"])
            logger(f"[OK] ONU {onu_id} en {olt_name}")
            return True
        
    except Exception as e:
        logger(f"[ERROR] ONU {slot}/{port}:{onu_id} en {olt_name}: {e}. {ACS['pppoe_user']} | {ACS['pppoe_password']} | {vlan} | {ACS['prioridad']}")
        try:
            validate_omci_output(conn,"quit", logger)
        except Exception:
            pass
        return False

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
