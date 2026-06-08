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
prompt_resp = tn.read_until(b">", timeout=5)
print(f"[LOGIN] Login response: {len(prompt_resp)} bytes")

# Enable
tn.write(b"enable\r\n")
enable_resp = tn.read_until(b"#", timeout=5)
print(f"[ENABLE] Enable response: {len(enable_resp)} bytes")

# Enviar comando y esperar
print("\nEnviando: show ont wan 1/0/1")
tn.write(b"show ont wan 1/0/1\r\n")
time.sleep(0.5)

# Intentar leer hasta #
try:
    resp = tn.read_until(b"#", timeout=10)
    print(f"[OK] Got response: {len(resp)} bytes")
    text = resp.decode('utf-8', errors='ignore')
    lines = text.split('\n')
    print(f"Lines: {len(lines)}")
    for i, line in enumerate(lines[:40]):
        print(f"{i}: {line}")
except Exception as e:
    print(f"[ERROR] read_until failed: {e}")
    
tn.close()
