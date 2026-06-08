#!/usr/bin/env python3
import telnetlib

HOST = "138.59.175.17"
PORT = 2123

tn = telnetlib.Telnet(HOST, PORT, timeout=5)

# Login
tn.read_until(b"User:", timeout=3)
tn.write(b"admin\r\n")
tn.read_until(b"Password:", timeout=3)
tn.write(b"3190gef6\r\n")
output = tn.read_until(b">", timeout=3)
print("Login successful (user mode)")
print(output.decode('utf-8', errors='ignore'))

# Cambiar a enable mode
print("\n=== Entrando en ENABLE mode ===")
tn.write(b"enable\r\n")
output = tn.read_until(b"#", timeout=3)
print(output.decode('utf-8', errors='ignore'))

print("\n=== COMANDO: show ont ===")
tn.write(b"show ont\r\n")
output = tn.read_until(b"#", timeout=5)
resp = output.decode('utf-8', errors='ignore')
print(f"Output:\n{resp}")

print("\n=== COMANDO: show running-config | include ont ===")
tn.write(b"show running-config | include ont\r\n")
output = tn.read_until(b"#", timeout=5)
resp = output.decode('utf-8', errors='ignore')
lines = resp.split('\n')
for line in lines:
    print(line)

tn.close()
