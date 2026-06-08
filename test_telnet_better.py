#!/usr/bin/env python3
import socket
import time

HOST = "138.59.175.17"
PORT = 2123

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((HOST, PORT))

def handle_telnet_negotiation():
    """Responder a telnet negotiation requests"""
    sock.settimeout(0.5)
    try:
        while True:
            data = sock.recv(1024)
            if not data:
                break
            # Si contiene IAC (0xFF), responder con IAC DO/DONT
            if b'\xff' in data:
                print(f"[TELNET NEG] Recibido: {repr(data)}")
                # Response: IAC DONT para opciones que no queremos
                resp = b''
                for b in data:
                    if b == 0xff:
                        resp += b'\xff\xfe'  # IAC DONT
                if resp:
                    print(f"[TELNET NEG] Respondiendo: {repr(resp)}")
                    sock.send(resp)
    except socket.timeout:
        pass
    sock.settimeout(None)

def read_until(prompt, timeout=3):
    """Leer hasta encontrar prompt"""
    sock.settimeout(timeout)
    data = b""
    try:
        while True:
            chunk = sock.recv(1024)
            if not chunk:
                break
            data += chunk
            if prompt.encode() in data or b'>' in data or b'#' in data:
                break
    except socket.timeout:
        pass
    sock.settimeout(None)
    return data.decode('utf-8', errors='ignore')

print("=== TELNET NEGOTIATION ===")
handle_telnet_negotiation()

print("\n=== LOGIN ===")
login_prompt = read_until("User:")
print(f"Recibido ({len(login_prompt)} bytes):\n{login_prompt}")

sock.send(b"admin\r\n")
pwd_prompt = read_until("Password:")
print(f"\nRecibido ({len(pwd_prompt)} bytes):\n{pwd_prompt}")

sock.send(b"3190gef6\r\n")
prompt = read_until(">")
print(f"\nRecibido ({len(prompt)} bytes):\n{prompt}")

print("\n=== COMANDO: show ont ===")
sock.send(b"show ont\r\n")
resp = read_until(">")
print(f"Respuesta ({len(resp)} bytes):\n{resp}")

sock.close()
