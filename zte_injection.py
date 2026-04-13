import csv
from typing import Dict, List

from netmiko import ConnectHandler


TRADUCTOR_MODELOS = {
    "F670LV9.0": "F670LV9.0",
    "EG8021V5": "EG8021V5",
    "EG8141A5": "EG8141A5",
    "IC405WSG": "IC405WSG",
    "IC425ETB": "IC425ETB",
}


REQUIRED_COLUMNS = ["PON_DESTINO", "ZTE_ONU_ID", "SN", "PPPoE_USER", "ONT_MODEL", "ONT_MODE"]


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


def build_row_commands(row: Dict[str, str]) -> List[str]:
    pon_destino = row["PON_DESTINO"]
    zte_onu_id = row["ZTE_ONU_ID"]
    sn = row["SN"].replace(":", "")
    pppoe_user = row["PPPoE_USER"]
    ont_model = row["ONT_MODEL"]
    ont_mode = (row["ONT_MODE"] or "BRIDGE").upper()

    modelo_seguro = TRADUCTOR_MODELOS.get(ont_model, ont_model)
    pon_base = _pon_base(pon_destino)

    common = [
        f"interface {pon_destino}",
        f"onu {zte_onu_id} type {modelo_seguro} sn {sn}",
        "exit",
        f"interface gpon_onu-{pon_base}:{zte_onu_id}",
        f"name {pppoe_user}",
        f"description {pppoe_user}",
        "tcont 1 profile SMARTOLT-300Mbps-UP",
        "gemport 1 name internet tcont 1",
        "exit",
    ]

    if ont_mode == "ROUTER":
        tail = [
            f"pon-onu-mng gpon_onu-{pon_base}:{zte_onu_id}",
            "service vlan700 gemport 1 vlan 700",
            "veip 1",
            "exit",
            f"interface vport-{pon_base}.{zte_onu_id}:1",
            "service-port 1 user-vlan 700 vlan 700",
            "qos traffic-policy SMARTOLT-300Mbps-DOWN direction egress",
            "exit",
        ]
    else:
        tail = [
            f"pon-onu-mng gpon_onu-{pon_base}:{zte_onu_id}",
            "dhcp-ip ethuni eth_0/1 from-internet",
            "dhcp-ip ethuni eth_0/2 from-internet",
            "dhcp-ip ethuni eth_0/3 from-internet",
            "dhcp-ip ethuni eth_0/4 from-internet",
            "service vlan700 gemport 1 vlan 700",
            "vlan port eth_0/1 mode tag vlan 700",
            "vlan port eth_0/2 mode tag vlan 700",
            "vlan port eth_0/3 mode tag vlan 700",
            "vlan port eth_0/4 mode tag vlan 700",
            "exit",
            f"interface vport-{pon_base}.{zte_onu_id}:1",
            "service-port 1 user-vlan 700 vlan 700",
            "qos traffic-policy SMARTOLT-300Mbps-DOWN direction egress",
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
):
    ok_count = 0
    err_count = 0

    if dry_run:
        logger("[WARN] Modo simulación activo: no se enviarán comandos a la OLT")
        for row in rows:
            sn = row["SN"].replace(":", "")
            user = row["PPPoE_USER"]
            pon_destino = row["PON_DESTINO"]
            logger(f"[INFO] [SIMULACION] Provisionando SN {sn} para el usuario {user} en {pon_destino}...")
            commands = build_row_commands(row)
            logger(f"[INFO] [SIMULACION] {len(commands)} comandos generados")
            ok_count += 1
        return {"ok": ok_count, "error": err_count, "total": len(rows)}

    conn = ConnectHandler(
        device_type="zte_zxros",
        host=ip,
        username=username,
        password=password,
        port=port,
        fast_cli=False,
    )

    try:
        conn.send_command_timing("configure terminal")

        for row in rows:
            sn = row["SN"].replace(":", "")
            user = row["PPPoE_USER"]
            pon_destino = row["PON_DESTINO"]
            logger(f"[INFO] Provisionando SN {sn} para el usuario {user} en {pon_destino}...")

            commands = build_row_commands(row)
            row_error = False

            for cmd in commands:
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
