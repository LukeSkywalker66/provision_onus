import os
import re
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, scrolledtext, messagebox

from migration_bdcom import (
    build_migration_rows,
    export_migration_csv,
    get_mac_vendor_heuristic_diagnostics,
    parse_bdcom_mac_table,
    parse_bdcom_running_config,
    query_mikrotik_pppoe_users,
)
from config import MIKROTIK_MAP


class MigrationBDCOMWindow(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Preparar Migracion BDCOM")
        self.geometry("980x620")

        self.running_path = tk.StringVar()
        self.mac_path = tk.StringVar()
        self.mikrotik_node = tk.StringVar()
        self.mikrotik_host = tk.StringVar()
        self.mikrotik_user = tk.StringVar()
        self.mikrotik_pass = tk.StringVar()
        self.mikrotik_port = tk.StringVar(value="8728")
        self.destination_vendor = tk.StringVar(value="zte")
        self.destination_board = tk.StringVar()
        self._mikrotik_options = {}

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

        tk.Label(frame_mk, text="Nodo: ").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.cmb_mikrotik = ttk.Combobox(
            frame_mk,
            textvariable=self.mikrotik_node,
            state="readonly",
            width=50,
        )
        self.cmb_mikrotik.grid(row=0, column=1, columnspan=3, sticky="w", padx=6, pady=4)
        self.cmb_mikrotik.bind("<<ComboboxSelected>>", self._on_select_mikrotik)

        tk.Label(frame_mk, text="Host/IP:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        tk.Entry(frame_mk, textvariable=self.mikrotik_host, width=24).grid(row=1, column=1, padx=6, pady=4)
        tk.Label(frame_mk, text="Usuario:").grid(row=1, column=2, sticky="w", padx=6, pady=4)
        tk.Entry(frame_mk, textvariable=self.mikrotik_user, width=20).grid(row=1, column=3, padx=6, pady=4)
        tk.Label(frame_mk, text="Password:").grid(row=1, column=4, sticky="w", padx=6, pady=4)
        tk.Entry(frame_mk, textvariable=self.mikrotik_pass, show="*", width=20).grid(row=1, column=5, padx=6, pady=4)
        tk.Label(frame_mk, text="Puerto:").grid(row=1, column=6, sticky="w", padx=6, pady=4)
        tk.Entry(frame_mk, textvariable=self.mikrotik_port, width=8).grid(row=1, column=7, padx=6, pady=4)
        tk.Label(frame_mk, text="Destino CSV:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(
            frame_mk,
            textvariable=self.destination_vendor,
            values=["zte", "huawei"],
            state="readonly",
            width=12,
        ).grid(row=2, column=1, padx=6, pady=4, sticky="w")

        tk.Label(
            frame_mk,
            text="Placa destino (slot/placa o frame/slot, ej: 1/4 o 0/1):",
        ).grid(row=2, column=2, columnspan=3, sticky="w", padx=6, pady=4)
        tk.Entry(frame_mk, textvariable=self.destination_board, width=16).grid(
            row=2,
            column=5,
            padx=6,
            pady=4,
            sticky="w",
        )

        self._load_mikrotik_options()

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

    def _load_mikrotik_options(self):
        self._mikrotik_options = {}
        labels = []
        for name, cfg in MIKROTIK_MAP.items():
            ip = cfg.get("ip", "")
            label = f"{name} ({ip})"
            self._mikrotik_options[label] = cfg
            labels.append(label)

        self.cmb_mikrotik["values"] = labels
        if labels:
            self.mikrotik_node.set(labels[0])
            self._apply_mikrotik_node(labels[0])

    def _apply_mikrotik_node(self, label: str):
        cfg = self._mikrotik_options.get(label)
        if not cfg:
            return
        self.mikrotik_host.set(str(cfg.get("ip", "")))
        self.mikrotik_user.set(str(cfg.get("user", "")))
        self.mikrotik_pass.set(str(cfg.get("password", "")))
        self.mikrotik_port.set(str(cfg.get("port", 8728)))

    def _on_select_mikrotik(self, _event=None):
        self._apply_mikrotik_node(self.mikrotik_node.get())

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
        destination_board = self.destination_board.get().strip()
        if not re.match(r"^\d+/\d+$", destination_board):
            raise ValueError("Placa destino invalida (formato esperado: 1/4 o 0/1)")

        destination_vendor = self.destination_vendor.get().strip().lower()
        if destination_vendor not in {"zte", "huawei"}:
            raise ValueError("Destino CSV invalido (usar zte u huawei)")

    def _run_generate(self):
        try:
            self.status.config(text="Procesando...")
            self._validate_inputs()

            heur = get_mac_vendor_heuristic_diagnostics()
            self._write(
                "[INFO] Heurística MAC/vendor -> "
                f"enabled={heur.get('enabled')} | "
                f"OUI overrides={heur.get('overrides_count')} | "
                f"manuf disponible={heur.get('manuf_available')}"
            )
            if heur.get("enabled") and not heur.get("has_data_source"):
                self._write(
                    "[WARN] Heurística activa sin fuente de vendors (sin OUI overrides y sin librería manuf)."
                )

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
            rows, matched, stats = build_migration_rows(
                mac_records,
                mac_to_pppoe,
                self.destination_board.get().strip(),
                self.destination_vendor.get().strip().lower(),
            )
            destination_vendor = self.destination_vendor.get().strip().lower()
            output_filename = f"migracion_{destination_vendor}_final.csv"
            output_path = os.path.join(os.getcwd(), output_filename)
            export_migration_csv(output_path, rows)

            self._write(f"[OK] Cruce exitoso: {matched} clientes")
            self._write(
                "[INFO] Clasificacion final ONT_MODE -> "
                f"ROUTER: {stats.get('final_router', 0)} | "
                f"BRIDGE: {stats.get('final_bridge', 0)}"
            )
            self._write(
                "[INFO] Fuentes de decision -> "
                f"Bridge-only model: {stats.get('bridge_only_model', 0)} | "
                f"SN/MAC mismatch->BRIDGE: {stats.get('sn_mac_vendor_mismatch', 0)} | "
                f"SN/MAC match->ROUTER: {stats.get('sn_mac_vendor_match', 0)} | "
                f"Profile origen fallback: {stats.get('source_profile_fallback', 0)} | "
                f"OVERRIDE fallback: {stats.get('override_fallback', 0)} | "
                f"Modelo router fallback: {stats.get('known_router_model_fallback', 0)} | "
                f"Default ROUTER: {stats.get('unresolved_default_router', 0)}"
            )
            if stats.get("unresolved_default_router", 0) > 0:
                self._write(
                    "[WARN] Hay ONUs clasificadas por fallback final (ROUTER) sin confirmación sólida. "
                    "Revisar esos casos por separado."
                )
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
