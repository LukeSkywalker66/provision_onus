#!/usr/bin/env python3
import telnetlib
import time

HOST = "138.59.175.17"
PORT = 2123

print("Conectando...")
tn = telnetlib.Telnet(HOST, PORT, timeout=5)

print("=== Esperando login prompt ===")
output = tn.read_until(b"User:", timeout=3)
print(f"Recibido: {repr(output)}")

tn.write(b"admin\r\n")
output = tn.read_until(b"Password:", timeout=3)
print(f"Recibido: {repr(output)}")

tn.write(b"3190gef6\r\n")
time.sleep(0.5)
output = tn.read_until(b">", timeout=3)
print(f"Recibido: {output.decode('utf-8', errors='ignore')}")

print("\n=== COMANDO: show ont ===")
tn.write(b"show ont\r\n")
output = tn.read_until(b">", timeout=5)
resp = output.decode('utf-8', errors='ignore')
print(f"Output:\n{resp}")

print("\n=== COMANDO: show interface ===")
tn.write(b"show interface\r\n")
output = tn.read_until(b">", timeout=5)
resp = output.decode('utf-8', errors='ignore')
lines = resp.split('\n')
for i, line in enumerate(lines[:20]):
    print(f"{i}: {line}")

tn.close()
