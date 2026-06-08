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

# Leer todo con manejo de paging (presionar ENTER en lugar de 'q')
full_output = b""
for i in range(50):  # Máximo 50 iteraciones para evitar loop infinito
    try:
        # Intentar leer hasta paging o #
        chunk = tn.read_until(b"Press any key to continue", timeout=1)
        full_output += chunk
        print(f"[CHUNK {i+1}] {len(chunk)} bytes")
        
        # Presionar ENTER para continuar (no 'q')
        tn.write(b"\r\n")
        time.sleep(0.2)
    except:
        # Leer lo que queda
        try:
            final = tn.read_until(b"#", timeout=1)
            full_output += final
            print(f"[FINAL] {len(final)} bytes")
        except:
            pass
        break

output = full_output.decode('utf-8', errors='ignore')
print(f"\nTotal: {len(output)} bytes\n")

# Dividir por separadores y mostrar
blocks = re.split(r'-{50,}', output)
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
    
    # Primeras líneas
    for line in block.split('\n')[:8]:
        if line.strip():
            print(f"  {line}")

tn.close()
