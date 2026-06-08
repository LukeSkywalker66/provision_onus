#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test: Simular múltiples ONTs - algunos con PPPoE, otros sin (BRIDGE)
"""

from migration_bdcom import query_tplink_onu_pppoe_from_telnet
from config import OLT_MAP

def test_multi_onts():
    """Test con múltiples ONTs para verificar ROUTER vs BRIDGE"""
    
    print("\n" + "="*60)
    print("TEST MULTI-ONTs: ROUTER (PPPoE) + BRIDGE (sin PPPoE)")
    print("="*60)
    
    cfg = OLT_MAP['TpLink_villadolores']
    
    # Simular varios ONTs (solo testearemos con uno real, el 1/5, 
    # pero el real debería iterar por todos)
    running_map = {
        (1, 5): {'sn': 'GPON0001', 'ont_model': 'ZTE', 'ont_mode': 'GPON'},
        # En producción habría muchos más
    }
    
    print(f"\n[INPUT] Consultando {len(running_map)} ONT(s)...")
    
    result = query_tplink_onu_pppoe_from_telnet(
        host=cfg['ip'],
        username=cfg['user'],
        password=cfg['password'],
        port=2123,
        running_map=running_map,
        logger=print
    )
    
    print(f"\n[RESULTADO] {len(result)} ONTs retornados:")
    
    router_count = 0
    bridge_count = 0
    
    for key, value in result.items():
        pon, ont = key
        mode = value.get('ont_mode', '?')
        user = value.get('pppoe_user', 'N/A')
        
        if mode == "ROUTER":
            router_count += 1
            status = f"✓ ROUTER (user={user})"
        elif mode == "BRIDGE":
            bridge_count += 1
            status = "  BRIDGE (sin PPPoE)"
        else:
            status = f"? {mode}"
        
        print(f"  PON={pon} ONT={ont}: {status}")
    
    print(f"\n[SUMMARY]")
    print(f"  ROUTER (PPPoE): {router_count}")
    print(f"  BRIDGE (sin PPPoE): {bridge_count}")
    print(f"  Total: {router_count + bridge_count}")
    
    assert len(result) == len(running_map), f"Expected {len(running_map)} results, got {len(result)}"
    assert result[(1, 5)]['ont_mode'] in ['ROUTER', 'BRIDGE'], "Mode debe ser ROUTER o BRIDGE"
    
    print("\n✓✓✓ TEST PASSED")
    print("="*60)

if __name__ == "__main__":
    test_multi_onts()
