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

# Probar diferentes comandos para ver ONT info
commands = [
    "show ont ?",
    "show ont 1",
    "show ont 1/0",
    "show ont 1/0/1",
    "show ont 1/0/1 5",
    "show service ?",
    "show service-port",
    "show service-port 1/0/1 5",
    "show running-config | include service-port",
]

for cmd in commands:
    print(f"\n{'='*60}\nCOMDO: {cmd}\n{'='*60}")
    tn.write(cmd.encode() + b"\r\n")
    try:
        output = tn.read_until(b"#", timeout=3)
        resp = output.decode('utf-8', errors='ignore')
        lines = resp.split('\n')
        # Mostrar sin las primeras líneas que son eco del comando
        for i, line in enumerate(lines):
            if i == 0:
                continue  # Skip echo
            if line.strip():
                print(line)
            if i > 30:  # Limitar a 30 líneas
                print(f"... ({len(lines)-i} líneas más)")
                break
    except:
        print("[TIMEOUT o ERROR]")

# Si hay paging, presionar q
tn.write(b"q\r\n")
tn.close()
