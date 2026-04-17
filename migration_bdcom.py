import csv
import re
from functools import lru_cache
from typing import Dict, List, Tuple

from librouteros import connect as routeros_connect

from config import (
    ENABLE_MAC_VENDOR_BRIDGE_HEURISTIC,
    MAC_OUI_VENDOR_OVERRIDES,
    SN_MAC_MISMATCH_BRIDGE_SN_VENDORS,
    get_mode_override_for_model,
    get_vendor_from_mac_vendor_name,
    get_vendor_from_sn,
    is_bridge_only_model,
    is_huawei_mac_validation_model,
    is_known_router_model,
)

try:
    from manuf import manuf as manuf_module
except Exception:
    manuf_module = None


def normalize_mac(raw: str) -> str:
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", raw or "").lower()
    if len(cleaned) != 12:
        return ""
    return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))


def mac_to_oui(mac: str) -> str:
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", mac or "").upper()
    if len(cleaned) < 6:
        return ""
    return cleaned[:6]


class MacVendorResolver:
    """
    Resuelve vendor por MAC de forma eficiente.

    Orden de resolución:
    1) Overrides por OUI desde .env (O(1))
    2) Base local de manuf (si está instalada)
    3) Vacío si no se pudo resolver
    """

    def __init__(self):
        self._override_map = dict(MAC_OUI_VENDOR_OVERRIDES)
        self._parser = None
        if manuf_module is not None:
            try:
                self._parser = manuf_module.MacParser()
            except Exception:
                self._parser = None

    def has_data_source(self) -> bool:
        return bool(self._override_map) or self._parser is not None

    def diagnostics(self) -> Dict[str, object]:
        return {
            "overrides_count": len(self._override_map),
            "manuf_available": self._parser is not None,
            "has_data_source": self.has_data_source(),
        }

    @lru_cache(maxsize=8192)
    def resolve(self, mac: str) -> str:
        norm = normalize_mac(mac)
        if not norm:
            return ""

        oui = mac_to_oui(norm)
        if oui in self._override_map:
            return self._override_map[oui]

        if self._parser is not None:
            try:
                vendor = self._parser.get_manuf(norm)
                return (vendor or "").strip().upper()
            except Exception:
                return ""

        return ""


MAC_VENDOR_RESOLVER = MacVendorResolver()


def get_mac_vendor_heuristic_diagnostics() -> Dict[str, object]:
    return {
        "enabled": ENABLE_MAC_VENDOR_BRIDGE_HEURISTIC,
        "mismatch_bridge_sn_vendors": sorted(SN_MAC_MISMATCH_BRIDGE_SN_VENDORS),
        **MAC_VENDOR_RESOLVER.diagnostics(),
    }


def _resolve_ont_mode_mac_first(base_mode: str, ont_model: str, sn: str, mac: str) -> Tuple[str, str]:
    """
    Estrategia de clasificación ONT_MODE:

    1) Vendor por SN (prefijos, ej: ZTE/TPL/HWT)
    2) Vendor por MAC (resuelto por OUI/manuf y normalizado)
       - Si ambos existen y son inconsistentes => BRIDGE
       - Si ambos existen y coinciden => ROUTER
    3) Fallback a profile/flow de OLT origen (base_mode)
    4) Fallback por override de modelo
    5) Fallback por modelo conocido router
    6) Default final: ROUTER (marcado para revisión)
    """
    if is_bridge_only_model(ont_model):
        return "BRIDGE", "BRIDGE_ONLY_MODEL"

    mode = (base_mode or "").strip().upper()
    sn_vendor = get_vendor_from_sn(sn)
    mac_vendor_norm = ""

    if ENABLE_MAC_VENDOR_BRIDGE_HEURISTIC:
        mac_vendor = MAC_VENDOR_RESOLVER.resolve(mac)
        if mac_vendor:
            mac_vendor_norm = get_vendor_from_mac_vendor_name(mac_vendor)

    # Regla específica para modelos mixtos: si la MAC no resuelve como Huawei,
    # clasificar como BRIDGE de forma determinística.
    if is_huawei_mac_validation_model(ont_model) and mac_vendor_norm and mac_vendor_norm != "HUAWEI":
        return "BRIDGE", "TARGET_MODEL_NON_HUAWEI_MAC"

    if ENABLE_MAC_VENDOR_BRIDGE_HEURISTIC and sn_vendor and mac_vendor_norm:
        if (
            sn_vendor in SN_MAC_MISMATCH_BRIDGE_SN_VENDORS
            and sn_vendor != mac_vendor_norm
        ):
            return "BRIDGE", "SN_MAC_VENDOR_MISMATCH"
        return "ROUTER", "SN_MAC_VENDOR_MATCH"

    if mode in {"ROUTER", "BRIDGE"}:
        return mode, "SOURCE_PROFILE_FALLBACK"

    override_mode = get_mode_override_for_model(ont_model)
    if override_mode:
        return override_mode, "OVERRIDE_FALLBACK"

    if is_known_router_model(ont_model):
        return "ROUTER", "KNOWN_ROUTER_MODEL_FALLBACK"

    return "ROUTER", "UNRESOLVED_DEFAULT_ROUTER"


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
    re_flow_profile = re.compile(r"^\s*gpon\s+onu\s+flow-mapping-profile\b", re.IGNORECASE)

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
            model_id = m_model.group(1).strip()
            key = (current_pon_port, current_logical)
            if key not in data:
                data[key] = {"sn": "", "ont_model": model_id, "ont_mode": ""}
            else:
                data[key]["ont_model"] = model_id

        m_flow = re_flow_profile.search(line)
        if m_flow and current_pon_port is not None and current_logical is not None:
            line_lower = line.strip().lower()
            key = (current_pon_port, current_logical)
            if key not in data:
                data[key] = {"sn": "", "ont_model": "", "ont_mode": ""}

            data[key]["ont_mode"] = (
                "ROUTER" if "flow-mapping-default-hgu" in line_lower else "BRIDGE"
            )

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


