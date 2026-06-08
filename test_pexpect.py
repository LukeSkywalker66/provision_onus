#!/usr/bin/env python3
import pexpect

# Usar telnet a través de pexpect
child = pexpect.spawn('telnet 138.59.175.17 2123')
child.timeout = 5

try:
    print("=== Esperando login prompt ===")
    child.expect('User:')
    print("Recibido User prompt")
    
    child.sendline('admin')
    child.expect('Password:')
    print("Recibido Password prompt")
    
    child.sendline('3190gef6')
    child.expect('#|>')
    print("Login exitoso!")
    
    print("\n=== COMANDO: show ont ===")
    child.sendline('show ont')
    child.expect('#|>')
    output = child.before.decode('utf-8', errors='ignore')
    print(f"Output:\n{output}")
    
    print("\n=== COMANDO: show interface ===")
    child.sendline('show interface')
    child.expect('#|>')
    output = child.before.decode('utf-8', errors='ignore')
    lines = output.split('\n')[:30]
    for line in lines:
        print(line)
    
    child.close()
    
except pexpect.exceptions.TIMEOUT:
    print(f"TIMEOUT. Buffer: {child.buffer}")
except pexpect.exceptions.EOF:
    print(f"EOF. Output: {child.before}")
except Exception as e:
    print(f"Error: {e}")
