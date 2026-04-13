import csv
import re
from typing import Dict, List, Tuple

from librouteros import connect as routeros_connect


def normalize_mac(raw: str) -> str:
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", raw or "").lower()
    if len(cleaned) != 12:
        return ""
    return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))


def parse_bdcom_running_config(file_path: str) -> Dict[Tuple[int, int], Dict[str, str]]:
    """
    Retorna mapa {(pon_port, onu_id): {"sn": str, "ont_model": str, "ont_mode": str}}.
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    lines = text.splitlines()
    current_pon_port = None
    current_logical = None
    data: Dict[Tuple[int, int], Dict[str, str]] = {}

    re_int_physical = re.compile(r"^\s*interface\s+GPON0/(\d+)\s*$", re.IGNORECASE)
    re_int_logical = re.compile(r"^\s*interface\s+GPON0/(\d+):(\d+)\s*$", re.IGNORECASE)
    re_bind = re.compile(r"\bgpon\s+bind-onu\s+sn\s+(\S+)\s+(\d+)\b", re.IGNORECASE)
    re_model = re.compile(r"\bgpon\s+onu\s+model-id\s+(\S+)\b", re.IGNORECASE)
    re_flow_profile = re.compile(r"\bgpon\s+onu\s+flow-mapping-profile\s+(\S+)\b", re.IGNORECASE)

    for line in lines:
        m_physical = re_int_physical.match(line)
        if m_physical:
            current_pon_port = int(m_physical.group(1))
            current_logical = None
            continue

        m_logical = re_int_logical.match(line)
        if m_logical:
            current_pon_port = int(m_logical.group(1))
            current_logical = int(m_logical.group(2))
            key = (current_pon_port, current_logical)
            if key not in data:
                data[key] = {"sn": "", "ont_model": "", "ont_mode": "BRIDGE"}
            elif not data[key].get("ont_mode"):
                data[key]["ont_mode"] = "BRIDGE"
            continue

        m_bind = re_bind.search(line)
        if m_bind and current_pon_port is not None:
            sn = m_bind.group(1).strip()
            onu_id = int(m_bind.group(2))
            key = (current_pon_port, onu_id)
            if key not in data:
                data[key] = {"sn": sn, "ont_model": "", "ont_mode": ""}
            else:
                data[key]["sn"] = sn
            continue

        m_model = re_model.search(line)
        if m_model and current_pon_port is not None and current_logical is not None:
            key = (current_pon_port, current_logical)
            if key not in data:
                data[key] = {"sn": "", "ont_model": m_model.group(1).strip(), "ont_mode": ""}
            else:
                data[key]["ont_model"] = m_model.group(1).strip()

        m_flow = re_flow_profile.search(line)
        if m_flow and current_pon_port is not None and current_logical is not None:
            profile_name = m_flow.group(1).strip().lower()
            key = (current_pon_port, current_logical)
            if key not in data:
                data[key] = {"sn": "", "ont_model": "", "ont_mode": ""}
            data[key]["ont_mode"] = "ROUTER" if "-hgu" in profile_name else "BRIDGE"

    return data


def parse_bdcom_mac_table(file_path: str, running_map: Dict[Tuple[int, int], Dict[str, str]]):
    """
    Cruza MAC table con running_map.
    Retorna lista de registros con: mac, sn, ont_model, pon_port, onu_id.
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    records = []
    seen = set()

    pattern = re.compile(
        r"^\s*(\d+)\s+([0-9A-Fa-f:.-]{12,})\s+DYNAMIC\s+gpon0/(\d+):(\d+)-1\s*$",
        re.IGNORECASE,
    )

    for line in text.splitlines():
        m = pattern.match(line)
        if not m:
            continue

        mac = normalize_mac(m.group(2))
        if not mac:
            continue

        pon_port = int(m.group(3))
        onu_id = int(m.group(4))
        key = (pon_port, onu_id)

        if key in seen:
            continue
        seen.add(key)

        base = running_map.get(key, {"sn": "", "ont_model": ""})
        source_port = f"gpon0/{pon_port}".lower()
        records.append(
            {
                "mac": mac,
                "pon_port": pon_port,
                "onu_id": onu_id,
                "source_port": source_port,
                "sn": base.get("sn", ""),
                "ont_model": base.get("ont_model", ""),
                "ont_mode": base.get("ont_mode", ""),
            }
        )

    return records


def query_mikrotik_pppoe_users(host: str, username: str, password: str, port: int = 8728):
    """
    Retorna mapa {mac_normalizada: pppoe_user} usando API de MikroTik.
    Fuente:
    - /ppp/active: name + caller-id
    - /ppp/secret: name + last-caller-id (respaldo)
    """
    api = routeros_connect(
        host=host,
        username=username,
        password=password,
        port=port,
        timeout=15,
    )

    mac_to_user = {}

    active_rows = api.path("ppp", "active").select("name", "caller-id")
    for row in active_rows:
        user = str(row.get("name", "")).strip()
        mac = normalize_mac(str(row.get("caller-id", "")))
        if user and mac:
            mac_to_user[mac] = user

    secret_rows = api.path("ppp", "secret").select("name", "last-caller-id")
    for row in secret_rows:
        user = str(row.get("name", "")).strip()
        mac = normalize_mac(str(row.get("last-caller-id", "")))
        if user and mac and mac not in mac_to_user:
            mac_to_user[mac] = user

    return mac_to_user


def build_pon_destino(source_port: str, zte_board: str) -> str:
    """
    Convierte puerto BDCOM (gpon0/X) a formato ZTE en espejo:
    gpon_olt-{zte_board}/{X}
    """
    source = (source_port or "").strip().lower()
    board = (zte_board or "").strip().strip("/")
    if not source or not board:
        return ""

    match = re.search(r"gpon0/(\d+)$", source)
    if not match:
        return ""
    port = match.group(1)
    return f"gpon_olt-{board}/{port}"


def build_migration_rows(mac_records: List[Dict[str, str]], mac_to_pppoe: Dict[str, str], zte_board: str):
    rows = []
    matched = 0
    for rec in mac_records:
        user = mac_to_pppoe.get(rec["mac"], "")
        if not user:
            continue
        matched += 1
        source_port = str(rec.get("source_port", "")).lower().strip()
        pon_destino = build_pon_destino(source_port, zte_board)
        sn_clean = str(rec.get("sn", "")).replace(":", "")
        rows.append(
            {
                "PON_DESTINO": pon_destino,
                "ZTE_ONU_ID": rec.get("onu_id", ""),
                "SN": sn_clean,
                "PPPoE_USER": user,
                "ONT_MODEL": rec.get("ont_model", ""),
                "ONT_MODE": rec.get("ont_mode", ""),
            }
        )
    return rows, matched


def export_migration_csv(output_path: str, rows: List[Dict[str, str]]):
    fields = ["PON_DESTINO", "ZTE_ONU_ID", "SN", "PPPoE_USER", "ONT_MODEL", "ONT_MODE"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
