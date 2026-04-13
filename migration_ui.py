import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox

from migration_bdcom import (
    build_migration_rows,
    export_migration_csv,
    parse_bdcom_mac_table,
    parse_bdcom_running_config,
    query_mikrotik_pppoe_users,
)


class MigrationBDCOMWindow(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Preparar Migracion BDCOM")
        self.geometry("980x620")

        self.running_path = tk.StringVar()
        self.mac_path = tk.StringVar()
        self.mikrotik_host = tk.StringVar()
        self.mikrotik_user = tk.StringVar()
        self.mikrotik_pass = tk.StringVar()
        self.mikrotik_port = tk.StringVar(value="8728")
        self.zte_board = tk.StringVar()

        self._build()

    def _build(self):
        frame_files = tk.LabelFrame(self, text="Archivos de entrada")
        frame_files.pack(fill="x", padx=10, pady=8)

        tk.Label(frame_files, text="BDCOM Running Config (.txt):").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        tk.Entry(frame_files, textvariable=self.running_path, width=90).grid(row=0, column=1, padx=6, pady=4)
        tk.Button(frame_files, text="Examinar", command=self._browse_running).grid(row=0, column=2, padx=6, pady=4)

        tk.Label(frame_files, text="BDCOM MAC Table (.txt):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        tk.Entry(frame_files, textvariable=self.mac_path, width=90).grid(row=1, column=1, padx=6, pady=4)
        tk.Button(frame_files, text="Examinar", command=self._browse_mac).grid(row=1, column=2, padx=6, pady=4)

        frame_mk = tk.LabelFrame(self, text="MikroTik (API)")
        frame_mk.pack(fill="x", padx=10, pady=6)

        tk.Label(frame_mk, text="Host/IP:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        tk.Entry(frame_mk, textvariable=self.mikrotik_host, width=24).grid(row=0, column=1, padx=6, pady=4)
        tk.Label(frame_mk, text="Usuario:").grid(row=0, column=2, sticky="w", padx=6, pady=4)
        tk.Entry(frame_mk, textvariable=self.mikrotik_user, width=20).grid(row=0, column=3, padx=6, pady=4)
        tk.Label(frame_mk, text="Password:").grid(row=0, column=4, sticky="w", padx=6, pady=4)
        tk.Entry(frame_mk, textvariable=self.mikrotik_pass, show="*", width=20).grid(row=0, column=5, padx=6, pady=4)
        tk.Label(frame_mk, text="Puerto:").grid(row=0, column=6, sticky="w", padx=6, pady=4)
        tk.Entry(frame_mk, textvariable=self.mikrotik_port, width=8).grid(row=0, column=7, padx=6, pady=4)
        tk.Label(frame_mk, text="Placa ZTE Destino (ej: 1/4):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        tk.Entry(frame_mk, textvariable=self.zte_board, width=16).grid(row=1, column=1, padx=6, pady=4, sticky="w")

        frame_actions = tk.Frame(self)
        frame_actions.pack(fill="x", padx=10, pady=8)
        self.btn_generate = tk.Button(frame_actions, text="Generar CSV de Migracion", width=28, command=self._on_generate)
        self.btn_generate.pack(side="left")
        self.status = tk.Label(frame_actions, text="Listo")
        self.status.pack(side="left", padx=12)

        self.log = scrolledtext.ScrolledText(self, height=24, width=130, state="normal")
        self.log.pack(fill="both", expand=True, padx=10, pady=8)

    def _browse_running(self):
        p = filedialog.askopenfilename(
            parent=self,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if p:
            self.running_path.set(p)
        self.lift()
        self.focus_force()

    def _browse_mac(self):
        p = filedialog.askopenfilename(
            parent=self,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if p:
            self.mac_path.set(p)
        self.lift()
        self.focus_force()

    def _write(self, msg):
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.update_idletasks()

    def _validate_inputs(self):
        if not self.running_path.get() or not os.path.exists(self.running_path.get()):
            raise ValueError("Selecciona un archivo valido para BDCOM Running Config")
        if not self.mac_path.get() or not os.path.exists(self.mac_path.get()):
            raise ValueError("Selecciona un archivo valido para BDCOM MAC Table")
        if not self.mikrotik_host.get().strip():
            raise ValueError("Ingresa Host/IP de MikroTik")
        if not self.mikrotik_user.get().strip():
            raise ValueError("Ingresa usuario de MikroTik")
        if not self.mikrotik_port.get().strip().isdigit():
            raise ValueError("Puerto de MikroTik invalido")
        zte_board = self.zte_board.get().strip()
        if not re.match(r"^\d+/\d+$", zte_board):
            raise ValueError("Placa ZTE Destino invalida (formato esperado: 1/4)")

    def _run_generate(self):
        try:
            self.status.config(text="Procesando...")
            self._validate_inputs()

            self._write("[1/4] Parseando Running Config...")
            running_map = parse_bdcom_running_config(self.running_path.get())
            self._write(f"[OK] Running Config parseado: {len(running_map)} ONUs mapeadas por puerto")

            self._write("[2/4] Parseando MAC Table y cruzando con Running Config...")
            mac_records = parse_bdcom_mac_table(self.mac_path.get(), running_map)
            self._write(f"[OK] MAC Table parseada: {len(mac_records)} registros con puerto/onu")

            self._write("[3/4] Consultando MikroTik via API (active + secret)...")
            mac_to_pppoe = query_mikrotik_pppoe_users(
                host=self.mikrotik_host.get().strip(),
                username=self.mikrotik_user.get().strip(),
                password=self.mikrotik_pass.get(),
                port=int(self.mikrotik_port.get().strip()),
            )
            self._write(f"[OK] MikroTik consultado: {len(mac_to_pppoe)} MACs con usuario PPPoE")

            self._write("[4/4] Construyendo CSV final de migracion...")
            rows, matched = build_migration_rows(
                mac_records,
                mac_to_pppoe,
                self.zte_board.get().strip(),
            )
            output_path = os.path.join(os.getcwd(), "migracion_zte_final.csv")
            export_migration_csv(output_path, rows)

            self._write(f"[OK] Cruce exitoso: {matched} clientes")
            self._write(f"[OK] Archivo generado: {output_path}")
            self.status.config(text=f"Completado - {matched} cruces")
            messagebox.showinfo(
                "Migracion lista",
                f"Archivo generado:\n{output_path}\n\nClientes cruzados: {matched}",
            )
        except Exception as e:
            self.status.config(text="Error")
            self._write(f"[ERROR] {e}")
            messagebox.showerror("Error", str(e))
        finally:
            self.btn_generate.config(state="normal")

    def _on_generate(self):
        self.btn_generate.config(state="disabled")
        t = threading.Thread(target=self._run_generate, daemon=True)
        t.start()
