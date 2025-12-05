import pandas as pd

REQUIRED = ["OLT", "Board", "Port", "Allocated ONU", "Service port VLAN"]
OPTIONAL = ["Onu Type", "Name"]

def parse_smartolt_csv(path):
    df = pd.read_csv(path)
    for col in REQUIRED:
        if col not in df.columns:
            raise ValueError(f"Falta columna requerida en CSV: {col}")

    # Normaliza tipos y retorna una lista de dicts “limpios”
    records = []
    for _, row in df.iterrows():
        try:
            rec = {
                "olt_name": str(row["OLT"]).strip(),
                "slot": int(row["Board"]),
                "port": int(row["Port"]),
                "onu_id": int(row["Allocated ONU"]),
                "onu_type": str(row.get("Onu Type", "") or ""),
                "pppoe_user": str(row.get("Name", "") or ""),
                "vlan": int(row["Service port VLAN"]),
            }
            records.append(rec)
        except Exception:
            # Salta filas corruptas o incompletas
            continue
    return records
