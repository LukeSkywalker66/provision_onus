import csv
from logging import config
import os
import re
import subprocess
import tempfile
import os
import shlex
import config
import shutil
import socket
import time
import subprocess
import tempfile
import os
import telnetlib
import select
from functools import lru_cache
from typing import Dict, List, Optional, Tuple
from librouteros import connect as routeros_connect
from netmiko import ConnectHandler
import paramiko

# Inyecci├│n Agresiva de Algoritmos Legacy (KEX, RSA, DSS)
legacy_kex = ('diffie-hellman-group1-sha1', 'diffie-hellman-group14-sha1')
legacy_keys = ('ssh-rsa', 'ssh-dss')
# Parche estricto para KEX legacy (TP-Link)
if 'diffie-hellman-group1-sha1' not in paramiko.Transport._preferred_kex:
    paramiko.Transport._preferred_kex = ('diffie-hellman-group1-sha1', 'diffie-hellman-group14-sha1') + paramiko.Transport._preferred_kex

for kex in legacy_kex:
    if kex not in paramiko.Transport._preferred_kex:
        paramiko.Transport._preferred_kex = (kex,) + paramiko.Transport._preferred_kex

for key in legacy_keys:
    if key not in paramiko.Transport._preferred_pubkeys:
        paramiko.Transport._preferred_pubkeys = (key,) + paramiko.Transport._preferred_pubkeys
    # Paramiko maneja internamente _preferred_keys para host keys
    if hasattr(paramiko.Transport, '_preferred_keys') and key not in paramiko.Transport._preferred_keys:
        paramiko.Transport._preferred_keys = (key,) + paramiko.Transport._preferred_keys

from config import (
    ENABLE_MAC_VENDOR_BRIDGE_HEURISTIC,
    MAC_OUI_VENDOR_OVERRIDES,
    SN_MAC_MISMATCH_BRIDGE_SN_VENDORS,
    TPLINK_DEFAULT_ONT_MODEL,
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

    Orden de resoluci├│n:
    1) Overrides por OUI desde .env (O(1))
    2) Base local de manuf (si est├í instalada)
    3) Vac├¡o si no se pudo resolver
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
    Estrategia de clasificaci├│n ONT_MODE:

    1) Vendor por SN (prefijos, ej: ZTE/TPL/HWT)
    2) Vendor por MAC (resuelto por OUI/manuf y normalizado)
       - Si ambos existen y son inconsistentes => BRIDGE
       - Si ambos existen y coinciden => ROUTER
    3) Fallback a profile/flow de OLT origen (base_mode)
    4) Fallback por override de modelo
    5) Fallback por modelo conocido router
    6) Default final: ROUTER (marcado para revisi├│n)
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

    # Regla espec├¡fica para modelos mixtos: si la MAC no resuelve como Huawei,
    # clasificar como BRIDGE de forma determin├¡stica.
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


