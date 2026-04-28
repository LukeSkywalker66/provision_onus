import re
import time
from typing import Dict, List, Tuple

import requests
from requests import exceptions as req_exc

from config import HUAWEI_INJECTION_OLT_NAME, OLT_MAP, SMARTOLT


def _short_text(value: object, max_len: int = 220) -> str:
    text = str(value or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _request_with_retry(
    method: str,
    url: str,
    headers: Dict[str, str],
    data=None,
    logger=None,
    context: str = "",
) -> Tuple[requests.Response, int, float]:
    timeout = int(SMARTOLT.get("timeout", 20))
    retries = int(SMARTOLT.get("retries", 3))
    retry_delay = float(SMARTOLT.get("retry_delay", 1.0))
    last_exc: Exception | None = None
    last_resp: requests.Response | None = None

    for attempt in range(1, max(1, retries) + 1):
        started = time.time()
        try:
            resp = requests.request(method, url, headers=headers, data=data or {}, timeout=timeout)
            elapsed_ms = (time.time() - started) * 1000.0
            last_resp = resp

            # Reintentar también en respuestas transitorias de backend/rate-limit.
            if resp.status_code in {429, 500, 502, 503, 504} and attempt < max(1, retries):
                if logger:
                    logger(
                        f"[WARN] SmartOLT {context} intento {attempt}/{retries} HTTP={resp.status_code}; reintento en {retry_delay * attempt:.1f}s"
                    )
                time.sleep(retry_delay * attempt)
                continue

            return resp, attempt, elapsed_ms
        except (req_exc.Timeout, req_exc.ConnectionError, req_exc.RequestException) as exc:
            last_exc = exc
            if attempt >= max(1, retries):
                break
            if logger:
                logger(
                    f"[WARN] SmartOLT {context} intento {attempt}/{retries} fallo: {_short_text(exc)}; reintento en {retry_delay * attempt:.1f}s"
                )
            time.sleep(retry_delay * attempt)

    if last_exc is not None:
        raise RuntimeError(f"SmartOLT {context} agotó reintentos: {_short_text(last_exc)}")
    if last_resp is not None:
        raise RuntimeError(
            f"SmartOLT {context} agotó reintentos HTTP={last_resp.status_code} resp={_short_text(last_resp.text)}"
        )
    raise RuntimeError("Fallo desconocido en request SmartOLT")


def _parse_board_port_from_pon_destino(pon_destino: str) -> Tuple[int, int]:
    value = (pon_destino or "").strip()
    m = re.match(r"^(\d+)/(\d+)/(\d+)$", value)
    if not m:
        raise ValueError(f"PON_DESTINO invalido: '{pon_destino}'")

    # Formato esperado en CSV Huawei: frame/board/port
    board = int(m.group(2))
    port = int(m.group(3))
    return board, port


def move_onu_by_external_id(onu_external_id: str, board: int, port: int, logger=None) -> Dict[str, object]:
    base_url = (SMARTOLT.get("base_url") or "").strip().rstrip("/")
    token = (SMARTOLT.get("token") or "").strip()
    olt_id = int(SMARTOLT.get("olt_id", 1))

    if not base_url:
        raise ValueError("SMARTOLT_BASEURL no configurado")
    if not token:
        raise ValueError("SMARTOLT_TOKEN no configurado")
    if not onu_external_id:
        raise ValueError("ONU external ID vacio")

    url = f"{base_url}/onu/move/{onu_external_id}"
    headers = {"X-Token": token}
    payload = {
        "olt_id": str(olt_id),
        "board": str(board),
        "port": str(port),
    }

    resp, attempts, elapsed_ms = _request_with_retry(
        "POST",
        url,
        headers=headers,
        data=payload,
        logger=logger,
        context=f"move/{onu_external_id}",
    )
    text = (resp.text or "").strip()

    result: Dict[str, object] = {
        "http_status": resp.status_code,
        "ok": False,
        "response_text": text,
        "attempts": attempts,
        "elapsed_ms": round(elapsed_ms, 1),
        "url": url,
        "payload": payload,
    }

    try:
        body = resp.json()
        result["response_json"] = body
        result["ok"] = bool(body.get("status") is True)
    except Exception:
        result["response_json"] = None

    if resp.status_code >= 400:
        result["ok"] = False

    return result


def update_onu_mode_by_external_id(onu_external_id: str, onu_mode: str, logger=None) -> Dict[str, object]:
    base_url = (SMARTOLT.get("base_url") or "").strip().rstrip("/")
    token = (SMARTOLT.get("token") or "").strip()

    if not base_url:
        raise ValueError("SMARTOLT_BASEURL no configurado")
    if not token:
        raise ValueError("SMARTOLT_TOKEN no configurado")
    if not onu_external_id:
        raise ValueError("ONU external ID vacio")

    mode_norm = (onu_mode or "").strip().lower()
    if mode_norm == "bridging":
        api_mode = "Bridging"
    elif mode_norm == "routing":
        api_mode = "Routing"
    else:
        raise ValueError("onu_mode invalido. Permitidos: Routing, Bridging")

    url = f"{base_url}/onu/update_onu_mode/{onu_external_id}"
    headers = {"X-Token": token}
    payload = {"onu_mode": api_mode}

    resp, attempts, elapsed_ms = _request_with_retry(
        "POST",
        url,
        headers=headers,
        data=payload,
        logger=logger,
        context=f"update_onu_mode/{onu_external_id}",
    )
    text = (resp.text or "").strip()

    result: Dict[str, object] = {
        "http_status": resp.status_code,
        "ok": False,
        "response_text": text,
        "attempts": attempts,
        "elapsed_ms": round(elapsed_ms, 1),
        "url": url,
        "payload": payload,
    }

    try:
        body = resp.json()
        result["response_json"] = body
        result["ok"] = bool(body.get("status") is True)
    except Exception:
        result["response_json"] = None

    if resp.status_code >= 400:
        result["ok"] = False

    return result


def _sanitize_external_id(raw: str) -> str:
    value = re.sub(r"[^0-9A-Za-z]", "", raw or "").strip()
    return value


def _normalize_onu_mode(raw_mode: str) -> str:
    mode = (raw_mode or "").strip().lower()
    if mode == "bridging" or mode == "bridge":
        return "Bridging"
    if mode == "routing" or mode == "router":
        return "Routing"
    return ""


def authorize_onu(
    *,
    onu_external_id: str,
    sn: str,
    onu_type: str,
    zone: str,
    name: str,
    onu_mode: str,
    board: int | None = None,
    port: int | None = None,
    logger=None,
    odb: str = "",
    address_or_comment: str = "",
) -> Dict[str, object]:
    base_url = (SMARTOLT.get("base_url") or "").strip().rstrip("/")
    token = (SMARTOLT.get("token") or "").strip()
    olt_id = int(SMARTOLT.get("olt_id", 1))
    pon_type = (SMARTOLT.get("authorize_pon_type") or "gpon").strip().lower()
    gpon_channel = (SMARTOLT.get("authorize_gpon_channel") or "gpon").strip().lower()
    epon_channel = (SMARTOLT.get("authorize_epon_channel") or "epon").strip().lower()
    vlan = str(SMARTOLT.get("authorize_vlan", "")).strip()
    upload_profile = (SMARTOLT.get("authorize_upload_profile") or "").strip()
    download_profile = (SMARTOLT.get("authorize_download_profile") or "").strip()

    if not base_url:
        raise ValueError("SMARTOLT_BASEURL no configurado")
    if not token:
        raise ValueError("SMARTOLT_TOKEN no configurado")
    if pon_type not in {"gpon", "epon"}:
        raise ValueError("SMARTOLT_AUTHORIZE_PON_TYPE invalido (gpon o epon)")
    if not vlan:
        raise ValueError("SMARTOLT_AUTHORIZE_VLAN no configurado")

    external_id = _sanitize_external_id(onu_external_id)
    sn_clean = _sanitize_external_id(sn)
    onu_type_clean = (onu_type or "").strip()
    zone_clean = (zone or "").strip()
    name_clean = (name or "").strip()
    mode_clean = _normalize_onu_mode(onu_mode)

    if not external_id:
        raise ValueError("onu_external_id vacio o invalido")
    if not sn_clean:
        raise ValueError("SN vacio o invalido")
    if not onu_type_clean:
        raise ValueError("onu_type vacio")
    if not zone_clean:
        raise ValueError("zone vacia")
    if not name_clean:
        raise ValueError("name vacio")
    if not mode_clean:
        raise ValueError("onu_mode invalido. Permitidos: Routing, Bridging")

    url = f"{base_url}/onu/authorize_onu"
    headers = {"X-Token": token}
    payload: Dict[str, str] = {
        "olt_id": str(olt_id),
        "pon_type": pon_type,
        "sn": sn_clean,
        "onu_type": onu_type_clean,
        "onu_mode": mode_clean,
        "vlan": vlan,
        "zone": zone_clean,
        "name": name_clean,
        "onu_external_id": external_id,
    }

    if pon_type == "gpon" and gpon_channel:
        payload["gpon_channel"] = gpon_channel
    if pon_type == "epon" and epon_channel:
        payload["epon_channel"] = epon_channel
    if board is not None:
        payload["board"] = str(board)
    if port is not None:
        payload["port"] = str(port)
    if odb:
        payload["odb"] = odb
    if address_or_comment:
        payload["address_or_comment"] = address_or_comment
    if upload_profile:
        payload["upload_speed_profile_name"] = upload_profile
    if download_profile:
        payload["download_speed_profile_name"] = download_profile

    resp, attempts, elapsed_ms = _request_with_retry(
        "POST",
        url,
        headers=headers,
        data=payload,
        logger=logger,
        context=f"authorize_onu/{external_id}",
    )
    text = (resp.text or "").strip()

    result: Dict[str, object] = {
        "http_status": resp.status_code,
        "ok": False,
        "response_text": text,
        "attempts": attempts,
        "elapsed_ms": round(elapsed_ms, 1),
        "url": url,
        "payload": payload,
    }

    try:
        body = resp.json()
        result["response_json"] = body
        result["ok"] = bool(body.get("status") is True)
    except Exception:
        result["response_json"] = None

    if resp.status_code >= 400:
        result["ok"] = False

    return result


def delete_onu_by_external_id(onu_external_id: str, logger=None) -> Dict[str, object]:
    base_url = (SMARTOLT.get("base_url") or "").strip().rstrip("/")
    token = (SMARTOLT.get("token") or "").strip()

    if not base_url:
        raise ValueError("SMARTOLT_BASEURL no configurado")
    if not token:
        raise ValueError("SMARTOLT_TOKEN no configurado")

    external_id = _sanitize_external_id(onu_external_id)
    if not external_id:
        raise ValueError("ONU external ID vacio o invalido")

    url = f"{base_url}/onu/delete/{external_id}"
    headers = {"X-Token": token}

    resp, attempts, elapsed_ms = _request_with_retry(
        "POST",
        url,
        headers=headers,
        data={},
        logger=logger,
        context=f"delete_onu/{external_id}",
    )
    text = (resp.text or "").strip()

    result: Dict[str, object] = {
        "http_status": resp.status_code,
        "ok": False,
        "response_text": text,
        "attempts": attempts,
        "elapsed_ms": round(elapsed_ms, 1),
        "url": url,
    }

    try:
        body = resp.json()
        result["response_json"] = body
        result["ok"] = bool(body.get("status") is True)
    except Exception:
        result["response_json"] = None

    if resp.status_code >= 400:
        result["ok"] = False

    return result


def _normalized_row_lookup(row: Dict[str, str]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for key, value in row.items():
        norm = re.sub(r"[^a-z0-9]", "", str(key or "").strip().lower())
        if norm and norm not in lookup:
            lookup[norm] = str(value or "").strip()
    return lookup


def _extract_external_id_from_row(row: Dict[str, str]) -> str:
    external_id, _source = _extract_external_id_with_source_from_row(row)
    return external_id


def _extract_external_id_with_source_from_row(row: Dict[str, str]) -> Tuple[str, str]:
    lookup = _normalized_row_lookup(row)
    external_id_candidates = [
        "onuexternalid",
        "onuuniqueexternalid",
        "uniqueexternalid",
        "externalid",
        "onuid",
    ]
    for key in external_id_candidates:
        value = lookup.get(key, "")
        cleaned = _sanitize_external_id(value)
        if cleaned:
            return cleaned, key

    sn_candidates = [
        "sn",
        "serial",
        "serialnumber",
        "onuserial",
        "onuserialnumber",
    ]
    for key in sn_candidates:
        value = lookup.get(key, "")
        cleaned = _sanitize_external_id(value)
        if cleaned:
            return cleaned, f"fallback:{key}"
    return "", ""


def get_olts_list() -> Dict[str, object]:
    base_url = (SMARTOLT.get("base_url") or "").strip().rstrip("/")
    token = (SMARTOLT.get("token") or "").strip()

    if not base_url:
        raise ValueError("SMARTOLT_BASEURL no configurado")
    if not token:
        raise ValueError("SMARTOLT_TOKEN no configurado")

    url = f"{base_url}/system/get_olts"
    headers = {"X-Token": token}
    resp, attempts, elapsed_ms = _request_with_retry("GET", url, headers=headers, context="get_olts")
    payload = resp.json()

    return {
        "http_status": resp.status_code,
        "status": payload.get("status"),
        "response": payload.get("response", []),
        "attempts": attempts,
        "elapsed_ms": round(elapsed_ms, 1),
    }


def _precheck_target_olt(logger):
    configured_id = str(SMARTOLT.get("olt_id", 1)).strip()
    expected_name = (HUAWEI_INJECTION_OLT_NAME or "").strip()
    expected_ip = str(OLT_MAP.get(expected_name, {}).get("ip", "")).strip()

    logger(
        "[INFO] SmartOLT precheck -> "
        f"base_url={SMARTOLT.get('base_url')} olt_id={configured_id} expected_name={expected_name}"
    )

    data = get_olts_list()
    if int(data.get("http_status", 500)) >= 400 or not data.get("status"):
        raise RuntimeError(
            f"No se pudo consultar OLTs en SmartOLT (HTTP={data.get('http_status')})."
        )

    olts = data.get("response", [])
    selected = next((o for o in olts if str(o.get("id", "")).strip() == configured_id), None)

    if not selected:
        raise RuntimeError(
            f"SMARTOLT_OLT_ID={configured_id} no existe en /system/get_olts"
        )

    selected_name = str(selected.get("name", "")).strip()
    selected_ip = str(selected.get("ip", "")).strip()
    logger(
        f"[INFO] SmartOLT OLT seleccionada -> id={configured_id} name={selected_name} ip={selected_ip} (get_olts intentos={data.get('attempts')} t={data.get('elapsed_ms')}ms)"
    )

    if expected_name and selected_name != expected_name:
        raise RuntimeError(
            "OLT ID de SmartOLT no coincide con la OLT objetivo de inyeccion: "
            f"esperada '{expected_name}' vs seleccionada '{selected_name}'."
        )
    if expected_ip and selected_ip != expected_ip:
        raise RuntimeError(
            "IP de OLT en SmartOLT no coincide con la configurada para la inyeccion: "
            f"esperada '{expected_ip}' vs seleccionada '{selected_ip}'."
        )


def move_onus_from_csv_rows(rows: List[Dict[str, str]], logger, dry_run: bool = False) -> Dict[str, int]:
    total = len(rows)
    ok = 0
    error = 0
    failures: List[str] = []
    started_total = time.time()

    logger(f"[INFO] SmartOLT move: total ONUs a procesar = {total}")

    # Validacion previa obligatoria para evitar mover sobre OLT incorrecta.
    _precheck_target_olt(logger)

    if dry_run:
        logger("[WARN] SmartOLT move en DRY-RUN: no se enviaran requests")

    move_delay = float(SMARTOLT.get("move_delay", 0.2))

    for index, row in enumerate(rows, start=1):
        sn = (row.get("SN") or "").replace(":", "").strip()
        pon_destino = (row.get("PON_DESTINO") or "").strip()
        pppoe_user = (row.get("PPPoE_USER") or "").strip()

        logger(
            f"[INFO] [SMARTOLT][{index}/{total}] SN={sn} user={pppoe_user} destino={pon_destino}"
        )

        try:
            board, port = _parse_board_port_from_pon_destino(pon_destino)
        except Exception as exc:
            msg = f"SN={sn} user={pppoe_user} parse_destino={_short_text(exc)}"
            logger(f"[ERROR] SmartOLT move {msg}")
            failures.append(msg)
            error += 1
            continue

        if dry_run:
            logger(
                f"[INFO] [SIMULACION][SMARTOLT] move SN={sn} -> olt_id={SMARTOLT.get('olt_id', 1)} board={board} port={port}"
            )
            ok += 1
            continue

        try:
            result = move_onu_by_external_id(sn, board, port, logger=logger)
            if result.get("ok"):
                logger(
                    "[OK] SmartOLT move "
                    f"SN={sn} user={pppoe_user} -> board={board} port={port} "
                    f"HTTP={result.get('http_status')} intentos={result.get('attempts')} t={result.get('elapsed_ms')}ms"
                )
                ok += 1
            else:
                msg = (
                    f"SN={sn} user={pppoe_user} HTTP={result.get('http_status')} "
                    f"intentos={result.get('attempts')} t={result.get('elapsed_ms')}ms "
                    f"resp={_short_text(result.get('response_text'))}"
                )
                logger(f"[ERROR] SmartOLT move {msg}")
                failures.append(msg)
                error += 1
        except Exception as exc:
            msg = f"SN={sn} user={pppoe_user} exception={_short_text(exc)}"
            logger(f"[ERROR] SmartOLT move {msg}")
            failures.append(msg)
            error += 1

        if move_delay > 0:
            time.sleep(move_delay)

    elapsed_total = round(time.time() - started_total, 2)
    logger(
        f"[INFO] SmartOLT move resumen: OK={ok} ERROR={error} TOTAL={total} TIEMPO={elapsed_total}s"
    )
    if failures:
        logger(f"[WARN] SmartOLT fallas detalladas ({len(failures)}):")
        for idx, item in enumerate(failures, start=1):
            logger(f"[WARN] [{idx}] {item}")

    return {"ok": ok, "error": error, "total": total}


def update_bridge_mode_from_csv_rows(rows: List[Dict[str, str]], logger, dry_run: bool = False) -> Dict[str, int]:
    bridge_rows = [
        row
        for row in rows
        if (row.get("ONT_MODE") or "").strip().upper() == "BRIDGE"
    ]

    total = len(bridge_rows)
    ok = 0
    error = 0
    skipped = len(rows) - len(bridge_rows)
    failures: List[str] = []
    started_total = time.time()

    logger(
        f"[INFO] SmartOLT mode update: total filas={len(rows)} BRIDGE={total} omitidas_no_bridge={skipped}"
    )

    if total == 0:
        logger("[WARN] No hay filas BRIDGE en el CSV; no hay cambios para enviar")
        return {"ok": 0, "error": 0, "total": 0, "skipped": skipped}

    # Mismo guard-rail operacional del flujo move.
    _precheck_target_olt(logger)

    if dry_run:
        logger("[WARN] SmartOLT mode update en DRY-RUN: no se enviaran requests")

    mode_delay = float(SMARTOLT.get("mode_update_delay", SMARTOLT.get("move_delay", 0.2)))

    for index, row in enumerate(bridge_rows, start=1):
        sn = (row.get("SN") or "").replace(":", "").strip()
        pppoe_user = (row.get("PPPoE_USER") or "").strip()

        logger(f"[INFO] [SMARTOLT-MODE][{index}/{total}] SN={sn} user={pppoe_user} target_mode=Bridging")

        if not sn:
            msg = f"SN vacio user={pppoe_user}"
            logger(f"[ERROR] SmartOLT mode update {msg}")
            failures.append(msg)
            error += 1
            continue

        if dry_run:
            logger(f"[INFO] [SIMULACION][SMARTOLT-MODE] update SN={sn} onu_mode=Bridging")
            ok += 1
            continue

        try:
            result = update_onu_mode_by_external_id(sn, "Bridging", logger=logger)
            if result.get("ok"):
                logger(
                    "[OK] SmartOLT mode update "
                    f"SN={sn} user={pppoe_user} -> Bridging "
                    f"HTTP={result.get('http_status')} intentos={result.get('attempts')} t={result.get('elapsed_ms')}ms"
                )
                ok += 1
            else:
                msg = (
                    f"SN={sn} user={pppoe_user} HTTP={result.get('http_status')} "
                    f"intentos={result.get('attempts')} t={result.get('elapsed_ms')}ms "
                    f"resp={_short_text(result.get('response_text'))}"
                )
                logger(f"[ERROR] SmartOLT mode update {msg}")
                failures.append(msg)
                error += 1
        except Exception as exc:
            msg = f"SN={sn} user={pppoe_user} exception={_short_text(exc)}"
            logger(f"[ERROR] SmartOLT mode update {msg}")
            failures.append(msg)
            error += 1

        if mode_delay > 0:
            time.sleep(mode_delay)

    elapsed_total = round(time.time() - started_total, 2)
    logger(
        f"[INFO] SmartOLT mode update resumen: OK={ok} ERROR={error} TOTAL_BRIDGE={total} OMITIDAS_NO_BRIDGE={skipped} TIEMPO={elapsed_total}s"
    )
    if failures:
        logger(f"[WARN] SmartOLT mode update fallas detalladas ({len(failures)}):")
        for idx, item in enumerate(failures, start=1):
            logger(f"[WARN] [{idx}] {item}")

    return {"ok": ok, "error": error, "total": total, "skipped": skipped}


def authorize_onus_from_csv_rows(rows: List[Dict[str, str]], logger, dry_run: bool = False) -> Dict[str, int]:
    total = len(rows)
    ok = 0
    error = 0
    failures: List[str] = []
    started_total = time.time()

    zone = (SMARTOLT.get("authorize_zone") or "").strip()
    odb = (SMARTOLT.get("authorize_odb") or "").strip()
    address = (SMARTOLT.get("authorize_address") or "").strip()
    allow_without_board_port = bool(SMARTOLT.get("authorize_allow_without_board_port", False))
    default_mode = _normalize_onu_mode(str(SMARTOLT.get("authorize_default_mode", "Routing"))) or "Routing"

    logger(f"[INFO] SmartOLT authorize: total ONUs a procesar = {total}")

    if not zone:
        raise ValueError("SMARTOLT_AUTHORIZE_ZONE no configurado")

    _precheck_target_olt(logger)

    if dry_run:
        logger("[WARN] SmartOLT authorize en DRY-RUN: no se enviaran requests")

    authorize_delay = float(SMARTOLT.get("authorize_delay", SMARTOLT.get("move_delay", 0.2)))

    for index, row in enumerate(rows, start=1):
        sn = _sanitize_external_id(row.get("SN") or "")
        pppoe_user = (row.get("PPPoE_USER") or "").strip()
        pon_destino = (row.get("PON_DESTINO") or "").strip()
        onu_type = (row.get("ONT_MODEL") or "").strip()
        row_mode = _normalize_onu_mode(row.get("ONT_MODE") or "") or default_mode
        external_id = sn
        name = pppoe_user or f"ONU-{sn[-6:]}"

        logger(
            f"[INFO] [SMARTOLT-AUTH][{index}/{total}] SN={sn} user={pppoe_user} destino={pon_destino} mode={row_mode}"
        )

        board: int | None = None
        port: int | None = None
        if pon_destino:
            try:
                board, port = _parse_board_port_from_pon_destino(pon_destino)
            except Exception as exc:
                if allow_without_board_port:
                    logger(
                        f"[WARN] SmartOLT authorize SN={sn} sin board/port por parse_destino={_short_text(exc)}"
                    )
                else:
                    msg = f"SN={sn} user={pppoe_user} parse_destino={_short_text(exc)}"
                    logger(f"[ERROR] SmartOLT authorize {msg}")
                    failures.append(msg)
                    error += 1
                    continue

        if not sn or not onu_type:
            msg = f"SN/ONT_MODEL faltante SN={sn} user={pppoe_user}"
            logger(f"[ERROR] SmartOLT authorize {msg}")
            failures.append(msg)
            error += 1
            continue

        if dry_run:
            logger(
                "[INFO] [SIMULACION][SMARTOLT-AUTH] "
                f"authorize SN={sn} external_id={external_id} type={onu_type} mode={row_mode} "
                f"board={board if board is not None else '-'} port={port if port is not None else '-'}"
            )
            ok += 1
            continue

        try:
            result = authorize_onu(
                onu_external_id=external_id,
                sn=sn,
                onu_type=onu_type,
                zone=zone,
                name=name,
                onu_mode=row_mode,
                board=board,
                port=port,
                logger=logger,
                odb=odb,
                address_or_comment=address,
            )
            if result.get("ok"):
                logger(
                    "[OK] SmartOLT authorize "
                    f"SN={sn} user={pppoe_user} HTTP={result.get('http_status')} "
                    f"intentos={result.get('attempts')} t={result.get('elapsed_ms')}ms"
                )
                ok += 1
            else:
                msg = (
                    f"SN={sn} user={pppoe_user} HTTP={result.get('http_status')} "
                    f"intentos={result.get('attempts')} t={result.get('elapsed_ms')}ms "
                    f"resp={_short_text(result.get('response_text'))}"
                )
                logger(f"[ERROR] SmartOLT authorize {msg}")
                failures.append(msg)
                error += 1
        except Exception as exc:
            msg = f"SN={sn} user={pppoe_user} exception={_short_text(exc)}"
            logger(f"[ERROR] SmartOLT authorize {msg}")
            failures.append(msg)
            error += 1

        if authorize_delay > 0:
            time.sleep(authorize_delay)

    elapsed_total = round(time.time() - started_total, 2)
    logger(
        f"[INFO] SmartOLT authorize resumen: OK={ok} ERROR={error} TOTAL={total} TIEMPO={elapsed_total}s"
    )
    if failures:
        logger(f"[WARN] SmartOLT authorize fallas detalladas ({len(failures)}):")
        for idx, item in enumerate(failures, start=1):
            logger(f"[WARN] [{idx}] {item}")

    return {"ok": ok, "error": error, "total": total}


def delete_onus_from_csv_rows(rows: List[Dict[str, str]], logger, dry_run: bool = False) -> Dict[str, int]:
    total_input = len(rows)
    ok = 0
    error = 0
    failures: List[str] = []
    started_total = time.time()

    prepared_rows: List[Tuple[str, str]] = []
    seen_external_ids: set[str] = set()
    skipped_duplicates = 0

    for row in rows:
        external_id, source = _extract_external_id_with_source_from_row(row)
        pppoe_user = (
            (row.get("PPPoE_USER") or "").strip()
            or (row.get("Name") or "").strip()
            or (row.get("name") or "").strip()
        )

        if external_id and source.startswith("fallback:"):
            logger(
                f"[WARN] SmartOLT delete usando fallback a SN external_id={external_id} user={pppoe_user} source={source}"
            )

        if external_id and external_id in seen_external_ids:
            skipped_duplicates += 1
            logger(
                f"[WARN] SmartOLT delete duplicado omitido external_id={external_id} user={pppoe_user}"
            )
            continue

        if external_id:
            seen_external_ids.add(external_id)
        prepared_rows.append((external_id, pppoe_user))

    total = len(prepared_rows)
    logger(
        f"[INFO] SmartOLT delete: filas_entrada={total_input} filas_a_procesar={total} duplicados_omitidos={skipped_duplicates}"
    )

    _precheck_target_olt(logger)

    if dry_run:
        logger("[WARN] SmartOLT delete en DRY-RUN: no se enviaran requests")

    delete_delay = float(SMARTOLT.get("delete_delay", SMARTOLT.get("move_delay", 0.2)))

    for index, (external_id, pppoe_user) in enumerate(prepared_rows, start=1):

        logger(f"[INFO] [SMARTOLT-DELETE][{index}/{total}] external_id={external_id} user={pppoe_user}")

        if not external_id:
            msg = f"external_id vacio user={pppoe_user}"
            logger(f"[ERROR] SmartOLT delete {msg}")
            failures.append(msg)
            error += 1
            continue

        if dry_run:
            logger(f"[INFO] [SIMULACION][SMARTOLT-DELETE] delete external_id={external_id}")
            ok += 1
            continue

        try:
            result = delete_onu_by_external_id(external_id, logger=logger)
            if result.get("ok"):
                logger(
                    "[OK] SmartOLT delete "
                    f"external_id={external_id} user={pppoe_user} "
                    f"HTTP={result.get('http_status')} intentos={result.get('attempts')} t={result.get('elapsed_ms')}ms"
                )
                ok += 1
            else:
                msg = (
                    f"external_id={external_id} user={pppoe_user} HTTP={result.get('http_status')} "
                    f"intentos={result.get('attempts')} t={result.get('elapsed_ms')}ms "
                    f"resp={_short_text(result.get('response_text'))}"
                )
                logger(f"[ERROR] SmartOLT delete {msg}")
                failures.append(msg)
                error += 1
        except Exception as exc:
            msg = f"external_id={external_id} user={pppoe_user} exception={_short_text(exc)}"
            logger(f"[ERROR] SmartOLT delete {msg}")
            failures.append(msg)
            error += 1

        if delete_delay > 0:
            time.sleep(delete_delay)

    elapsed_total = round(time.time() - started_total, 2)
    logger(f"[INFO] SmartOLT delete resumen: OK={ok} ERROR={error} TOTAL={total} TIEMPO={elapsed_total}s")
    if failures:
        logger(f"[WARN] SmartOLT delete fallas detalladas ({len(failures)}):")
        for idx, item in enumerate(failures, start=1):
            logger(f"[WARN] [{idx}] {item}")

    return {
        "ok": ok,
        "error": error,
        "total": total,
        "total_input": total_input,
        "duplicates_skipped": skipped_duplicates,
    }
