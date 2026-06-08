#!/usr/bin/env python3
import telnetlib
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

# Enviar comando
print("Enviando: show ont wan 1/0/1")
tn.write(b"show ont wan 1/0/1\r\n")
time.sleep(0.5)

# Leer TODA la respuesta disponible
output = b""
tn.timeout = 2
try:
    while True:
        chunk = tn.recv(4096)
        if not chunk:
            break
        output += chunk
        print(f"[RX] {len(chunk)} bytes")
except:
    pass
tn.timeout = None

print(f"\n=== TOTAL: {len(output)} bytes ===")
print(output.decode('utf-8', errors='ignore'))

tn.close()
