import csv
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Tuple

from netmiko import ConnectHandler
import config
from omci import validate_omci_output


# Cargar configuracion de Perfiles Huawei desde config.py (que lee desde .env)
_huawei_config = config.get_huawei_injection_params()
VLAN_ID = _huawei_config["vlan_id"]
TRAFFIC_TABLE_UP = _huawei_config["traffic_table_up"]
TRAFFIC_TABLE_DOWN = _huawei_config["traffic_table_down"]
HUAWEI_INJECTION_CMD_DELAY = float(_huawei_config.get("cmd_delay", 0.4))
HUAWEI_INJECTION_MAX_RETRIES = int(_huawei_config.get("max_retries", 10))
HUAWEI_INJECTION_FORBIDDEN_PROMPT_PREFIXES = [
    p.strip().upper()
    for p in _huawei_config.get("forbidden_prompt_prefixes", [])
    if str(p).strip()
]
HUAWEI_REQUIRE_EXPLICIT_MODEL_PROFILE = bool(
    _huawei_config.get("require_explicit_model_profile", True)
)


# Nota: Los perfiles de línea y servicio ahora se obtienen dinámicamente por modelo ONT
# usando config.get_huawei_profiles_for_ont_model()


REQUIRED_COLUMNS_BASE = ["PON_DESTINO", "SN", "PPPoE_USER", "ONT_MODEL"]
HUAWEI_ID_CANDIDATES = ["ID", "HUAWEI_ONU_ID", "ZTE_ONU_ID"]


def _pick_huawei_onu_id(row: Dict[str, str]) -> str:
    for key in HUAWEI_ID_CANDIDATES:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


