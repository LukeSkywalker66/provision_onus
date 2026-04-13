import csv
import re
from typing import Dict, List, Tuple

import paramiko


def normalize_mac(raw: str) -> str:
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", raw or "").lower()
    if len(cleaned) != 12:
        return ""
    return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))


def parse_bdcom_running_config(file_path: str) -> Dict[Tuple[int, int], Dict[str, str]]:
    """
    Retorna mapa {(pon_port, onu_id): {"sn": str, "ont_model": str}}.
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
            continue

        m_bind = re_bind.search(line)
        if m_bind and current_pon_port is not None:
            sn = m_bind.group(1).strip()
            onu_id = int(m_bind.group(2))
            key = (current_pon_port, onu_id)
            if key not in data:
                data[key] = {"sn": sn, "ont_model": ""}
            else:
                data[key]["sn"] = sn
            continue

        m_model = re_model.search(line)
        if m_model and current_pon_port is not None and current_logical is not None:
            key = (current_pon_port, current_logical)
            if key not in data:
                data[key] = {"sn": "", "ont_model": m_model.group(1).strip()}
            else:
                data[key]["ont_model"] = m_model.group(1).strip()

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
        records.append(
            {
                "mac": mac,
                "pon_port": pon_port,
                "onu_id": onu_id,
                "sn": base.get("sn", ""),
                "ont_model": base.get("ont_model", ""),
            }
        )

    return records


def _parse_key_values(line: str) -> Dict[str, str]:
    data = {}
    for k, v in re.findall(r'(\S+)=((?:"[^"]*")|\S+)', line):
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        data[k] = v
    return data


def _ssh_run_command(client: paramiko.SSHClient, cmd: str) -> str:
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    return (out + "\n" + err).strip()


def query_mikrotik_pppoe_users(host: str, username: str, password: str, port: int = 22):
    """
    Retorna mapa {mac_normalizada: pppoe_user} usando active y secret como respaldo.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=port, username=username, password=password, timeout=15)

    try:
        active_out = _ssh_run_command(client, "/ppp active print detail without-paging")
        secret_out = _ssh_run_command(client, "/ppp secret print detail without-paging")

        mac_to_user = {}

        for line in active_out.splitlines():
            line = line.strip()
            if "name=" not in line:
                continue
            row = _parse_key_values(line)
            user = row.get("name", "").strip()
            mac = normalize_mac(row.get("caller-id", ""))
            if user and mac:
                mac_to_user[mac] = user

        for line in secret_out.splitlines():
            line = line.strip()
            if "name=" not in line:
                continue
            row = _parse_key_values(line)
            user = row.get("name", "").strip()
            mac = normalize_mac(row.get("last-caller-id", ""))
            if user and mac and mac not in mac_to_user:
                mac_to_user[mac] = user

        return mac_to_user
    finally:
        client.close()


def build_migration_rows(mac_records: List[Dict[str, str]], mac_to_pppoe: Dict[str, str]):
    rows = []
    matched = 0
    for rec in mac_records:
        user = mac_to_pppoe.get(rec["mac"], "")
        if not user:
            continue
        matched += 1
        rows.append(
            {
                "PON_DESTINO": "",
                "ZTE_ONU_ID": "",
                "SN": rec.get("sn", ""),
                "PPPoE_USER": user,
                "ONT_MODEL": rec.get("ont_model", ""),
            }
        )
    return rows, matched


def export_migration_csv(output_path: str, rows: List[Dict[str, str]]):
    fields = ["PON_DESTINO", "ZTE_ONU_ID", "SN", "PPPoE_USER", "ONT_MODEL"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
