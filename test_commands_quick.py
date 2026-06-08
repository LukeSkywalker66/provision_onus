#!/usr/bin/env python3
import socket
import time
import threading

def telnet_cmd(cmd, timeout=3):
    result = {"resp": ""}
    
    def connect_and_send():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(("138.59.175.17", 2123))
            
            # Skip telnet negotiation
            try:
                sock.recv(1024)
            except:
                pass
            
            # Login
            sock.send(b"admin\r\n")
            try:
                sock.recv(1024)
            except:
                pass
            
            sock.send(b"3190gef6\r\n")
            try:
                sock.recv(1024)
            except:
                pass
            
            # Send command
            sock.send(cmd.encode() + b"\r\n")
            time.sleep(0.3)
            
            # Read response
            data = b""
            try:
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            except socket.timeout:
                pass
            
            result["resp"] = data.decode('utf-8', errors='ignore')
            sock.close()
        except Exception as e:
            result["resp"] = f"[ERROR] {e}"
    
    thread = threading.Thread(target=connect_and_send, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    
    return result["resp"]

commands = [
    "show ont",
    "show interface",
    "display ont",
]

for cmd in commands:
    print(f"\n{'='*50}\nCOMDO: {cmd}\n{'='*50}")
    resp = telnet_cmd(cmd, timeout=4)
    if resp:
        lines = [l for l in resp.split('\n') if l.strip()]
        for line in lines[:10]:
            print(line)
        if len(lines) > 10:
            print(f"... ({len(lines)-10} más)")
    else:
        print("[Sin respuesta]")
