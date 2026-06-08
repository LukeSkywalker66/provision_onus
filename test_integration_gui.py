#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test de integración: Simular llamada desde GUI migration_ui.py
"""

from migration_bdcom import query_tplink_onu_pppoe_from_telnet
from config import OLT_MAP
import json

def test_gui_call():
    """Simula la llamada desde migration_ui.py línea 244-253"""
    
    print("\n" + "="*60)
    print("TEST INTEGRACIÓN GUI -> migration_bdcom")
    print("="*60)
    
    # Obtener config de OLT
    cfg = OLT_MAP['TpLink_villadolores']
    print(f"\n[CONFIG] OLT IP: {cfg['ip']}")
    print(f"[CONFIG] OLT User: {cfg['user']}")
    
    # Simular running_map con ONTs
    running_map = {
        (1, 5): {
            'sn': 'GPON000012345678',
            'ont_model': 'ZTE F660',
            'ont_mode': 'GPON'
        }
    }
    
    print(f"\n[INPUT] running_map: {running_map}")
    
    # Llamar función (como lo haría migration_ui.py)
    print(f"\n[CALL] query_tplink_onu_pppoe_from_telnet()")
    print(f"       host={cfg['ip']}, port=2123, user={cfg['user']}")
    
    result = query_tplink_onu_pppoe_from_telnet(
        host=cfg['ip'],
        username=cfg['user'],
        password=cfg['password'],
        port=2123,
        running_map=running_map,
        logger=print
    )
    
    print(f"\n[RESULT] Retornó {len(result)} ONT(s):")
    for key, value in result.items():
        pon, ont = key
        print(f"\n  PON={pon} ONT={ont}:")
        print(f"    - pppoe_user: {value.get('pppoe_user', 'N/A')}")
        print(f"    - ont_mode: {value.get('ont_mode', 'N/A')}")
        print(f"    - raw bytes: {len(value.get('raw', ''))} bytes")
    
    # Verificar que coincida con expected
    assert (1, 5) in result, "ONT (1, 5) not found in result"
    assert result[(1, 5)]['pppoe_user'] == 'jicarranza', f"Expected user=jicarranza, got {result[(1, 5)]['pppoe_user']}"
    assert result[(1, 5)]['ont_mode'] == 'ROUTER', f"Expected mode=ROUTER, got {result[(1, 5)]['ont_mode']}"
    
    print("\n✓✓✓ TEST PASSED - Integración GUI-migration_bdcom correcta")
    print("="*60)

if __name__ == "__main__":
    test_gui_call()
