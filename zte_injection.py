import csv
import logging
import os
import socket
from datetime import datetime
from typing import Dict, List

from netmiko import ConnectHandler
from config import OLT_MAP, get_zte_injection_params


TRADUCTOR_MODELOS = {
    "F670LV9.0": "F670LV9.0",
    "EG8021V5": "EG8021V5",
    "EG8141A5": "EG8141A5",
    "IC405WSG": "IC405WSG",
    "IC425ETB": "IC425ETB",
}


REQUIRED_COLUMNS = ["PON_DESTINO", "ZTE_ONU_ID", "SN", "PPPoE_USER", "ONT_MODEL", "ONT_MODE"]
ZTE_INJECTION_PARAMS = get_zte_injection_params()


def _without_dss_hostkey(logger):
    try:
        import paramiko
    except Exception as exc:
        logger(f"[WARN] Paramiko no disponible para ajustar ssh-dss: {exc}")
        return None

    old_pubkeys = getattr(paramiko.Transport, "_preferred_pubkeys", None)
    old_keys = getattr(paramiko.Transport, "_preferred_keys", None)
    changed = False

    def _remove_dss(pref):
        if pref and "ssh-dss" in pref:
            return tuple(key for key in pref if key != "ssh-dss"), True
        return pref, False

    if old_pubkeys is not None:
        new_pubkeys, changed_pub = _remove_dss(old_pubkeys)
        if changed_pub:
            paramiko.Transport._preferred_pubkeys = new_pubkeys
            changed = True

    if old_keys is not None:
        new_keys, changed_keys = _remove_dss(old_keys)
        if changed_keys:
            paramiko.Transport._preferred_keys = new_keys
            changed = True

    if changed:
        logger("[INFO] Forzando host key sin ssh-dss para esta conexion")

    return (old_pubkeys, old_keys)


def _restore_dss_hostkey(state):
    if not state:
        return
    old_pubkeys, old_keys = state
    try:
        import paramiko
    except Exception:
        return

    if old_pubkeys is not None:
        paramiko.Transport._preferred_pubkeys = old_pubkeys
    if old_keys is not None:
        paramiko.Transport._preferred_keys = old_keys


def load_migration_csv(file_path: str) -> List[Dict[str, str]]:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV sin cabeceras")

        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV inválido: faltan columnas {missing}")

        rows = []
        for row in reader:
            cleaned = {k: (row.get(k) or "").strip() for k in REQUIRED_COLUMNS}
            if not cleaned["PON_DESTINO"] or not cleaned["ZTE_ONU_ID"] or not cleaned["SN"] or not cleaned["PPPoE_USER"]:
                continue
            rows.append(cleaned)
        return rows


def _pon_base(pon_destino: str) -> str:
    value = (pon_destino or "").strip()
    return value.replace("gpon_olt-", "", 1)


def build_row_commands(
    row: Dict[str, str],
    tcont_profile: str | None = None,
    down_profile: str | None = None,
) -> List[str]:
    pon_destino = row["PON_DESTINO"]
    zte_onu_id = row["ZTE_ONU_ID"]
    sn = row["SN"].replace(":", "")
    pppoe_user = row["PPPoE_USER"]
    ont_model = row["ONT_MODEL"]
    ont_mode = (row["ONT_MODE"] or "BRIDGE").upper()
    vlan_id = str(ZTE_INJECTION_PARAMS.get("vlan_id", "700")).strip() or "700"
    tcont_profile = (
        (tcont_profile or "").strip()
        or str(ZTE_INJECTION_PARAMS.get("tcont_profile", "SMARTOLT-300Mbps-UP")).strip()
        or "SMARTOLT-300Mbps-UP"
    )
    down_profile = (
        (down_profile or "").strip()
        or str(ZTE_INJECTION_PARAMS.get("down_profile", "SMARTOLT-300Mbps-DOWN")).strip()
        or "SMARTOLT-300Mbps-DOWN"
    )

    modelo_seguro = TRADUCTOR_MODELOS.get(ont_model, ont_model)
    pon_base = _pon_base(pon_destino)

    common = [
        f"interface {pon_destino}",
        f"onu {zte_onu_id} type {modelo_seguro} sn {sn}",
        "exit",
        f"interface gpon_onu-{pon_base}:{zte_onu_id}",
        f"name {pppoe_user}",
        f"description {pppoe_user}",
        f"tcont 1 profile {tcont_profile}",
        "gemport 1 name internet tcont 1",
        "exit",
    ]

    if ont_mode == "ROUTER":
        tail = [
            f"pon-onu-mng gpon_onu-{pon_base}:{zte_onu_id}",
            f"service vlan{vlan_id} gemport 1 vlan {vlan_id}",
            "veip 1",
            "exit",
            f"interface vport-{pon_base}.{zte_onu_id}:1",
            f"service-port 1 user-vlan {vlan_id} vlan {vlan_id}",
            f"qos traffic-policy {down_profile} direction egress",
            "exit",
        ]
    else:
        tail = [
            f"pon-onu-mng gpon_onu-{pon_base}:{zte_onu_id}",
            "dhcp-ip ethuni eth_0/1 from-internet",
            "dhcp-ip ethuni eth_0/2 from-internet",
            "dhcp-ip ethuni eth_0/3 from-internet",
            "dhcp-ip ethuni eth_0/4 from-internet",
            f"service vlan{vlan_id} gemport 1 vlan {vlan_id}",
            f"vlan port eth_0/1 mode tag vlan {vlan_id}",
            f"vlan port eth_0/2 mode tag vlan {vlan_id}",
            f"vlan port eth_0/3 mode tag vlan {vlan_id}",
            f"vlan port eth_0/4 mode tag vlan {vlan_id}",
            "exit",
            f"interface vport-{pon_base}.{zte_onu_id}:1",
            f"service-port 1 user-vlan {vlan_id} vlan {vlan_id}",
            f"qos traffic-policy {down_profile} direction egress",
            "exit",
        ]

    return common + tail


