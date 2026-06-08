#!/usr/bin/env python3
import socket
import time

HOST = "138.59.175.17"
PORT = 2123

print(f"Conectando a {HOST}:{PORT}...")
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((HOST, PORT))

def read_until(sock, timeout=2):
    sock.settimeout(timeout)
    data = b""
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            print(f"[RX] {len(chunk)} bytes: {repr(chunk[:100])}")
    except socket.timeout:
        pass
    sock.settimeout(None)
    return data

# Login
print("\n=== LOGIN ===")
login_prompt = read_until(sock)
print(f"[TOTAL] {len(login_prompt)} bytes")

sock.send(b"admin\r\n")
time.sleep(0.5)
pwd_prompt = read_until(sock)
print(f"[TOTAL] {len(pwd_prompt)} bytes")

sock.send(b"3190gef6\r\n")
time.sleep(1)
login_resp = read_until(sock, timeout=3)
print(f"[TOTAL] {len(login_resp)} bytes:\n{login_resp.decode('utf-8', errors='ignore')}")

# Enviar comando
print("\n=== COMANDO: show ont 1/0/1 5 ===")
sock.send(b"show ont 1/0/1 5\r\n")
time.sleep(1)
resp = read_until(sock, timeout=5)
print(f"[TOTAL] {len(resp)} bytes:\n{resp.decode('utf-8', errors='ignore')}")

sock.close()
print("Cerrado")