def detect_olt_origin_from_running(file_path: str) -> str:
    """
    Detecta origen del running-config: bdcom | tplink.
    Default por compatibilidad: bdcom cuando no hay se├▒ales claras.
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read().lower()

    bdcom_markers = [
        "welcome to bdcom",
        "gpon bind-onu sn",
        "flow-mapping-default-hgu",
    ]
    tplink_markers = [
        "tp-link",
        "interface gpon ",
        "onu add",
        "ont add",
    ]

    bdcom_score = sum(1 for marker in bdcom_markers if marker in text)
    tplink_score = sum(1 for marker in tplink_markers if marker in text)

    if tplink_score > bdcom_score:
        return "tplink"
    return "bdcom"


def _normalize_sn_value(raw_sn: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", (raw_sn or "")).upper()


def _infer_tplink_mode_from_lineprofile(lineprofile_id: str, raw_line: str = "") -> str:
    """
    Inferencia conservadora del modo TP-Link a partir del perfil de l├¡nea.

    Criterio actual:
    - lineprofile 0 -> BRIDGE
    - cualquier otro lineprofile -> ROUTER
    - si el texto de la l├¡nea trae se├▒ales expl├¡citas, se respetan primero
    """
    line_lower = (raw_line or "").lower()
    if "flow-mapping-default-hgu" in line_lower or " veip" in line_lower:
        return "ROUTER"
    if "flow-mapping-default" in line_lower:
        return "BRIDGE"

    try:
        profile_num = int(str(lineprofile_id).strip())
    except Exception:
        return ""

    return "BRIDGE" if profile_num == 0 else "ROUTER"


def parse_tplink_running_config(file_path: str) -> Dict[Tuple[int, int], Dict[str, str]]:
    """
    Parser tolerant para running-config de TP-Link GPON OLT.
    Mantiene estructura de salida compatible con BDCOM:
      {(pon_port, onu_id): {"sn": str, "ont_model": str, "ont_mode": str}}
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.read().splitlines()

    current_pon_port = None
    current_logical = None
    data: Dict[Tuple[int, int], Dict[str, str]] = {}

    re_int_physical_patterns = [
        re.compile(r"^\s*interface\s+GPON0/(\d+)\s*$", re.IGNORECASE),
        re.compile(r"^\s*interface\s+GPON\s+\d+/\d+/(\d+)\s*$", re.IGNORECASE),
    ]
    re_int_logical_patterns = [
        re.compile(r"^\s*interface\s+GPON0/(\d+):(\d+)\s*$", re.IGNORECASE),
        re.compile(r"^\s*interface\s+GPON\s+\d+/\d+/(\d+):(\d+)\s*$", re.IGNORECASE),
    ]

    re_bind_bdcom = re.compile(r"\bgpon\s+bind-onu\s+sn\s+(\S+)\s+(\d+)\b", re.IGNORECASE)
    re_bind_tplink_a = re.compile(
        r"\b(?:onu|ont)\s+add\s+(\d+)\s+sn\s+(\S+)\s+ont-lineprofile-id\s+(\d+)\s+ont-srvprofile-id\s+(\d+)",
        re.IGNORECASE,
    )
    re_bind_tplink_b = re.compile(
        r"\b(?:onu|ont)\s+add\s+sn\s+(\S+)\s+(\d+)\s+ont-lineprofile-id\s+(\d+)\s+ont-srvprofile-id\s+(\d+)",
        re.IGNORECASE,
    )
    re_bind_tplink_sn_auth = re.compile(
        r"\b(?:onu|ont)\s+add\s+(\d+)\s+sn-auth\s+(\S+)\s+ont-lineprofile-id\s+(\d+)\s+ont-srvprofile-id\s+(\d+)",
        re.IGNORECASE,
    )

    re_model_patterns = [
        re.compile(r"\bgpon\s+onu\s+model-id\s+(\S+)\b", re.IGNORECASE),
        re.compile(r"\b(?:onu|ont)\s+model(?:-id)?\s+(\S+)\b", re.IGNORECASE),
    ]

    for raw_line in lines:
        line = raw_line.rstrip()
        line_lower = line.lower()

        matched_physical = False
        for pattern in re_int_physical_patterns:
            m_physical = pattern.match(line)
            if m_physical:
                current_pon_port = int(m_physical.group(1))
                current_logical = None
                matched_physical = True
                break
        if matched_physical:
            continue

        matched_logical = False
        for pattern in re_int_logical_patterns:
            m_logical = pattern.match(line)
            if m_logical:
                current_pon_port = int(m_logical.group(1))
                current_logical = int(m_logical.group(2))
                key = (current_pon_port, current_logical)
                if key not in data:
                    data[key] = {"sn": "", "ont_model": "", "ont_mode": "BRIDGE"}
                elif not data[key].get("ont_mode"):
                    data[key]["ont_mode"] = "BRIDGE"
                matched_logical = True
                break
        if matched_logical:
            continue

        m_bind = re_bind_bdcom.search(line)
        if m_bind and current_pon_port is not None:
            sn = _normalize_sn_value(m_bind.group(1))
            onu_id = int(m_bind.group(2))
            key = (current_pon_port, onu_id)
            if key not in data:
                data[key] = {"sn": sn, "ont_model": "", "ont_mode": ""}
            else:
                data[key]["sn"] = sn
            continue

        m_bind = re_bind_tplink_a.search(line)
        if m_bind and current_pon_port is not None:
            lineprofile_id = m_bind.group(3)
            onu_id = int(m_bind.group(1))
            sn = _normalize_sn_value(m_bind.group(2))
            key = (current_pon_port, onu_id)
            if key not in data:
                data[key] = {
                    "sn": sn,
                    "ont_model": "",
                    "ont_mode": _infer_tplink_mode_from_lineprofile(lineprofile_id, line),
                }
            else:
                data[key]["sn"] = sn
                inferred_mode = _infer_tplink_mode_from_lineprofile(lineprofile_id, line)
                if inferred_mode:
                    data[key]["ont_mode"] = inferred_mode
            continue

        m_bind = re_bind_tplink_b.search(line)
        if m_bind and current_pon_port is not None:
            lineprofile_id = m_bind.group(3)
            sn = _normalize_sn_value(m_bind.group(1))
            onu_id = int(m_bind.group(2))
            key = (current_pon_port, onu_id)
            if key not in data:
                data[key] = {
                    "sn": sn,
                    "ont_model": "",
                    "ont_mode": _infer_tplink_mode_from_lineprofile(lineprofile_id, line),
                }
            else:
                data[key]["sn"] = sn
                inferred_mode = _infer_tplink_mode_from_lineprofile(lineprofile_id, line)
                if inferred_mode:
                    data[key]["ont_mode"] = inferred_mode
            continue

        m_bind = re_bind_tplink_sn_auth.search(line)
        if m_bind and current_pon_port is not None:
            lineprofile_id = m_bind.group(3)
            onu_id = int(m_bind.group(1))
            sn = _normalize_sn_value(m_bind.group(2))
            key = (current_pon_port, onu_id)
            if key not in data:
                data[key] = {
                    "sn": sn,
                    "ont_model": "",
                    "ont_mode": _infer_tplink_mode_from_lineprofile(lineprofile_id, line),
                }
            else:
                data[key]["sn"] = sn
                inferred_mode = _infer_tplink_mode_from_lineprofile(lineprofile_id, line)
                if inferred_mode:
                    data[key]["ont_mode"] = inferred_mode
            continue

        for pattern in re_model_patterns:
            m_model = pattern.search(line)
            if m_model and current_pon_port is not None and current_logical is not None:
                model_id = m_model.group(1).strip()
                key = (current_pon_port, current_logical)
                if key not in data:
                    data[key] = {"sn": "", "ont_model": model_id, "ont_mode": ""}
                else:
                    data[key]["ont_model"] = model_id
                break

        if current_pon_port is not None and current_logical is not None:
            key = (current_pon_port, current_logical)
            if key not in data:
                data[key] = {"sn": "", "ont_model": "", "ont_mode": ""}

            if not data[key].get("ont_mode"):
                if "flow-mapping-default-hgu" in line_lower or " veip" in line_lower:
                    data[key]["ont_mode"] = "ROUTER"
                elif "flow-mapping-default" in line_lower:
                    data[key]["ont_mode"] = "BRIDGE"

    return data


