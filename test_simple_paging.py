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

# Leer hasta encontrar paging
chunk1 = tn.read_until(b"Press any key to continue", timeout=5)
print(f"[CHUNK1] {len(chunk1)} bytes")

# Presionar 'q' para salir del paging
tn.write(b"q\r\n")
time.sleep(0.3)

# Leer el resto hasta #
try:
    chunk2 = tn.read_until(b"#", timeout=5)
    print(f"[CHUNK2] {len(chunk2)} bytes")
except:
    chunk2 = b""

full_output = (chunk1 + chunk2).decode('utf-8', errors='ignore')
print(f"\nTotal: {len(full_output)} bytes\n")

# Dividir por separadores
blocks = re.split(r'-{50,}', full_output)
print(f"Bloques: {len(blocks)}\n")

for i, block in enumerate(blocks):
    if not block.strip() or len(block) < 50:
        continue
    
    print(f"\n{'='*60}\n[BLOQUE {i}] {len(block)} bytes\n")
    
    # Buscar información
    wan_match = re.search(r'WAN\s+ID\s*[:=\s]+(\d+)', block, re.IGNORECASE)
    conn_type_match = re.search(r'Connection\s+type\s*[:=\s]+([^\n]+)', block, re.IGNORECASE)
    user_match = re.search(r'PPPoE\s+user\s+name\s*[:=\s]+(\S+)', block, re.IGNORECASE)
    
    if wan_match:
        print(f"WAN ID: {wan_match.group(1)}")
    if conn_type_match:
        print(f"Connection type: {conn_type_match.group(1).strip()}")
    if user_match:
        print(f"✓✓✓ PPPoE user: {user_match.group(1)}")
    
    # Mostrar primeras 10 líneas
    print("\nContenido:")
    for line in block.split('\n')[:10]:
        if line.strip():
            print(f"  {line}")

tn.close()