def load_migration_csv(file_path: str) -> List[Dict[str, str]]:
    with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV sin cabeceras")

        # Normaliza cabeceras para tolerar BOM y espacios accidentales.
        reader.fieldnames = [
            ((name or "").replace("\ufeff", "").strip())
            for name in reader.fieldnames
        ]

        missing = [c for c in REQUIRED_COLUMNS_BASE if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV invalido: faltan columnas {missing}")

        if not any(col in reader.fieldnames for col in HUAWEI_ID_CANDIDATES):
            raise ValueError(
                "CSV invalido: falta columna de ID ONU (aceptadas: ID, HUAWEI_ONU_ID, ZTE_ONU_ID)"
            )

        rows: List[Dict[str, str]] = []
        for row in reader:
            huawei_onu_id = _pick_huawei_onu_id(row)
            cleaned = {
                "PON_DESTINO": (row.get("PON_DESTINO") or "").strip(),
                "HUAWEI_ONU_ID": huawei_onu_id,
                "SN": (row.get("SN") or "").replace(":", "").strip(),
                "PPPoE_USER": (row.get("PPPoE_USER") or "").strip(),
                "ONT_MODEL": (row.get("ONT_MODEL") or "").strip().upper(),
                "ONT_MODE": (row.get("ONT_MODE") or "ROUTER").strip().upper(),
            }
            if cleaned["ONT_MODE"] not in {"ROUTER", "BRIDGE"}:
                cleaned["ONT_MODE"] = "ROUTER"
            if not cleaned["PON_DESTINO"] or not cleaned["HUAWEI_ONU_ID"] or not cleaned["SN"]:
                continue
            rows.append(cleaned)

        return rows


def parse_frame_slot_port(pon_destino: str) -> Tuple[str, str]:
    """
    Convierte formatos como:
    - gpon_olt-1/4/10
    - 1/4/10
    En:
    - FRAME_SLOT: 1/4
    - PORT: 10
    """
    value = (pon_destino or "").strip()
    value = value.replace("gpon_olt-", "", 1)

    match = re.search(r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)$", value)
    if not match:
        raise ValueError(f"No se pudo parsear PON_DESTINO '{pon_destino}' (esperado: X/Y/Z)")

    frame_slot = f"{match.group(1)}/{match.group(2)}"
    port = match.group(3)
    return frame_slot, port


def build_row_commands(row: Dict[str, str]) -> List[str]:
    """
    Genera comandos Huawei VRP para provisionar una ONT.
    
    Los perfiles de línea y servicio se obtienen dinámicamente según el modelo ONT.
    Se mapean desde config.py basado en HUAWEI_ONT_MODE_PROFILES en .env.
    Si el modelo no está mapeado, se usan los perfiles default (genéricos).
    """
    frame_slot, port = parse_frame_slot_port(row["PON_DESTINO"])
    onu_id = row["HUAWEI_ONU_ID"]
    sn = row["SN"].replace(":", "")
    pppoe_user = row["PPPoE_USER"]
    ont_model = row.get("ONT_MODEL", "")
    
    # El perfil siempre se determina por modelo ONT, independiente de ONT_MODE.
    line_prof, srv_prof = config.get_huawei_profiles_for_ont_model(ont_model)

    ont_mode = (row.get("ONT_MODE") or "ROUTER").strip().upper()
    native_vlan_cmds = []
    if ont_mode == "BRIDGE":
        native_vlan_cmds = [
            f"ont port native-vlan {port} {onu_id} eth {eth} vlan {VLAN_ID} priority 0"
            for eth in range(1, 5)
        ]
    
    return [
        f"interface gpon {frame_slot}",
        (
            f"ont add {port} {onu_id} sn-auth {sn} omci "
            f"ont-lineprofile-id {line_prof} ont-srvprofile-id {srv_prof} "
            f"desc \"{pppoe_user}\""
        ),
        *native_vlan_cmds,
        "quit",
        (
            f"service-port vlan {VLAN_ID} gpon {frame_slot}/{port} ont {onu_id} gemport 1 "
            f"multi-service user-vlan {VLAN_ID} tag-transform translate "
            f"inbound traffic-table index {TRAFFIC_TABLE_UP} "
            f"outbound traffic-table index {TRAFFIC_TABLE_DOWN}"
        ),
    ]


def _has_error(output: str) -> bool:
    text = (output or "").lower()
    return any(token in text for token in ["failure", "error", "already exists", "invalid", "incomplete"])


def _execute_huawei_cmd(conn, cmd: str, logger) -> str:
    """
    Ejecuta comandos de forma segura reutilizando la lógica OMCI del proyecto.

    - Reintenta automáticamente ante OLT ocupada.
    - Maneja prompts de confirmación.
    - Valida errores funcionales en respuesta.
    - Agrega una breve espera entre pasos dependientes.
    """
    logger(f"[INFO] [CMD] {cmd}")
    out = validate_omci_output(
        conn,
        cmd,
        logger,
        max_retries=max(1, HUAWEI_INJECTION_MAX_RETRIES),
    )
    if _has_error(out):
        raise RuntimeError(out.strip() or "Respuesta con error del equipo")
    time.sleep(HUAWEI_INJECTION_CMD_DELAY)
    return out


def _execute_huawei_cmd_permissive(conn, cmd: str, logger) -> str:
    """
    Ejecuta comando en modo tolerante a errores (para limpieza/reparacion).

    No lanza excepción por respuestas de error funcional del equipo.
    """
    logger(f"[INFO] [CMD][REPAIR] {cmd}")
    try:
        out = validate_omci_output(
            conn,
            cmd,
            logger,
            max_retries=max(1, HUAWEI_INJECTION_MAX_RETRIES),
        )
    except Exception as exc:
        logger(f"[WARN] [REPAIR] Fallo al ejecutar '{cmd}': {exc}")
        return ""

    if _has_error(out):
        logger(f"[WARN] [REPAIR] Respuesta con error (se continua): {out.strip()}")
    time.sleep(HUAWEI_INJECTION_CMD_DELAY)
    return out


def _extract_service_port_ids(output: str) -> List[str]:
    """
    Extrae IDs de service-port desde salida de 'display service-port ...'.

    Se toma el primer campo numérico de líneas tabulares.
    """
    service_ports: List[str] = []
    for line in (output or "").splitlines():
        m = re.match(r"^\s*(\d+)\s+", line)
        if not m:
            continue
        sp_id = m.group(1)
        if sp_id not in service_ports:
            service_ports.append(sp_id)
    return service_ports


def _repair_cleanup_row(conn, row: Dict[str, str], logger):
    """
    Limpia estado previo de una ONU para reprovisionar desde cero.

    Estrategia:
    1) Buscar service-ports de esa ONT y eliminarlos
    2) Eliminar ONT en interfaz GPON
    Todo en modo tolerante (continúa ante errores de inexistencia).
    """
    frame_slot, port = parse_frame_slot_port(row["PON_DESTINO"])
    onu_id = row["HUAWEI_ONU_ID"]

    logger(
        f"[INFO] [REPAIR] Limpieza previa ONU {onu_id} en GPON {frame_slot}/{port}"
    )

    # Buscar service-port(s) asociados a la ONT
    sp_display_cmd = f"display service-port port {frame_slot}/{port} ont {onu_id}"
    out = _execute_huawei_cmd_permissive(conn, sp_display_cmd, logger)
    sp_ids = _extract_service_port_ids(out)

    if sp_ids:
        for sp_id in sp_ids:
            _execute_huawei_cmd_permissive(conn, f"undo service-port {sp_id}", logger)
    else:
        logger("[INFO] [REPAIR] No se encontraron service-ports para eliminar")

    _execute_huawei_cmd_permissive(conn, f"interface gpon {frame_slot}", logger)
    _execute_huawei_cmd_permissive(conn, f"ont delete {port} {onu_id}", logger)
    _execute_huawei_cmd_permissive(conn, "quit", logger)


def _reset_to_config(conn, logger):
    """
    Recupera contexto de CLI tras un fallo para continuar con la siguiente fila.

    No existe transacción real en CLI Huawei, pero este reset evita arrastre
    de contexto parcial entre ONUs.
    """
    for cmd in ("quit", "quit", "config"):
        try:
            validate_omci_output(
                conn,
                cmd,
                logger,
                max_retries=max(1, HUAWEI_INJECTION_MAX_RETRIES),
            )
        except Exception:
            pass


def _ensure_huawei_config_mode(conn, logger):
    """
    Garantiza que la sesión quede en modo de configuración Huawei.

    Verifica el prompt antes y después de `enable`/`config` para evitar ejecutar
    comandos de inyección en contexto incorrecto.
    """
    try:
        prompt_before = conn.find_prompt().strip()
    except Exception:
        prompt_before = ""

    logger(f"[INFO] Prompt inicial SSH: {prompt_before or '<desconocido>'}")

    prompt_before_upper = prompt_before.upper()
    forbidden_hit = next(
        (p for p in HUAWEI_INJECTION_FORBIDDEN_PROMPT_PREFIXES if prompt_before_upper.startswith(p)),
        "",
    )
    if forbidden_hit:
        raise RuntimeError(
            f"ABORTADO por seguridad: prompt '{prompt_before}' coincide con prefijo prohibido '{forbidden_hit}'."
        )

    if "(" in prompt_before and ")" in prompt_before and "config" in prompt_before.lower():
        logger("[INFO] Sesion ya estaba en modo configuracion")
        return

    validate_omci_output(
        conn,
        "enable",
        logger,
        max_retries=max(1, HUAWEI_INJECTION_MAX_RETRIES),
    )

    try:
        prompt_after_enable = conn.find_prompt().strip()
    except Exception:
        prompt_after_enable = ""
    logger(f"[INFO] Prompt post-enable: {prompt_after_enable or '<desconocido>'}")

    prompt_after_enable_upper = prompt_after_enable.upper()
    forbidden_hit = next(
        (p for p in HUAWEI_INJECTION_FORBIDDEN_PROMPT_PREFIXES if prompt_after_enable_upper.startswith(p)),
        "",
    )
    if forbidden_hit:
        raise RuntimeError(
            f"ABORTADO por seguridad: prompt post-enable '{prompt_after_enable}' coincide con '{forbidden_hit}'."
        )

    validate_omci_output(
        conn,
        "config",
        logger,
        max_retries=max(1, HUAWEI_INJECTION_MAX_RETRIES),
    )

    try:
        prompt_after_config = conn.find_prompt().strip()
    except Exception:
        prompt_after_config = ""
    logger(f"[INFO] Prompt post-config: {prompt_after_config or '<desconocido>'}")

    prompt_after_config_upper = prompt_after_config.upper()
    forbidden_hit = next(
        (p for p in HUAWEI_INJECTION_FORBIDDEN_PROMPT_PREFIXES if prompt_after_config_upper.startswith(p)),
        "",
    )
    if forbidden_hit:
        raise RuntimeError(
            f"ABORTADO por seguridad: prompt post-config '{prompt_after_config}' coincide con '{forbidden_hit}'."
        )

    if not ("(" in prompt_after_config and ")" in prompt_after_config):
        raise RuntimeError(
            "No se pudo confirmar modo configuracion en la OLT (prompt inesperado tras 'config')."
        )


def run_preprovision_huawei(
    ip: str,
    username: str,
    password: str,
    rows: List[Dict[str, str]],
    logger,
    port: int = 22,
    dry_run: bool = True,
    repair_mode: bool = False,
):
    ok_count = 0
    err_count = 0

    model_totals: Dict[str, int] = {}
    unmapped_models = set()
    for row in rows:
        model = (row.get("ONT_MODEL") or "").strip().upper()
        if not model:
            model = "<SIN_MODELO>"
        model_totals[model] = model_totals.get(model, 0) + 1
        if not config.has_explicit_huawei_profile_for_model(model):
            unmapped_models.add(model)

    mapped_count = sum(
        count for model, count in model_totals.items() if config.has_explicit_huawei_profile_for_model(model)
    )
    unmapped_count = sum(model_totals[m] for m in unmapped_models)
    logger(
        "[INFO] Modelos ONT en lote -> "
        f"mapeados={mapped_count} | sin mapeo explicito={unmapped_count}"
    )
    if unmapped_models:
        logger(
            "[WARN] Modelos sin mapeo explicito detectados: "
            + ", ".join(sorted(unmapped_models))
        )
        if HUAWEI_REQUIRE_EXPLICIT_MODEL_PROFILE:
            raise ValueError(
                "Se detectaron modelos ONT sin mapeo explicito en HUAWEI_ONT_MODE_PROFILES. "
                "Se aborta para evitar provisionar con perfil generico. "
                f"Modelos: {', '.join(sorted(unmapped_models))}"
            )

    if dry_run:
        logger("[WARN] Modo simulacion activo: no se enviaran comandos a la OLT Huawei")
        logger("[INFO] Nota: en dry-run no hay wait de red ni transaccion SSH real")
        for row in rows:
            frame_slot, pon_port = parse_frame_slot_port(row["PON_DESTINO"])
            logger(
                f"[INFO] [SIMULACION] ONU {row['HUAWEI_ONU_ID']} ({row['PPPoE_USER']}) [{row.get('ONT_MODE','ROUTER')}] en GPON {frame_slot}/{pon_port}"
            )
            if repair_mode:
                logger("[INFO] [SIMULACION][REPAIR] Se ejecutaria limpieza previa (service-port + ont delete)")
            commands = build_row_commands(row)
            for cmd in commands:
                logger(f"[INFO] [CMD] {cmd}")
            ok_count += 1
        return {"ok": ok_count, "error": err_count, "total": len(rows)}

    os.makedirs("logs", exist_ok=True)
    session_log_path = os.path.join(
        "logs",
        f"huawei_injection_session_{datetime.now().strftime('%Y%m%d-%H%M%S')}.log",
    )
    logger(f"[INFO] Session log Netmiko: {session_log_path}")

    conn = ConnectHandler(
        device_type="huawei",
        host=ip,
        username=username,
        password=password,
        port=port,
        global_cmd_verify=False,
        fast_cli=False,
        session_log=session_log_path,
    )

    try:
        _ensure_huawei_config_mode(conn, logger)

        for row in rows:
            frame_slot, pon_port = parse_frame_slot_port(row["PON_DESTINO"])
            logger(
                f"[INFO] Inyectando ONU {row['HUAWEI_ONU_ID']} ({row['PPPoE_USER']}) [{row.get('ONT_MODE','ROUTER')}] en GPON {frame_slot}/{pon_port}"
            )
            commands = build_row_commands(row)
            row_error = False

            if repair_mode:
                _repair_cleanup_row(conn, row, logger)

            for cmd in commands:
                try:
                    _execute_huawei_cmd(conn, cmd, logger)
                except Exception as cmd_error:
                    logger(f"[ERROR] Fallo en ONU {row['HUAWEI_ONU_ID']}: respuesta '{str(cmd_error).strip()}'")
                    err_count += 1
                    row_error = True
                    _reset_to_config(conn, logger)
                    break

            if not row_error:
                ok_count += 1

        validate_omci_output(
            conn,
            "quit",
            logger,
            max_retries=max(1, HUAWEI_INJECTION_MAX_RETRIES),
        )
        return {"ok": ok_count, "error": err_count, "total": len(rows)}
    finally:
        conn.disconnect()