def build_pon_destino(source_port: str, destination_board: str, destination_vendor: str = "zte") -> str:
    """
    Convierte puerto BDCOM (gpon0/X) a formato de destino en espejo.

    - ZTE: gpon_olt-{board}/{X}
    - Huawei: {board}/{X}
    """
    source = (source_port or "").strip().lower()
    board = (destination_board or "").strip().strip("/")
    vendor = (destination_vendor or "zte").strip().lower()
    if not source or not board:
        return ""

    match = re.search(r"gpon0/(\d+)$", source)
    if not match:
        return ""
    port = match.group(1)
    if vendor == "huawei":
        try:
            port_num = int(port)
        except ValueError:
            return ""
        # Huawei usa numeración de puertos base 0 en este flujo.
        corrected_port = max(0, port_num - 1)
        return f"{board}/{corrected_port}"
    return f"gpon_olt-{board}/{port}"


def build_migration_rows(
    mac_records: List[Dict[str, str]],
    mac_to_pppoe: Dict[str, str],
    destination_board: str,
    destination_vendor: str = "zte",
):
    rows = []
    matched = 0
    stats = {
        "final_router": 0,
        "final_bridge": 0,
        "bridge_only_model": 0,
        "sn_mac_vendor_mismatch": 0,
        "sn_mac_vendor_match": 0,
        "source_profile_fallback": 0,
        "override_fallback": 0,
        "known_router_model_fallback": 0,
        "unresolved_default_router": 0,
    }
    for rec in mac_records:
        user = mac_to_pppoe.get(rec["mac"], "")
        if not user:
            continue
        matched += 1
        source_port = str(rec.get("source_port", "")).lower().strip()
        pon_destino = build_pon_destino(source_port, destination_board, destination_vendor)
        sn_clean = str(rec.get("sn", "")).replace(":", "")
        ont_model = rec.get("ont_model", "")
        base_mode = rec.get("ont_mode", "")
        final_mode, mode_reason = _resolve_ont_mode_mac_first(
            base_mode,
            ont_model,
            rec.get("sn", ""),
            rec.get("mac", ""),
        )

        if final_mode == "ROUTER":
            stats["final_router"] += 1
        else:
            stats["final_bridge"] += 1

        if mode_reason == "BRIDGE_ONLY_MODEL":
            stats["bridge_only_model"] += 1
        elif mode_reason == "SN_MAC_VENDOR_MISMATCH":
            stats["sn_mac_vendor_mismatch"] += 1
        elif mode_reason == "SN_MAC_VENDOR_MATCH":
            stats["sn_mac_vendor_match"] += 1
        elif mode_reason == "SOURCE_PROFILE_FALLBACK":
            stats["source_profile_fallback"] += 1
        elif mode_reason == "OVERRIDE_FALLBACK":
            stats["override_fallback"] += 1
        elif mode_reason == "KNOWN_ROUTER_MODEL_FALLBACK":
            stats["known_router_model_fallback"] += 1
        elif mode_reason == "UNRESOLVED_DEFAULT_ROUTER":
            stats["unresolved_default_router"] += 1

        rows.append(
            {
                "PON_DESTINO": pon_destino,
                "ZTE_ONU_ID": rec.get("onu_id", ""),
                "SN": sn_clean,
                "PPPoE_USER": user,
                "ONT_MODEL": ont_model,
                "ONT_MODE": final_mode,
            }
        )
    return rows, matched, stats


def export_migration_csv(output_path: str, rows: List[Dict[str, str]]):
    fields = ["PON_DESTINO", "ZTE_ONU_ID", "SN", "PPPoE_USER", "ONT_MODEL", "ONT_MODE"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
