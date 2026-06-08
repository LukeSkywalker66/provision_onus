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
tn.read_until(b">", timeout=3)

# Enable
tn.write(b"enable\r\n")
tn.read_until(b"#", timeout=3)

# Probar show ont wan
print("=== show ont wan ? ===")
tn.write(b"show ont wan ?\r\n")
output = tn.read_until(b"#", timeout=3)
print(output.decode('utf-8', errors='ignore'))

print("\n=== show ont wan 1/0/1 5 ===")
tn.write(b"show ont wan 1/0/1 5\r\n")
output = tn.read_until(b"#", timeout=3)
print(output.decode('utf-8', errors='ignore'))

print("\n=== show ont wan 1/0/1 ===")
tn.write(b"show ont wan 1/0/1\r\n")
try:
    output = tn.read_until(b"#", timeout=5)
    resp = output.decode('utf-8', errors='ignore')
    lines = resp.split('\n')
    for i, line in enumerate(lines):
        print(line)
        if i > 50:
            print(f"... ({len(lines)-i} líneas más)")
            break
except:
    print("[TIMEOUT]")

tn.close()
