import csv
import re
from typing import Dict, List, Tuple

from netmiko import ConnectHandler
import config


# Cargar configuracion de Perfiles Huawei desde config.py (que lee desde .env)
_huawei_config = config.get_huawei_injection_params()
VLAN_ID = _huawei_config["vlan_id"]
TRAFFIC_TABLE_UP = _huawei_config["traffic_table_up"]
TRAFFIC_TABLE_DOWN = _huawei_config["traffic_table_down"]

# Perfiles para modo ROUTER
LINE_PROF_ROUTER = _huawei_config["line_prof_router"]
SRV_PROF_ROUTER = _huawei_config["srv_prof_router"]

# Perfiles para modo BRIDGE
LINE_PROF_BRIDGE = _huawei_config["line_prof_bridge"]
SRV_PROF_BRIDGE = _huawei_config["srv_prof_bridge"]


REQUIRED_COLUMNS_BASE = ["PON_DESTINO", "SN", "PPPoE_USER", "ONT_MODE"]
HUAWEI_ID_CANDIDATES = ["ID", "HUAWEI_ONU_ID", "ZTE_ONU_ID"]


def _pick_huawei_onu_id(row: Dict[str, str]) -> str:
    for key in HUAWEI_ID_CANDIDATES:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


def load_migration_csv(file_path: str) -> List[Dict[str, str]]:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV sin cabeceras")

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
                "ONT_MODE": (row.get("ONT_MODE") or "BRIDGE").strip().upper(),
            }
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
    frame_slot, port = parse_frame_slot_port(row["PON_DESTINO"])
    onu_id = row["HUAWEI_ONU_ID"]
    sn = row["SN"].replace(":", "")
    pppoe_user = row["PPPoE_USER"]
    ont_mode = (row["ONT_MODE"] or "BRIDGE").upper()

    if ont_mode == "ROUTER":
        return [
            f"interface gpon {frame_slot}",
            (
                f"ont add {port} {onu_id} sn-auth {sn} omci "
                f"ont-lineprofile-id {LINE_PROF_ROUTER} ont-srvprofile-id {SRV_PROF_ROUTER} "
                f"desc \"{pppoe_user}\""
            ),
            "quit",
            (
                f"service-port vlan {VLAN_ID} gpon {frame_slot}/{port} ont {onu_id} gemport 1 "
                f"multi-service user-vlan {VLAN_ID} rx-cttr {TRAFFIC_TABLE_UP} tx-cttr {TRAFFIC_TABLE_DOWN}"
            ),
        ]

    return [
        f"interface gpon {frame_slot}",
        (
            f"ont add {port} {onu_id} sn-auth {sn} omci "
            f"ont-lineprofile-id {LINE_PROF_BRIDGE} ont-srvprofile-id {SRV_PROF_BRIDGE} "
            f"desc \"{pppoe_user}\""
        ),
        f"ont port native-vlan {port} {onu_id} eth 1 vlan {VLAN_ID}",
        "quit",
        (
            f"service-port vlan {VLAN_ID} gpon {frame_slot}/{port} ont {onu_id} gemport 1 "
            f"multi-service user-vlan {VLAN_ID} rx-cttr {TRAFFIC_TABLE_UP} tx-cttr {TRAFFIC_TABLE_DOWN}"
        ),
    ]


def _has_error(output: str) -> bool:
    text = (output or "").lower()
    return any(token in text for token in ["failure", "error", "already exists", "invalid", "incomplete"])


def run_preprovision_huawei(
    ip: str,
    username: str,
    password: str,
    rows: List[Dict[str, str]],
    logger,
    port: int = 22,
    dry_run: bool = True,
):
    ok_count = 0
    err_count = 0

    if dry_run:
        logger("[WARN] Modo simulacion activo: no se enviaran comandos a la OLT Huawei")
        for row in rows:
            frame_slot, pon_port = parse_frame_slot_port(row["PON_DESTINO"])
            logger(
                f"[INFO] [SIMULACION] ONU {row['HUAWEI_ONU_ID']} ({row['PPPoE_USER']}) en GPON {frame_slot}/{pon_port}"
            )
            commands = build_row_commands(row)
            for cmd in commands:
                logger(f"[INFO] [CMD] {cmd}")
            ok_count += 1
        return {"ok": ok_count, "error": err_count, "total": len(rows)}

    conn = ConnectHandler(
        device_type="huawei",
        host=ip,
        username=username,
        password=password,
        port=port,
        fast_cli=False,
    )

    try:
        conn.send_command_timing("enable")
        conn.send_command_timing("config")

        for row in rows:
            frame_slot, pon_port = parse_frame_slot_port(row["PON_DESTINO"])
            logger(
                f"[INFO] Inyectando ONU {row['HUAWEI_ONU_ID']} ({row['PPPoE_USER']}) en GPON {frame_slot}/{pon_port}"
            )
            commands = build_row_commands(row)
            row_error = False

            for cmd in commands:
                logger(f"[INFO] [CMD] {cmd}")
                out = conn.send_command_timing(cmd)
                if _has_error(out):
                    logger(f"[ERROR] Fallo en ONU {row['HUAWEI_ONU_ID']}: respuesta '{out.strip()}'")
                    err_count += 1
                    row_error = True
                    conn.send_command_timing("quit")
                    conn.send_command_timing("quit")
                    conn.send_command_timing("config")
                    break

            if not row_error:
                ok_count += 1

        conn.send_command_timing("quit")
        return {"ok": ok_count, "error": err_count, "total": len(rows)}
    finally:
        conn.disconnect()