def parse_running_config_auto(file_path: str, forced_origin: Optional[str] = None):
    """
    Parser de running-config con detecci├│n o forzado de origen.
    Retorna (running_map, origin_detected).
    """
    origin = (forced_origin or "auto").strip().lower()
    if origin not in {"auto", "bdcom", "tplink"}:
        raise ValueError("Origen de running-config invalido (auto|bdcom|tplink)")

    if origin == "auto":
        origin = detect_olt_origin_from_running(file_path)

    if origin == "tplink":
        return parse_tplink_running_config(file_path), "tplink"

    return parse_bdcom_running_config(file_path), "bdcom"


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


def detect_olt_origin_from_mac_table(file_path: str) -> str:
    """
    Detecta origen de tabla MAC: bdcom | tplink.
    Default por compatibilidad: bdcom.
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read().lower()

    if re.search(r"\bgpon\d+/\d+/\d+", text) or re.search(r"\bgpon\s+\d+/\d+/\d+", text):
        return "tplink"
    if re.search(r"\bgpon0/\d+:\d+-\d+", text):
        return "bdcom"
    return "bdcom"


def parse_tplink_mac_table(file_path: str, running_map: Dict[Tuple[int, int], Dict[str, str]]):
    """
    Parser tolerant para MAC table de TP-Link.
    Estructura de retorno compatible con parser BDCOM.
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    records = []
    seen = set()

    patterns = [
        re.compile(
            r"^\s*\d+\s+([0-9A-Fa-f:.-]{12,})\s+\S+\s+gpon0/(\d+):(\d+)(?:-\d+)?\s*$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*([0-9A-Fa-f:.-]{12,})\s+\d+\s+gpon\d+/\d+/(\d+):(\d+)\s+\S+\s+\S+\s*$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*\d+\s+([0-9A-Fa-f:.-]{12,})\s+\S+\s+gpon\s+\d+/(\d+)/(\d+)(?:/\d+)?\s*$",
            re.IGNORECASE,
        ),
    ]

    fallback_pattern = re.compile(
        r"([0-9A-Fa-f:.-]{12,}).*?gpon(?:0/|\s+\d+/)(\d+)[/:](\d+)",
        re.IGNORECASE,
    )
    only_port_pattern = re.compile(
        r"^\s*([0-9A-Fa-f:.-]{12,})\s+\d+\s+gpon\d+/\d+/(\d+)\s+\S+\s+\S+\s*$",
        re.IGNORECASE,
    )

    has_tplink_port_rows_without_onu = False

    for line in text.splitlines():
        match = None
        for pattern in patterns:
            match = pattern.match(line)
            if match:
                break

        if not match:
            if only_port_pattern.match(line):
                has_tplink_port_rows_without_onu = True
            match = fallback_pattern.search(line)
            if not match:
                continue

        mac = normalize_mac(match.group(1))
        if not mac:
            continue

        pon_port = int(match.group(2))
        onu_id = int(match.group(3))
        key = (pon_port, onu_id)

        if key in seen:
            continue
        seen.add(key)

        base = running_map.get(key, {"sn": "", "ont_model": "", "ont_mode": ""})
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

    if not records and has_tplink_port_rows_without_onu:
        raise ValueError(
            "La MAC table TP-LINK no incluye ONT/ONU ID por puerto (solo GponX/Y/Z). "
            "No es posible cruzar MAC -> ONU de forma confiable con este dump. "
            "Exporta una tabla que incluya ONT/ONU ID en el puerto (ej: Gpon1/0/1:23)."
        )

    return records


