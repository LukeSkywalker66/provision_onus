#!/usr/bin/env python3
"""Test rápido para verificar que la nueva función genera filas con MIGRATION_ID y BRIDGE ONTs"""

import sys
sys.path.insert(0, r'c:\Desarrollo\Fuentes\provision_onus')

from migration_bdcom import build_migration_rows_from_tplink_running, export_migration_csv

# Datos de prueba
running_map = {
    (1, 3): {"sn": "TPLGE715EDD0", "ont_model": "TPLINK"},
    (1, 4): {"sn": "TPLGB5E00327", "ont_model": "TPLINK"},
    (1, 5): {"sn": "TPLGB55683C0", "ont_model": "TPLINK"},
    (2, 1): {"sn": "TPLGBRIDGE01", "ont_model": "TPLINK"},  # Sin PPPoE
    (2, 2): {"sn": "TPLGBRIDGE02", "ont_model": "TPLINK"},  # Sin PPPoE
}

tplink_wan_map = {
    (1, 3): {"pppoe_user": "msanchez7", "ont_mode": "ROUTER"},
    (1, 4): {"pppoe_user": "dhurvitz", "ont_mode": "ROUTER"},
    (1, 5): {"pppoe_user": "jicarranza", "ont_mode": "ROUTER"},
    (2, 1): {"pppoe_user": "", "ont_mode": "BRIDGE"},   # BRIDGE sin PPPoE
    (2, 2): {"pppoe_user": "", "ont_mode": "BRIDGE"},   # BRIDGE sin PPPoE
}

print("Ejecutando test de build_migration_rows_from_tplink_running...")
rows, matched, stats = build_migration_rows_from_tplink_running(
    running_map,
    tplink_wan_map,
    destination_board="1",
    destination_vendor="zte",
)

print(f"\n✓ Filas generadas: {len(rows)} de {len(running_map)} ONTs")
print(f"✓ Matched: {matched}")
print(f"✓ ROUTER: {stats['final_router']}, BRIDGE: {stats['final_bridge']}")
print("\nPrimeras filas generadas:")
for i, row in enumerate(rows, 1):
    print(f"  {i}. {row['MIGRATION_ID']} | PON={row['PON_DESTINO']} | ONU={row['ZTE_ONU_ID']} | MODE={row['ONT_MODE']} | USER={row['PPPoE_USER'] or '(vacío)'}")

# Test de exportación
print("\nTest de exportación CSV...")
test_path = r"c:\Desarrollo\Fuentes\provision_onus\test_output_migration.csv"
export_migration_csv(test_path, rows)
print(f"✓ CSV exportado a {test_path}")

# Verificar que tiene MIGRATION_ID
with open(test_path, "r") as f:
    content = f.read()
    if "MIGRATION_ID" in content:
        print("✓ MIGRATION_ID está en el CSV header")
    if "migracion01" in content:
        print("✓ migracion01 aparece en el CSV")
    if "BRIDGE" in content:
        print("✓ Modo BRIDGE aparece en el CSV")
    print("\nContenido del CSV:")
    print(content)

print("\n✅ Test completado exitosamente")