def _has_error(output: str) -> bool:
    text = (output or "").lower()
    return any(token in text for token in ["error", "invalid", "failed", "failure"])


def run_preprovision_zte(
    ip: str,
    username: str,
    password: str,
    rows: List[Dict[str, str]],
    logger,
    port: int = 22,
    dry_run: bool = True,
    olt_name: str = "",
):
    ok_count = 0
    err_count = 0

    host = (ip or "").strip()
    user = (username or "").strip()
    port = int(port or 22)
    resolved = ""
    if host:
        try:
            resolved = socket.gethostbyname(host)
        except Exception as exc:
            resolved = f"<resolve_error: {exc}>"

    prefix = f"ZTE {olt_name}".strip()
    if prefix == "ZTE":
        prefix = "ZTE"
    if resolved and resolved != host:
        conn_msg = f"[INFO] Conexion SSH {prefix} -> host={host} resolved={resolved} user={user} port={port}"
    else:
        conn_msg = f"[INFO] Conexion SSH {prefix} -> host={host} user={user} port={port}"

    logger(conn_msg)
    logging.info(conn_msg)

    if dry_run:
        logger("[WARN] Modo simulación activo: no se enviarán comandos a la OLT")
        tcont_profile = None
        down_profile = None
        if olt_name:
            cfg = OLT_MAP.get(olt_name)
            if cfg:
                tcont_profile = (cfg.get("zte_tcont_profile") or "").strip() or None
                down_profile = (cfg.get("zte_down_profile") or "").strip() or None

        tcont_profile = (
            (tcont_profile or "").strip()
            or str(ZTE_INJECTION_PARAMS.get("tcont_profile", "SMARTOLT-300Mbps-UP")).strip()
            or "SMARTOLT-300Mbps-UP"
        )
        down_profile = (
            (down_profile or "").strip()
            or str(ZTE_INJECTION_PARAMS.get("down_profile", "SMARTOLT-300Mbps-DOWN")).strip()
            or "SMARTOLT-300Mbps-DOWN"
        )
        logger(f"[INFO] Perfiles ZTE: tcont={tcont_profile} down={down_profile}")
        for row in rows:
            sn = row["SN"].replace(":", "")
            user = row["PPPoE_USER"]
            pon_destino = row["PON_DESTINO"]
            logger(f"[INFO] [SIMULACION] Provisionando SN {sn} para el usuario {user} en {pon_destino}...")
            commands = build_row_commands(row, tcont_profile=tcont_profile, down_profile=down_profile)
            logger(f"[INFO] [SIMULACION] {len(commands)} comandos generados")
            for cmd in commands:
                logger(f"[INFO] [CMD] {cmd}")
            ok_count += 1
        return {"ok": ok_count, "error": err_count, "total": len(rows)}

    tcont_profile = None
    down_profile = None
    if olt_name:
        cfg = OLT_MAP.get(olt_name)
        if cfg:
            tcont_profile = (cfg.get("zte_tcont_profile") or "").strip() or None
            down_profile = (cfg.get("zte_down_profile") or "").strip() or None

    tcont_profile = (
        (tcont_profile or "").strip()
        or str(ZTE_INJECTION_PARAMS.get("tcont_profile", "SMARTOLT-300Mbps-UP")).strip()
        or "SMARTOLT-300Mbps-UP"
    )
    down_profile = (
        (down_profile or "").strip()
        or str(ZTE_INJECTION_PARAMS.get("down_profile", "SMARTOLT-300Mbps-DOWN")).strip()
        or "SMARTOLT-300Mbps-DOWN"
    )
    logger(f"[INFO] Perfiles ZTE: tcont={tcont_profile} down={down_profile}")

    os.makedirs("logs", exist_ok=True)
    session_log_path = os.path.join(
        "logs",
        f"zte_injection_session_{datetime.now().strftime('%Y%m%d-%H%M%S')}.log",
    )
    logger(f"[INFO] Session log Netmiko: {session_log_path}")

    restore_state = _without_dss_hostkey(logger)
    try:
        conn = ConnectHandler(
            device_type="zte_zxros",
            host=host,
            username=user,
            password=password,
            port=port,
            fast_cli=False,
            session_log=session_log_path,
        )
    finally:
        _restore_dss_hostkey(restore_state)

    try:
        conn.send_command_timing("configure terminal")

        for row in rows:
            sn = row["SN"].replace(":", "")
            user = row["PPPoE_USER"]
            pon_destino = row["PON_DESTINO"]
            logger(f"[INFO] Provisionando SN {sn} para el usuario {user} en {pon_destino}...")

            commands = build_row_commands(row, tcont_profile=tcont_profile, down_profile=down_profile)
            row_error = False

            for cmd in commands:
                logger(f"[INFO] [CMD] {cmd}")
                out = conn.send_command_timing(cmd)
                if _has_error(out):
                    logger(f"[ERROR] Fallo en la inyección de {sn}. Omitiendo y continuando con el siguiente")
                    row_error = True
                    err_count += 1
                    # Reset de contexto para siguiente fila
                    conn.send_command_timing("end")
                    conn.send_command_timing("configure terminal")
                    break

            if not row_error:
                ok_count += 1

        conn.send_command_timing("exit")
        return {"ok": ok_count, "error": err_count, "total": len(rows)}
    finally:
        conn.disconnect()