def parse_mac_table_auto(
    file_path: str,
    running_map: Dict[Tuple[int, int], Dict[str, str]],
    forced_origin: Optional[str] = None,
):
    """
    Parser de MAC table con detecci├│n o forzado de origen.
    Retorna (mac_records, origin_detected).
    """
    origin = (forced_origin or "auto").strip().lower()
    if origin not in {"auto", "bdcom", "tplink"}:
        raise ValueError("Origen de MAC table invalido (auto|bdcom|tplink)")

    if origin == "auto":
        origin = detect_olt_origin_from_mac_table(file_path)

    if origin == "tplink":
        return parse_tplink_mac_table(file_path, running_map), "tplink"

    return parse_bdcom_mac_table(file_path, running_map), "bdcom"


def _extract_pppoe_user_from_tplink_wan_output(text: str) -> str:
    patterns = [
        re.compile(r"pppoe\s+username\s*[:=]\s*(\S+)", re.IGNORECASE),
        re.compile(r"username\s*[:=]\s*(\S+)", re.IGNORECASE),
        re.compile(r"user\s*name\s*[:=]\s*(\S+)", re.IGNORECASE),
        re.compile(r"account\s*[:=]\s*(\S+)", re.IGNORECASE),
    ]
    matches = []
    for line in (text or "").splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        for pattern in patterns:
            match = pattern.search(line_clean)
            if match:
                value = (match.group(1) or "").strip().strip('"').strip("'")
                if value and value not in {"-", "N/A", "none", "NONE"}:
                    matches.append(value)
    if matches:
        return matches[-1]
    return ""


def _extract_ont_mode_from_tplink_wan_output(text: str) -> str:
    has_router = False
    has_bridge = False
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line_lower = line.lower()
        if "connection type" in line_lower:
            parts = line.split(":", 1)
            value = parts[1].strip().lower() if len(parts) > 1 else ""
            if "bridge" in value:
                has_bridge = True
            if (
                "pppoe" in value
                or "dynamic" in value
                or "static" in value
                or "ipoe" in value
                or "dhcp" in value
            ):
                has_router = True

    if has_router:
        return "ROUTER"
    if has_bridge:
        return "BRIDGE"

    lower = (text or "").lower()
    if "pppoe" in lower or "route" in lower or "routing" in lower:
        return "ROUTER"
    if "bridge" in lower or "bridging" in lower:
        return "BRIDGE"
    return ""



def _parse_tplink_wan_output_bulk(text: str) -> Dict[Tuple[int, int], Dict[str, str]]:
    results: Dict[Tuple[int, int], Dict[str, str]] = {}
    current_block: List[str] = []
    current_key: Optional[Tuple[int, int]] = None
    pending_pon: Optional[str] = None

    def flush():
        nonlocal current_block, current_key, pending_pon
        if current_key and current_block:
            block_text = "\n".join(current_block)
            if current_key in results:
                block_text = results[current_key]["raw"] + "\n" + block_text
            results[current_key] = {
                "pppoe_user": _extract_pppoe_user_from_tplink_wan_output(block_text),
                "ont_mode": _extract_ont_mode_from_tplink_wan_output(block_text),
                "raw": block_text,
            }
        current_block = []
        current_key = None
        pending_pon = None

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        pon_match = re.search(r"^PON\s+ID\s*:\s*([0-9/]+)", line, re.IGNORECASE)
        if pon_match:
            flush()
            pending_pon = pon_match.group(1).strip()
            current_block = [line]
            continue

        if pending_pon:
            current_block.append(line)
            ont_match = re.search(r"^ONT\s+ID\s*:\s*(\d+)", line, re.IGNORECASE)
            if ont_match and current_key is None:
                pon_port = int(pending_pon.split("/")[-1])
                current_key = (pon_port, int(ont_match.group(1)))
            continue

    flush()
    return results


