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

# Probar variaciones del comando
commands = [
    "show ont wan 1/0/1 ?",
    "show ont wan 1/0/1 all",
    "show ont info 1/0/1 5",
    "show ont 1/0/1 5",
]

for cmd in commands:
    print(f"\n{'='*50}\nCOMDO: {cmd}\n{'='*50}")
    tn.write(cmd.encode() + b"\r\n")
    time.sleep(0.3)
    try:
        resp = tn.read_until(b"#", timeout=5)
        text = resp.decode('utf-8', errors='ignore')
        lines = text.split('\n')
        for i, line in enumerate(lines[:15]):
            if line.strip():
                print(line)
        if len(lines) > 15:
            print(f"... ({len(lines)-15} más)")
    except Exception as e:
        print(f"[ERROR] {e}")

tn.close()
