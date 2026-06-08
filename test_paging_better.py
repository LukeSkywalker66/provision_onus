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

# Leer respuesta completa, manejando paging
full_output = ""
max_attempts = 20
attempt = 0

while attempt < max_attempts:
    attempt += 1
    try:
        # Intentar leer hasta paging o #
        chunk = tn.read_until(b"Press any key to continue (Q to quit)", timeout=1)
        full_output += chunk.decode('utf-8', errors='ignore')
        print(f"[CHUNK {attempt}] {len(chunk)} bytes, encontrado paging")
        
        # Enviar 'q' para continuar
        tn.write(b"q\r\n")
        time.sleep(0.2)
    except:
        # Intentar leer lo que queda hasta #
        try:
            final = tn.read_until(b"#", timeout=1)
            final_str = final.decode('utf-8', errors='ignore')
            # Filtrar la salida de 'q' si la hay
            if final_str.startswith("q"):
                final_str = final_str[1:]
            full_output += final_str
            print(f"[FINAL {attempt}] {len(final)} bytes")
            break
        except:
            print(f"[TIMEOUT {attempt}]")
            break

output = full_output
print(f"\nOutput total: {len(output)} bytes\n")

# Dividir por separadores y parsear
blocks = re.split(r'\s*-{50,}\s*', output)
print(f"Bloques encontrados: {len(blocks)}\n")

for i, block in enumerate(blocks):
    if not block.strip() or "show ont wan" in block.lower():
        continue
    
    print(f"\n[BLOQUE {i}]")
    
    # Buscar WAN ID, Connection type, PPPoE user
    wan_match = re.search(r'WAN\s+ID\s*[:=\s]+(\d+)', block, re.IGNORECASE)
    conn_type_match = re.search(r'Connection\s+type\s*[:=\s]+(\S+)', block, re.IGNORECASE)
    user_match = re.search(r'PPPoE\s+user\s+name\s*[:=\s]+(\S+)', block, re.IGNORECASE)
    
    if wan_match:
        print(f"  WAN ID: {wan_match.group(1)}")
    if conn_type_match:
        print(f"  Connection type: {conn_type_match.group(1)}")
    if user_match:
        print(f"  PPPoE user: {user_match.group(1)}")
        print(f"  ✓✓✓ ENCONTRADO PPPoE!")
    
    # Primeras líneas
    lines = block.split('\n')[:5]
    for line in lines:
        if line.strip():
            print(f"    {line}")

tn.close()
