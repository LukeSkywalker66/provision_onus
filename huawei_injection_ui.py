import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, simpledialog

from huawei_injection import load_migration_csv, run_preprovision_huawei
from smartolt_api import move_onus_from_csv_rows, update_bridge_mode_from_csv_rows


class HuaweiInjectionWindow(tk.Toplevel):
    def __init__(
        self,
        master=None,
        default_olt_name="",
        default_ip="",
        default_user="",
        default_password="",
        default_port=22,
        strict_target_identity=True,
    ):
        super().__init__(master)
        self.title("Inyeccion Huawei (Pre-Aprovisionamiento)")
        self.geometry("980x620")

        self.olt_name = tk.StringVar(value=(default_olt_name or "HUAWEI"))
        self.huawei_ip = tk.StringVar(value=default_ip)
        self.huawei_user = tk.StringVar(value=default_user)
        self.huawei_password = tk.StringVar(value=default_password)
        self.huawei_port = tk.StringVar(value=str(default_port or 22))
        self.strict_target_identity = bool(strict_target_identity)
        self.expected_ip = (default_ip or "").strip()
        self.expected_user = (default_user or "").strip()
        self.expected_port = str(default_port or 22).strip()
        self.csv_path = tk.StringVar(value=os.path.join(os.getcwd(), "migracion_zte_final.csv"))
        self.simulation_mode = tk.BooleanVar(value=True)
        self.repair_mode = tk.BooleanVar(value=False)
        self.smartolt_move_mode = tk.BooleanVar(value=False)
        self.smartolt_move_only = tk.BooleanVar(value=False)
        self.smartolt_mode_update_mode = tk.BooleanVar(value=False)
        self.smartolt_mode_update_only = tk.BooleanVar(value=False)
        self._ui_queue = queue.Queue()
        self._closing = False

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._drain_ui_queue)

    def _build(self):
        frame_conn = tk.LabelFrame(self, text="Conexion OLT destino")
        frame_conn.pack(fill="x", padx=10, pady=8)

        tk.Label(frame_conn, text="OLT:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        tk.Entry(frame_conn, textvariable=self.olt_name, width=22, state="readonly").grid(
            row=0, column=1, padx=6, pady=4
        )

        tk.Label(frame_conn, text="IP:").grid(row=0, column=2, sticky="w", padx=6, pady=4)
        tk.Entry(
            frame_conn,
            textvariable=self.huawei_ip,
            width=20,
            state="readonly" if self.strict_target_identity else "normal",
        ).grid(row=0, column=3, padx=6, pady=4)
        tk.Label(frame_conn, text="Usuario:").grid(row=0, column=4, sticky="w", padx=6, pady=4)
        tk.Entry(
            frame_conn,
            textvariable=self.huawei_user,
            width=20,
            state="readonly" if self.strict_target_identity else "normal",
        ).grid(row=0, column=5, padx=6, pady=4)
        tk.Label(frame_conn, text="Contrasena:").grid(row=0, column=6, sticky="w", padx=6, pady=4)
        tk.Entry(frame_conn, textvariable=self.huawei_password, show="*", width=20).grid(row=0, column=7, padx=6, pady=4)
        tk.Label(frame_conn, text="Puerto SSH:").grid(row=0, column=8, sticky="w", padx=6, pady=4)
        tk.Entry(
            frame_conn,
            textvariable=self.huawei_port,
            width=8,
            state="readonly" if self.strict_target_identity else "normal",
        ).grid(row=0, column=9, padx=6, pady=4)

        frame_csv = tk.LabelFrame(self, text="Archivo CSV de migracion")
        frame_csv.pack(fill="x", padx=10, pady=6)
        tk.Entry(frame_csv, textvariable=self.csv_path, width=100).pack(side="left", padx=6, pady=6)
        tk.Button(frame_csv, text="Cargar CSV", command=self._browse_csv).pack(side="left", padx=6, pady=6)

        frame_actions = tk.Frame(self)
        frame_actions.pack(fill="x", padx=10, pady=8)
        tk.Checkbutton(
            frame_actions,
            text="Modo Simulacion (Dry-Run)",
            variable=self.simulation_mode,
        ).pack(side="left", padx=6)
        tk.Checkbutton(
            frame_actions,
            text="Modo reparacion (recrear ONU + service-port)",
            variable=self.repair_mode,
        ).pack(side="left", padx=6)
        tk.Checkbutton(
            frame_actions,
            text="Mover ONUs en SmartOLT por CSV",
            variable=self.smartolt_move_mode,
        ).pack(side="left", padx=6)
        tk.Checkbutton(
            frame_actions,
            text="Solo SmartOLT move (sin inyeccion OLT)",
            variable=self.smartolt_move_only,
        ).pack(side="left", padx=6)
        tk.Checkbutton(
            frame_actions,
            text="Actualizar modo BRIDGE en SmartOLT por CSV",
            variable=self.smartolt_mode_update_mode,
        ).pack(side="left", padx=6)
        tk.Checkbutton(
            frame_actions,
            text="Solo SmartOLT mode update (sin inyeccion OLT)",
            variable=self.smartolt_mode_update_only,
        ).pack(side="left", padx=6)

        self.btn_start = tk.Button(
            frame_actions,
            text="Iniciar Inyeccion Huawei",
            width=28,
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
        self._queue_ui(self._append_log, msg)

    def _queue_ui(self, callback, *args, **kwargs):
        if self._closing:
            return
        self._ui_queue.put((callback, args, kwargs))

    def _drain_ui_queue(self):
        if self._closing or not self.winfo_exists():
            return
        try:
            while True:
                callback, args, kwargs = self._ui_queue.get_nowait()
                try:
                    callback(*args, **kwargs)
                except tk.TclError:
                    # La ventana ya no existe o el widget fue destruido.
                    pass
        except queue.Empty:
            pass
        finally:
            if not self._closing and self.winfo_exists():
                self.after(100, self._drain_ui_queue)

    def _append_log(self, msg):
        if not self.winfo_exists() or not self.log.winfo_exists():
            return
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

    def _set_status(self, text):
        if self.winfo_exists() and self.status.winfo_exists():
            self.status.config(text=text)

    def _set_start_button_state(self, state):
        if self.winfo_exists() and self.btn_start.winfo_exists():
            self.btn_start.config(state=state)

    def _show_info(self, title, message):
        if self.winfo_exists():
            messagebox.showinfo(title, message, parent=self)

    def _show_error(self, title, message):
        if self.winfo_exists():
            messagebox.showerror(title, message, parent=self)

    def _on_close(self):
        self._closing = True
        self.destroy()

    def _validate_inputs(self):
        if not self.huawei_ip.get().strip():
            raise ValueError(f"Ingresa IP de OLT destino ({self.olt_name.get()})")
        if not self.huawei_user.get().strip():
            raise ValueError(f"Ingresa usuario de OLT destino ({self.olt_name.get()})")
        if not self.huawei_port.get().strip().isdigit():
            raise ValueError("Puerto SSH de OLT destino invalido")
        if not self.csv_path.get().strip() or not os.path.exists(self.csv_path.get().strip()):
            raise ValueError("Selecciona un CSV de migracion valido")
        if self.strict_target_identity:
            cur_ip = self.huawei_ip.get().strip()
            cur_user = self.huawei_user.get().strip()
            cur_port = self.huawei_port.get().strip()
            if (
                cur_ip != self.expected_ip
                or cur_user != self.expected_user
                or cur_port != self.expected_port
            ):
                raise ValueError(
                    "La identidad del destino no coincide con la OLT configurada para este proceso."
                )

    def _run(self):
        try:
            self._queue_ui(self._set_status, "Procesando...")
            self._validate_inputs()

            rows = load_migration_csv(self.csv_path.get().strip())
            if not rows:
                raise ValueError("No hay filas validas para procesar en el CSV")

            self._write(f"[INFO] Filas a procesar: {len(rows)}")
            if self.simulation_mode.get():
                self._write("[WARN] Ejecutando en MODO SIMULACION (dry-run)")
            else:
                self._write(
                    f"[WARN] Ejecutando en MODO REAL sobre OLT productiva {self.olt_name.get()} ({self.huawei_ip.get().strip()})"
                )
            if self.repair_mode.get():
                self._write(
                    "[WARN] MODO REPARACION activo: por cada ONU se intentara eliminar service-port(s) y ONT antes de recrear"
                )
            if self.smartolt_move_mode.get():
                self._write(
                    "[WARN] SMARTOLT MOVE activo: se actualizara board/port por SN uno a uno segun el CSV"
                )
            if self.smartolt_move_only.get():
                self._write("[WARN] MODO SOLO SMARTOLT activo: se omitira la inyeccion en OLT")
            if self.smartolt_mode_update_mode.get():
                self._write(
                    "[WARN] SMARTOLT MODE UPDATE activo: se enviara onu_mode=Bridging para filas BRIDGE del CSV"
                )
            if self.smartolt_mode_update_only.get():
                self._write("[WARN] MODO SOLO SMARTOLT MODE UPDATE activo: se omitira la inyeccion en OLT")

            if self.smartolt_move_mode.get():
                move_result = move_onus_from_csv_rows(
                    rows=rows,
                    logger=self._write,
                    dry_run=self.simulation_mode.get(),
                )
                if move_result.get("error", 0) > 0 and not self.simulation_mode.get():
                    raise RuntimeError(
                        "SmartOLT move tuvo errores. Se aborta inyeccion OLT para evitar inconsistencias."
                    )

            if self.smartolt_mode_update_mode.get():
                mode_result = update_bridge_mode_from_csv_rows(
                    rows=rows,
                    logger=self._write,
                    dry_run=self.simulation_mode.get(),
                )
                if mode_result.get("error", 0) > 0 and not self.simulation_mode.get():
                    raise RuntimeError(
                        "SmartOLT mode update tuvo errores. Se aborta inyeccion OLT para evitar inconsistencias."
                    )

            if self.smartolt_move_only.get() or self.smartolt_mode_update_only.get():
                self._write("[OK] Flujo SmartOLT finalizado (sin inyeccion OLT)")
                self._queue_ui(self._set_status, "Completado")
                self._queue_ui(
                    self._show_info,
                    "Proceso finalizado",
                    "Proceso SmartOLT completado. No se ejecuto inyeccion OLT.",
                )
                return

            self._write(
                f"[INFO] Abriendo sesion SSH contra {self.olt_name.get()} {self.huawei_ip.get().strip()}:{self.huawei_port.get().strip()}"
            )

            result = run_preprovision_huawei(
                ip=self.huawei_ip.get().strip(),
                username=self.huawei_user.get().strip(),
                password=self.huawei_password.get(),
                port=int(self.huawei_port.get().strip()),
                rows=rows,
                logger=self._write,
                dry_run=self.simulation_mode.get(),
                repair_mode=self.repair_mode.get(),
            )
            self._write("[INFO] Sesion SSH establecida y flujo de inyeccion ejecutado")

            self._write("[OK] Inyeccion Huawei finalizada")
            self._write(
                f"[INFO] Resumen: OK={result['ok']} | ERROR={result['error']} | TOTAL={result['total']}"
            )
            self._queue_ui(self._set_status, "Completado")
            self._queue_ui(
                self._show_info,
                "Inyeccion Huawei finalizada",
                f"OK: {result['ok']}\nError: {result['error']}\nTotal: {result['total']}",
            )
        except Exception as e:
            self._queue_ui(self._set_status, "Error")
            self._write(f"[ERROR] {e}")
            self._queue_ui(self._show_error, "Error", str(e))
        finally:
            self._queue_ui(self._set_start_button_state, "normal")

    def _on_start(self):
        if self.smartolt_move_only.get() and not self.smartolt_move_mode.get():
            self.smartolt_move_mode.set(True)
        if self.smartolt_mode_update_only.get() and not self.smartolt_mode_update_mode.get():
            self.smartolt_mode_update_mode.set(True)

        if not self.simulation_mode.get():
            confirmation = simpledialog.askstring(
                "Confirmacion requerida",
                f"Escribe EJECUTAR para confirmar inyeccion REAL en {self.olt_name.get()} ({self.huawei_ip.get()}):",
                parent=self,
            )
            if confirmation != "EJECUTAR":
                self._write("[WARN] Confirmacion invalida. Se cancela la ejecucion real.")
                return

        self.btn_start.config(state="disabled")
        t = threading.Thread(target=self._run, daemon=True)
        t.start()