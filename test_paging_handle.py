#!/usr/bin/env python3
import telnetlib
import re
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

# Comando
print("Enviando: show ont wan 1/0/1 5")
tn.write(b"show ont wan 1/0/1 5\r\n")
time.sleep(0.5)

# Leer respuesta completa, manejando paging
full_output = b""
try:
    while True:
        try:
            chunk = tn.read_until(b"Press any key to continue", timeout=2)
            full_output += chunk
            print(f"[CHUNK] {len(chunk)} bytes, encontrado paging prompt")
            
            # Enviar 'q' para continuar
            tn.write(b"q\r\n")
            time.sleep(0.2)
        except:
            # No hay más paging, intentar leer hasta el final
            try:
                final = tn.read_until(b"#", timeout=3)
                full_output += final
                print(f"[FINAL] {len(final)} bytes")
            except:
                pass
            break
except Exception as e:
    print(f"Error: {e}")

output = full_output.decode('utf-8', errors='ignore')
print(f"\nOutput total: {len(output)} bytes\n")
print(output)

tn.close()
