import os
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, simpledialog

from zte_injection import load_migration_csv, run_preprovision_zte


class ZTEInjectionWindow(tk.Toplevel):
    def __init__(
        self,
        master=None,
        default_ip="",
        default_user="",
        default_password="",
        default_port=22,
        default_vlan_id="700",
        default_olt_name="",
        olt_options=None,
    ):
        super().__init__(master)
        self.title("Inyeccion ZTE (Pre-Aprovisionamiento)")
        self.geometry("980x620")

        self.olt_options = olt_options or {}
        if default_olt_name and default_olt_name not in self.olt_options:
            default_olt_name = ""
        if not default_olt_name and self.olt_options:
            default_olt_name = next(iter(self.olt_options), "")
        self.olt_name = tk.StringVar(value=default_olt_name)
        self.zte_ip = tk.StringVar(value=default_ip)
        self.zte_user = tk.StringVar(value=default_user)
        self.zte_password = tk.StringVar(value=default_password)
        self.zte_port = tk.StringVar(value=str(default_port or 22))
        self.zte_vlan_id = tk.StringVar(value=str(default_vlan_id or "700"))
        self.csv_path = tk.StringVar(value=os.path.join(os.getcwd(), "migracion_zte_final.csv"))
        self.simulation_mode = tk.BooleanVar(value=True)

        self._build()
        if self.olt_options:
            self.olt_name.trace_add("write", lambda *_: self._apply_olt_config())
        self._apply_olt_config()

    def _build(self):
        frame_conn = tk.LabelFrame(self, text="Conexion OLT ZTE")
        frame_conn.pack(fill="x", padx=10, pady=8)

        row = 0
        if self.olt_options:
            tk.Label(frame_conn, text="OLT:").grid(row=row, column=0, sticky="w", padx=6, pady=4)
            olt_menu = tk.OptionMenu(frame_conn, self.olt_name, *self.olt_options.keys())
            olt_menu.config(width=22)
            olt_menu.grid(row=row, column=1, padx=6, pady=4, sticky="w")
            row += 1
        else:
            tk.Label(frame_conn, text="OLT:").grid(row=row, column=0, sticky="w", padx=6, pady=4)
            tk.Label(frame_conn, text="(sin OLT ZTE configurada)").grid(
                row=row, column=1, padx=6, pady=4, sticky="w"
            )
            row += 1

        tk.Label(frame_conn, text="IP:").grid(row=row, column=0, sticky="w", padx=6, pady=4)
        tk.Entry(frame_conn, textvariable=self.zte_ip, width=20).grid(row=row, column=1, padx=6, pady=4)
        tk.Label(frame_conn, text="Usuario:").grid(row=row, column=2, sticky="w", padx=6, pady=4)
        tk.Entry(frame_conn, textvariable=self.zte_user, width=20).grid(row=row, column=3, padx=6, pady=4)
        tk.Label(frame_conn, text="Password:").grid(row=row, column=4, sticky="w", padx=6, pady=4)
        tk.Entry(frame_conn, textvariable=self.zte_password, show="*", width=20).grid(row=row, column=5, padx=6, pady=4)
        tk.Label(frame_conn, text="Puerto:").grid(row=row, column=6, sticky="w", padx=6, pady=4)
        tk.Entry(frame_conn, textvariable=self.zte_port, width=8).grid(row=row, column=7, padx=6, pady=4)
        tk.Label(frame_conn, text="VLAN:").grid(row=row, column=8, sticky="w", padx=6, pady=4)
        tk.Entry(frame_conn, textvariable=self.zte_vlan_id, width=8).grid(row=row, column=9, padx=6, pady=4)

        frame_csv = tk.LabelFrame(self, text="Archivo CSV de migracion")
        frame_csv.pack(fill="x", padx=10, pady=6)
        tk.Entry(frame_csv, textvariable=self.csv_path, width=100).pack(side="left", padx=6, pady=6)
        tk.Button(frame_csv, text="Cargar CSV", command=self._browse_csv).pack(side="left", padx=6, pady=6)

        frame_actions = tk.Frame(self)
        frame_actions.pack(fill="x", padx=10, pady=8)
        tk.Checkbutton(
            frame_actions,
            text="Modo simulacion (sin cambios en OLT)",
            variable=self.simulation_mode,
        ).pack(side="left", padx=6)
        self.btn_start = tk.Button(
            frame_actions,
            text="Iniciar Pre-Aprovisionamiento",
            width=30,
            command=self._on_start,
        )
        self.btn_start.pack(side="left", padx=8)
        self.status = tk.Label(frame_actions, text="Listo")
        self.status.pack(side="left", padx=12)

        self.log = scrolledtext.ScrolledText(self, height=24, width=130, state="normal")
        self.log.pack(fill="both", expand=True, padx=10, pady=8)
        self.log.tag_config("error", foreground="red")
        self.log.tag_config("warn", foreground="orange")
        self.log.tag_config("ok", foreground="green")
        self.log.tag_config("info", foreground="black")

    def _browse_csv(self):
        p = filedialog.askopenfilename(parent=self, filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if p:
            self.csv_path.set(p)
        self.lift()
        self.focus_force()

    def _write(self, msg):
        tag = "info"
        if msg.startswith("[ERROR]"):
            tag = "error"
        elif msg.startswith("[WARN]"):
            tag = "warn"
        elif msg.startswith("[OK]"):
            tag = "ok"
        self.log.insert(tk.END, msg + "\n", tag)
        self.log.see(tk.END)
        self.log.update_idletasks()

    def _apply_olt_config(self):
        if not self.olt_options:
            return
        olt_name = (self.olt_name.get() or "").strip()
        cfg = self.olt_options.get(olt_name)
        if not cfg:
            return
        self.zte_ip.set(cfg.get("ip", "") or "")
        self.zte_user.set(cfg.get("user", "") or "")
        self.zte_password.set(cfg.get("password", "") or "")
        self.zte_port.set(str(cfg.get("port", 22) or 22))

    def _validate_inputs(self):
        if not self.zte_ip.get().strip():
            raise ValueError("Ingresa IP de OLT ZTE")
        if not self.zte_user.get().strip():
            raise ValueError("Ingresa usuario de OLT ZTE")
        if not self.zte_port.get().strip().isdigit():
            raise ValueError("Puerto de OLT ZTE invalido")
        if not self.zte_vlan_id.get().strip().isdigit():
            raise ValueError("VLAN de ZTE invalida")
        if not self.csv_path.get().strip() or not os.path.exists(self.csv_path.get().strip()):
            raise ValueError("Selecciona un CSV de migracion valido")

    def _run(self):
        try:
            self.status.config(text="Procesando...")
            self._validate_inputs()

            selected_olt = (self.olt_name.get() or "").strip()
            if selected_olt:
                self._write(f"[INFO] OLT destino: {selected_olt}")

            rows = load_migration_csv(self.csv_path.get().strip())
            if not rows:
                raise ValueError("No hay filas validas para procesar en el CSV")

            self._write(f"[INFO] Filas a procesar: {len(rows)}")
            if self.simulation_mode.get():
                self._write("[WARN] Ejecutando en MODO SIMULACION (dry-run)")
            else:
                self._write("[WARN] Ejecutando en MODO REAL sobre OLT productiva")

            result = run_preprovision_zte(
                ip=self.zte_ip.get().strip(),
                username=self.zte_user.get().strip(),
                password=self.zte_password.get(),
                port=int(self.zte_port.get().strip()),
                rows=rows,
                logger=self._write,
                dry_run=self.simulation_mode.get(),
                olt_name=selected_olt,
            )

            self._write("[OK] Pre-aprovisionamiento finalizado")
            self._write(
                f"[INFO] Resumen: OK={result['ok']} | ERROR={result['error']} | TOTAL={result['total']}"
            )
            self.status.config(text="Completado")
            messagebox.showinfo(
                "Inyeccion finalizada",
                f"OK: {result['ok']}\nError: {result['error']}\nTotal: {result['total']}",
            )
        except Exception as e:
            self.status.config(text="Error")
            self._write(f"[ERROR] {e}")
            messagebox.showerror("Error", str(e))
        finally:
            self.btn_start.config(state="normal")

    def _on_start(self):
        if not self.simulation_mode.get():
            confirmation = simpledialog.askstring(
                "Confirmación requerida",
                "Escribe EJECUTAR para confirmar inyección REAL en OLT productiva:",
                parent=self,
            )
            if confirmation != "EJECUTAR":
                self._write("[WARN] Confirmación inválida. Se cancela la ejecución real.")
                return

        self.btn_start.config(state="disabled")
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