def _merge_tplink_wan_maps(
    base: Dict[Tuple[int, int], Dict[str, str]],
    extra: Dict[Tuple[int, int], Dict[str, str]],
) -> Dict[Tuple[int, int], Dict[str, str]]:
    merged = dict(base)
    for key, payload in extra.items():
        if key in merged:
            raw = merged[key].get("raw", "")
            new_raw = payload.get("raw", "")
            merged[key]["raw"] = (raw + "\n" + new_raw).strip()
            merged[key]["pppoe_user"] = payload.get("pppoe_user") or merged[key].get("pppoe_user", "")
            merged[key]["ont_mode"] = payload.get("ont_mode") or merged[key].get("ont_mode", "")
        else:
            merged[key] = payload
    return merged


def _resolve_plink_path() -> str:
    configured = getattr(config, "TPLINK_PLINK_PATH", "")
    if configured and os.path.exists(configured):
        return configured

    for candidate in ("plink.exe", "plink"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    default_path = r"C:\Program Files\PuTTY\plink.exe"
    if os.path.exists(default_path):
        return default_path

    return ""




def query_tplink_onu_pppoe_from_telnet(
    host: str,
    username: str,
    password: str,
    port: int,
    running_map: Dict[Tuple[int, int], Dict[str, str]],
    logger=None,
) -> Dict[Tuple[int, int], Dict[str, str]]:
    """
    Consulta ONU WAN info vía telnet usando select() para lectura robusta.
    Comando: show ont wan 1/0/{pon} {ont_id}
    
    Lógica:
    - Si encuentra PPPoE user en CUALQUIER WAN → ROUTER con ese user
    - Si NO encuentra PPPoE en NINGUNA WAN → BRIDGE
    - Retorna TODOS los ONTs consultados (online)
    """
    if logger:
        logger(f"[INFO] TELNET TP-LINK -> {host}:{port} user={username}")
        logger(f"[INFO] Total ONTs a consultar: {len(running_map)}")

    results: Dict[Tuple[int, int], Dict[str, str]] = {}
    consulted = 0
    with_pppoe = 0
    bridge_mode = 0
    failed = 0
    
    def read_with_timeout(tn, timeout_sec=1):
        """Lee datos disponibles sin bloquearse usando select()"""
        try:
            sock = tn.get_socket()
            if not sock:
                return b""
            readable, _, _ = select.select([sock], [], [], timeout_sec)
            if readable:
                return tn.read_very_eager()
        except:
            pass
        return b""
    
    try:
        # Conectar telnet
        tn = telnetlib.Telnet(host, port, timeout=10)
        
        # Login
        if logger:
            logger(f"[DEBUG] Esperando User prompt...")
        tn.read_until(b"User:", timeout=5)
        
        tn.write(username.encode() + b"\r\n")
        tn.read_until(b"Password:", timeout=5)
        
        tn.write(password.encode() + b"\r\n")
        tn.read_until(b">", timeout=5)
        if logger:
            logger(f"[DEBUG] Login exitoso")
        
        # Entrar en enable mode
        tn.write(b"enable\r\n")
        tn.read_until(b"#", timeout=5)
        if logger:
            logger(f"[DEBUG] Enable mode activado")
        
        # Procesar cada ONT en running_map
        for pon_port, onu_id in sorted(running_map.keys()):
            wan_cmd = f"show ont wan 1/0/{pon_port} {onu_id}"
            consulted += 1
            
            try:
                tn.write(wan_cmd.encode() + b"\r\n")
                time.sleep(0.5)
                
                # Leer respuesta con paging usando select()
                full_output = b""
                paging_count = 0
                
                for iteration in range(50):  # Max 50 iteraciones
                    chunk = read_with_timeout(tn, timeout_sec=1)
                    
                    if not chunk:
                        break
                    
                    full_output += chunk
                    
                    # Si contiene paging, presionar ENTER
                    if b"Press any key to continue" in chunk:
                        paging_count += 1
                        tn.write(b"\r\n")
                        time.sleep(0.2)
                    
                    # Si terminó (contiene prompt #), salir
                    if b"#" in chunk:
                        break
                
                wan_output = full_output.decode('utf-8', errors='ignore')
                
                # Dividir por separadores y BUSCAR EN TODAS LAS WANs
                blocks = re.split(r'-{50,}', wan_output)
                
                pppoe_user = None
                ont_mode = "BRIDGE"  # Default: BRIDGE si no hay PPPoE
                
                # Recorrer TODOS los bloques WAN para este ONT
                for block in blocks:
                    if not block.strip() or len(block) < 100:
                        continue
                    
                    # Verificar que sea del ONT correcto
                    pon_match = re.search(r'PON\s+ID\s*[:=\s]+(\d+)/(\d+)/(\d+)', block, re.IGNORECASE)
                    ont_match = re.search(r'ONT\s+ID\s*[:=\s]+(\d+)', block, re.IGNORECASE)
                    
                    if not (pon_match and ont_match):
                        continue
                    
                    extracted_pon = int(pon_match.group(3))
                    extracted_onu = int(ont_match.group(1))
                    
                    if (extracted_pon, extracted_onu) != (pon_port, onu_id):
                        continue
                    
                    # BUSCAR PPPoE user en ESTE bloque WAN
                    user_in_block = _extract_pppoe_user_from_tplink_wan_output(block)
                    if user_in_block:
                        # Encontró PPPoE en ESTA WAN → es ROUTER
                        pppoe_user = user_in_block
                        ont_mode = "ROUTER"
                        # NO hacer break, seguir buscando por si hay más
                        # pero guardaremos el primero que encuentre
                        if not results.get((pon_port, onu_id)):
                            # Primera vez que encuentra PPPoE
                            break
                
                # Guardar resultado (incluso sin PPPoE)
                results[(pon_port, onu_id)] = {
                    "pppoe_user": pppoe_user or "",  # Vacío si no hay PPPoE
                    "ont_mode": ont_mode,  # ROUTER si tiene PPPoE, BRIDGE si no
                    "raw": wan_output,
                }
                
                if pppoe_user:
                    with_pppoe += 1
                else:
                    bridge_mode += 1
                
                if logger and consulted % 5 == 0:  # Log cada 5 ONTs
                    logger(f"[PROGRESS] {consulted}/{len(running_map)} consultados, {with_pppoe} ROUTER (PPPoE), {bridge_mode} BRIDGE (sin PPPoE)")
            
            except Exception as e:
                failed += 1
                if logger and consulted % 5 == 0:
                    logger(f"[PROGRESS] {consulted}/{len(running_map)} consultados, {with_pppoe} ROUTER, {bridge_mode} BRIDGE, {failed} errores")
        
        tn.close()
        
        if logger:
            logger(f"[OK] Consulta completada: {consulted} consultados, {with_pppoe} ROUTER (PPPoE), {bridge_mode} BRIDGE, {failed} errores")
        
        return results
    
    except Exception as exc:
        if logger:
            logger(f"[ERROR] Telnet failed: {str(exc)[:200]}")
        return {}


def query_tplink_onu_pppoe_from_running(
    host: str,
    username: str,
    password: str,
    port: int,
    running_map: Dict[Tuple[int, int], Dict[str, str]],
    logger=None,
) -> Dict[Tuple[int, int], Dict[str, str]]:
    import queue
    import threading

    if logger:
        logger(f"[INFO] SSH TP-LINK (interactive plink) -> {host}:{port} user={username}")

    plink_path = _resolve_plink_path()
    if not plink_path:
        raise FileNotFoundError(f"Binario plink.exe no encontrado en: {plink_path}")

    sorted_keys = sorted(running_map.keys(), key=lambda item: (item[0], item[1]))

    # Omitir -batch explícitamente.
    cmd = [
        plink_path,
        "-ssh",
        "-t",
        "-P", str(port),
        "-l", username,
        host,
    ]
    extra_args = shlex.split(config.TPLINK_PLINK_ARGS) if config.TPLINK_PLINK_ARGS else []
    cmd = [cmd[0]] + extra_args + cmd[1:]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    password_sent = False
    shell_ready = False
    read_error = None
    results: Dict[Tuple[int, int], Dict[str, str]] = {}
    password_lock = threading.Lock()
    raw_output_parts: List[str] = []

    def _send_password() -> None:
        nonlocal password_sent, shell_ready
        with password_lock:
            if password_sent:
                return
            proc.stdin.write(password + "\r\n")
            proc.stdin.flush()
            password_sent = True
            shell_ready = True

    def _reader() -> None:
        nonlocal read_error, password_sent, shell_ready
        buffer = ""
        try:
            while True:
                chunk = proc.stdout.read(1)
                if chunk == "" or chunk is None:
                    break
                raw_output_parts.append(chunk)
                buffer += chunk
                lower_buffer = buffer.lower()
                if (not password_sent) and ("assword:" in lower_buffer or "password:" in lower_buffer):
                    if logger:
                        logger("[INFO] Prompt de password detectado; inyectando contraseña")
                    _send_password()
        except Exception as exc:
            read_error = exc

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()

    # Si plink no expone el prompt por stdout capturado, enviar la contraseña tras arrancar.
    wait_password_deadline = time.time() + 3
    while time.time() < wait_password_deadline and not password_sent:
        if proc.poll() is not None:
            break
        time.sleep(0.05)

    if not password_sent:
        if logger:
            logger("[INFO] Enviando contraseña tras espera inicial")
        _send_password()

    # LOGIN INTERCEPTOR
    login_timeout = time.time() + 30
    while time.time() < login_timeout:
        if read_error:
            raise RuntimeError(f"Error leyendo stdout de plink: {read_error}")
        if proc.poll() is not None:
            break

        if password_sent:
            break

        time.sleep(0.1)

    if not password_sent:
        try:
            proc.terminate()
        except Exception:
            pass
        raise RuntimeError("No se detectó prompt de password en plink")

    # INYECCIÓN DE COMANDOS
    command_list = ["terminal length 0"]
    for pon_port, onu_id in sorted_keys:
        command_list.append(f"show ont wan 1/0/{pon_port} {onu_id}")
    command_list.append("exit")

    for command in command_list:
        proc.stdin.write(command + "\r\n")
        proc.stdin.flush()

    try:
        proc.stdin.close()
    except Exception:
        pass

    # READING LOOP
    capture_timeout = time.time() + max(60, len(command_list) * 5)
    while time.time() < capture_timeout:
        if read_error:
            raise RuntimeError(f"Error leyendo stdout de plink: {read_error}")

        if proc.poll() is not None:
            break

        time.sleep(0.1)

    reader_thread.join(timeout=5)

    full_output = "".join(raw_output_parts)
    if logger and not shell_ready:
        logger("[WARN] No se detectó prompt shell explícito; parseando salida recibida")

    # PARSEO por cada comando emitido, usando el texto completo capturado.
    for pon_port, onu_id in sorted_keys:
        command_marker = f"show ont wan 1/0/{pon_port} {onu_id}"
        command_index = full_output.lower().find(command_marker.lower())
        if command_index >= 0:
            segment_start = command_index + len(command_marker)
            next_command_index = len(full_output)
            for next_pon, next_onu in sorted_keys:
                if (next_pon, next_onu) == (pon_port, onu_id):
                    continue
                next_marker = f"show ont wan 1/0/{next_pon} {next_onu}"
                candidate_index = full_output.lower().find(next_marker.lower(), segment_start)
                if candidate_index >= 0 and candidate_index < next_command_index:
                    next_command_index = candidate_index
            text = full_output[segment_start:next_command_index]
        else:
            text = full_output

        pon_match = re.search(r"PON\s+ID\s*:\s*(\d+)", text, re.IGNORECASE)
        ont_match = re.search(r"ONT\s+ID\s*:\s*(\d+)", text, re.IGNORECASE)

        if not (pon_match and ont_match):
            continue

        extracted_pon = int(pon_match.group(1))
        extracted_onu = int(ont_match.group(1))
        current_key = (extracted_pon, extracted_onu)
        pppoe_user = _extract_pppoe_user_from_tplink_wan_output(text)
        ont_mode = _extract_ont_mode_from_tplink_wan_output(text)
        results[current_key] = {
            "pppoe_user": pppoe_user,
            "ont_mode": ont_mode,
            "raw": text,
        }

    if not results and logger:
        logger(full_output)

    try:
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass

    return results


def build_migration_rows_from_tplink_running(
    running_map: Dict[Tuple[int, int], Dict[str, str]],
    tplink_wan_map: Dict[Tuple[int, int], Dict[str, str]],
    destination_board: str,
    destination_vendor: str = "zte",
    destination_base0: Optional[bool] = None,
):
    rows = []
    matched = 0
    bridge_counter = 1
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

    for (pon_port, onu_id), info in sorted(running_map.items(), key=lambda x: (x[0][0], x[0][1])):
        wan = tplink_wan_map.get((pon_port, onu_id), {})
        user = (wan.get("pppoe_user") or "").strip()
        ont_mode_source = (wan.get("ont_mode") or info.get("ont_mode") or "ROUTER").strip().upper()

        if not user and ont_mode_source != "BRIDGE":
            continue

        matched += 1
        source_port = f"gpon0/{pon_port}"
        pon_destino = build_pon_destino(
            source_port,
            destination_board,
            destination_vendor,
            destination_base0=destination_base0,
        )

        sn_clean = str(info.get("sn", "")).replace(":", "")
        ont_model = (info.get("ont_model") or "").strip() or TPLINK_DEFAULT_ONT_MODEL
        base_mode = ont_mode_source
        if base_mode not in {"ROUTER", "BRIDGE"}:
            base_mode = "ROUTER"

        final_mode = base_mode
        if final_mode == "ROUTER":
            stats["final_router"] += 1
        else:
            stats["final_bridge"] += 1
        stats["source_profile_fallback"] += 1

        if not user:
            user = f"migracion{bridge_counter:02d}"
            bridge_counter += 1

        rows.append(
            {
                "PON_DESTINO": pon_destino,
                "ZTE_ONU_ID": onu_id,
                "SN": sn_clean,
                "PPPoE_USER": user,
                "ONT_MODEL": ont_model,
                "ONT_MODE": final_mode,
            }
        )

    return rows, matched, stats


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


def list_mikrotik_ppp_secrets(host: str, username: str, password: str, port: int = 8728) -> List[str]:
    """
    Retorna todos los nombres de /ppp/secret del nodo MikroTik.
    """
    api = routeros_connect(
        host=host,
        username=username,
        password=password,
        port=port,
        timeout=15,
    )

    names: List[str] = []
    secret_rows = api.path("ppp", "secret").select("name")
    for row in secret_rows:
        name = str(row.get("name", "")).strip()
        if name:
            names.append(name)

    return sorted(set(names), key=lambda x: x.lower())


def delete_mikrotik_ppp_secret(host: str, username: str, password: str, secret_name: str, port: int = 8728) -> bool:
    """
    Elimina un secret por nombre en /ppp/secret.

    Retorna True si pudo eliminarlo, False si no existe.
    Lanza excepci├│n si hay error de API/conectividad o si falla el borrado.
    """
    target = str(secret_name or "").strip()
    if not target:
        raise ValueError("Nombre de secret vacio")

    api = routeros_connect(
        host=host,
        username=username,
        password=password,
        port=port,
        timeout=15,
    )

    secret_path = api.path("ppp", "secret")
    rows = list(secret_path.select(".id", "name"))
    row = next((r for r in rows if str(r.get("name", "")).strip() == target), None)
    if not row:
        return False

    secret_id = str(row.get(".id", "")).strip()
    if not secret_id:
        raise RuntimeError(f"No se pudo obtener .id para secret '{target}'")

    delete_errors: List[str] = []
    for attempt in (
        lambda: secret_path.remove(secret_id),
        lambda: secret_path.remove(id=secret_id),
        lambda: secret_path.remove(numbers=secret_id),
        lambda: secret_path.remove(**{".id": secret_id}),
    ):
        try:
            attempt()
            return True
        except Exception as exc:
            delete_errors.append(str(exc))

    raise RuntimeError(
        f"No se pudo eliminar secret '{target}' (.id={secret_id}). Errores: {' | '.join(delete_errors)}"
    )


def build_pon_destino(
    source_port: str,
    destination_board: str,
    destination_vendor: str = "zte",
    destination_base0: Optional[bool] = None,
) -> str:
    """
    Convierte puerto BDCOM (gpon0/X) a formato de destino en espejo.

        - ZTE: gpon_olt-{board}/{X}
        - Huawei: {board}/{X}

        Ajuste base 0 (resta 1 al puerto origen):
        - destination_base0=True: siempre resta 1
        - destination_base0=False: no resta
        - destination_base0=None: mantiene comportamiento legacy
            (Huawei resta 1, ZTE no resta)
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
    try:
        port_num = int(port)
    except ValueError:
        return ""

    if destination_base0 is None:
        # Compatibilidad hacia atr├ís: Huawei base 0, ZTE base 1.
        apply_base0 = vendor == "huawei"
    else:
        apply_base0 = bool(destination_base0)

    final_port = max(0, port_num - 1) if apply_base0 else port_num

    if vendor == "huawei":
        return f"{board}/{final_port}"
    return f"gpon_olt-{board}/{final_port}"


def build_migration_rows(
    mac_records: List[Dict[str, str]],
    mac_to_pppoe: Dict[str, str],
    destination_board: str,
    destination_vendor: str = "zte",
    destination_base0: Optional[bool] = None,
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
        pon_destino = build_pon_destino(
            source_port,
            destination_board,
            destination_vendor,
            destination_base0=destination_base0,
        )
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


def _safe_int(value: object, default: int = 10**9) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _pon_sort_key(pon_destino: str) -> Tuple[str, Tuple[int, ...], str]:
    value = (pon_destino or "").strip().lower()
    numbers = tuple(_safe_int(n) for n in re.findall(r"\d+", value))
    if not numbers:
        numbers = (10**9,)
    alpha = re.sub(r"\d+", "", value)
    return alpha, numbers, value


def _row_sort_key(row: Dict[str, str]) -> Tuple[str, Tuple[int, ...], str, int, str]:
    pon_destino = row.get("PON_DESTINO", "")
    onu_id = _safe_int(row.get("ZTE_ONU_ID", ""))
    sn = (row.get("SN") or "").strip().upper()
    pon_alpha, pon_numbers, pon_raw = _pon_sort_key(pon_destino)
    return pon_alpha, pon_numbers, pon_raw, onu_id, sn


def export_migration_csv(output_path: str, rows: List[Dict[str, str]]):
    fields = ["PON_DESTINO", "ZTE_ONU_ID", "SN", "PPPoE_USER", "ONT_MODEL", "ONT_MODE"]
    ordered_rows = sorted(rows, key=_row_sort_key)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(ordered_rows)
