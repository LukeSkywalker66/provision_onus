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

# Probar con diferentes ONT IDs
for ont_id in [0, 1, 5, 10]:
    cmd = f"show ont wan 1/0/1 {ont_id}"
    print(f"\n{'='*60}\nCOMDO: {cmd}\n{'='*60}")
    tn.write(cmd.encode() + b"\r\n")
    time.sleep(0.3)
    try:
        resp = tn.read_until(b"#", timeout=10)
        text = resp.decode('utf-8', errors='ignore')
        lines = text.split('\n')
        for i, line in enumerate(lines[:50]):
            if line.strip():
                print(line)
        if len(lines) > 50:
            print(f"... ({len(lines)-50} más)")
    except Exception as e:
        print(f"[ERROR] {e}")

tn.close()
