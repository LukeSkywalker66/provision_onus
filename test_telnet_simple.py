#!/usr/bin/env python3
import socket
import time

HOST = "138.59.175.17"
PORT = 2123

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((HOST, PORT))

def send_and_receive(cmd, timeout=3):
    sock.send(cmd.encode() + b"\r\n")
    time.sleep(0.3)
    
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
    sock.settimeout(None)
    return data.decode('utf-8', errors='ignore')

# Skip login
sock.settimeout(1)
try:
    while True:
        sock.recv(1024)
except socket.timeout:
    pass
sock.settimeout(None)

sock.send(b"admin\r\n")
time.sleep(0.3)
sock.recv(1024)

sock.send(b"3190gef6\r\n")
time.sleep(1)
sock.recv(1024)

# Now test commands
print("=== COMANDO: show ont ===")
resp = send_and_receive("show ont")
print(f"Respuesta ({len(resp)} bytes):")
print(resp)

print("\n=== COMANDO: show interface ===")
resp = send_and_receive("show interface")
print(f"Respuesta ({len(resp)} bytes):")
lines = resp.split('\n')[:20]
for line in lines:
    print(line)

sock.close()
