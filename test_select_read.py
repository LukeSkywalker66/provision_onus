#!/usr/bin/env python3
"""Test para validar lectura con select"""

import telnetlib
import select
import time
import socket

HOST = "138.59.175.17"
PORT = 2123

def read_with_timeout(tn, timeout=1):
    """Lee datos disponibles sin bloquearse"""
    sock = tn.get_socket()
    if sock:
        readable, _, _ = select.select([sock], [], [], timeout)
        if readable:
            try:
                return tn.read_very_eager()
            except:
                return b""
    return b""

# Conectar
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

# Leer con select
full_output = b""
paging_count = 0

for iteration in range(50):
    # Leer lo que esté disponible
    chunk = read_with_timeout(tn, timeout=1)
    
    if not chunk:
        print(f"[Iteration {iteration}] No data, breaking")
        break
    
    print(f"[Iteration {iteration}] {len(chunk)} bytes")
    full_output += chunk
    
    # Si contiene el prompt de paging, presionar ENTER
    if b"Press any key to continue" in chunk:
        paging_count += 1
        print(f"  -> Paging prompt detected, pressing ENTER (count: {paging_count})")
        tn.write(b"\r\n")
        time.sleep(0.2)
    
    # Si contiene el prompt #, salir
    if b"#" in chunk or b"DS-P7001" in chunk:
        print(f"  -> Command prompt detected, done")
        break

print(f"\nTotal: {len(full_output)} bytes")
print(f"Paging prompts: {paging_count}")
print(f"\n=== Output Preview (first 500 chars) ===")
print(full_output.decode('utf-8', errors='ignore')[:500])

tn.close()
