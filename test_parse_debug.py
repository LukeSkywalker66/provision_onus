#!/usr/bin/env python3
import telnetlib
import re
import time

HOST = "138.59.175.17"
PORT = 2123

tn = telnetlib.Telnet(HOST, PORT, timeout=10)

# Login
tn.read_until(b"User:", timeout=5)
tn.write(b"admin\r\n")
tn.read_until(b"Password:", timeout=5)
tn.write(b"3190gef6\r\n")
tn.read_until(b">", timeout=5)

# Enable
tn.write(b"enable\r\n")
tn.read_until(b"#", timeout=5)

# Comando
print("Enviando: show ont wan 1/0/1 5")
tn.write(b"show ont wan 1/0/1 5\r\n")
time.sleep(0.5)

resp = tn.read_until(b"#", timeout=10)
output = resp.decode('utf-8', errors='ignore')
print(f"Output total: {len(output)} bytes\n")

# Dividir por separadores
blocks = re.split(r'\s*-{50,}\s*', output)
print(f"Bloques encontrados: {len(blocks)}\n")

for i, block in enumerate(blocks):
    if not block.strip():
        print(f"[BLOQUE {i}] Vacío")
        continue
    
    print(f"[BLOQUE {i}] {len(block)} bytes")
    
    # Buscar PON y ONT ID
    pon_match = re.search(r'PON\s+ID\s*[:\s]+(\d+)/(\d+)/(\d+)', block, re.IGNORECASE)
    ont_match = re.search(r'ONT\s+ID\s*[:\s]+(\d+)', block, re.IGNORECASE)
    
    if pon_match:
        print(f"  PON: {pon_match.group(1)}/{pon_match.group(2)}/{pon_match.group(3)}")
    else:
        print(f"  PON: NO ENCONTRADO")
    
    if ont_match:
        print(f"  ONT: {ont_match.group(1)}")
    else:
        print(f"  ONT: NO ENCONTRADO")
    
    # Buscar PPPoE user
    user_match = re.search(r'PPPoE\s+user\s+name\s*[:=\s]+(\S+)', block, re.IGNORECASE)
    if user_match:
        print(f"  PPPoE user: {user_match.group(1)}")
    else:
        print(f"  PPPoE user: NO ENCONTRADO")
    
    # Mostrar primeras 300 caracteres
    print(f"  Contenido: {block[:300]}")
    print()

tn.close()
