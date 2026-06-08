#!/usr/bin/env python3
import socket
import time

def telnet_cmd(cmd, user="admin", pwd="3190gef6"):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("138.59.175.17", 2123))
    
    def read_response(timeout=3):
        sock.settimeout(timeout)
        data = b""
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass
        return data
    
    # Skip telnet handshake
    read_response(1)
    
    # Login
    sock.send(b"admin\r\n")
    read_response(1)
    sock.send(b"3190gef6\r\n")
    read_response(1)
    
    # Send command
    sock.send(cmd.encode() + b"\r\n")
    time.sleep(0.5)
    resp = read_response(2)
    sock.close()
    
    return resp.decode('utf-8', errors='ignore')

commands = [
    "show ont",
    "show interface",
    "show interface 1/0/1",
    "show interface 1/0/1 5",
    "show interface 1/0/1:5",
    "show interface 1/0",
    "show port 1/0/1",
    "display ont",
    "display interface",
]

for cmd in commands:
    print(f"\n{'='*60}")
    print(f"COMANDO: {cmd}")
    print('='*60)
    resp = telnet_cmd(cmd)
    lines = resp.split('\n')
    # Mostrar primeras 15 líneas
    for i, line in enumerate(lines[:15]):
        if line.strip():
            print(line)
    if len(lines) > 15:
        print(f"... ({len(lines)-15} líneas más)")
