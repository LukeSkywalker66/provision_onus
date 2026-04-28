import threading
import tkinter as tk
from datetime import datetime
import os
from tkinter import messagebox, scrolledtext, ttk

from config import MIKROTIK_MAP
from migration_bdcom import delete_mikrotik_ppp_secret, list_mikrotik_ppp_secrets


class MikrotikSecretWindow(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Borrar secret MikroTik")
        self.geometry("980x620")

        self.mikrotik_node = tk.StringVar()
        self.mikrotik_host = tk.StringVar()
        self.mikrotik_user = tk.StringVar()
        self.mikrotik_pass = tk.StringVar()
        self.mikrotik_port = tk.StringVar(value="8728")

        self.secret_name = tk.StringVar()
        self.validation_text = tk.StringVar(value="Sin validar")

        self._mikrotik_options = {}
        self._loaded_secrets = []
        self._loaded_secrets_set = set()
        self._deleted_log_path = ""

        self._build()

    def _build(self):
        frame_mk = tk.LabelFrame(self, text="Nodo MikroTik")
        frame_mk.pack(fill="x", padx=10, pady=8)

        tk.Label(frame_mk, text="Nodo:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
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

        frame_secret = tk.LabelFrame(self, text="Validacion y borrado")
        frame_secret.pack(fill="x", padx=10, pady=8)

        tk.Label(frame_secret, text="Nombre de secret:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        entry_secret = tk.Entry(frame_secret, textvariable=self.secret_name, width=48)
        entry_secret.grid(row=0, column=1, sticky="w", padx=6, pady=4)
        entry_secret.bind("<KeyRelease>", lambda _e: self._refresh_validation())

        self.lbl_validation = tk.Label(frame_secret, textvariable=self.validation_text, fg="gray")
        self.lbl_validation.grid(row=0, column=2, sticky="w", padx=8, pady=4)

        self.btn_load = tk.Button(frame_secret, text="Cargar secrets", width=16, command=self._on_load_secrets)
        self.btn_load.grid(row=1, column=0, padx=6, pady=6, sticky="w")

        self.btn_delete = tk.Button(
            frame_secret,
            text="Borrar secret",
            width=16,
            command=self._on_delete_secret,
            state="disabled",
        )
        self.btn_delete.grid(row=1, column=1, padx=6, pady=6, sticky="w")

        self.lbl_count = tk.Label(frame_secret, text="Secrets cargados: 0")
        self.lbl_count.grid(row=1, column=2, padx=6, pady=6, sticky="w")

        self.log = scrolledtext.ScrolledText(self, height=24, width=130, state="normal")
        self.log.pack(fill="both", expand=True, padx=10, pady=8)

        self._load_mikrotik_options()

    def _write(self, msg):
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.update_idletasks()

    def _ensure_deleted_log_file(self):
        if self._deleted_log_path:
            return self._deleted_log_path

        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d")
        self._deleted_log_path = os.path.join(log_dir, f"mikrotik_deleted_secrets_{stamp}.csv")

        if not os.path.exists(self._deleted_log_path):
            with open(self._deleted_log_path, "w", encoding="utf-8", newline="") as f:
                f.write("timestamp,node,host,secret_name,status\n")

        return self._deleted_log_path

    def _audit_deleted_secret(self, secret_name: str):
        path = self._ensure_deleted_log_file()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        node = self.mikrotik_node.get().strip().replace(",", " ")
        host = self.mikrotik_host.get().strip().replace(",", " ")
        secret = str(secret_name or "").strip().replace(",", " ")
        with open(path, "a", encoding="utf-8", newline="") as f:
            f.write(f"{timestamp},{node},{host},{secret},DELETED_OK\n")

        self._write(f"[INFO] Auditoria de borrado actualizada: {path}")

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

    def _validate_connection_inputs(self):
        if not self.mikrotik_host.get().strip():
            raise ValueError("Ingresa Host/IP de MikroTik")
        if not self.mikrotik_user.get().strip():
            raise ValueError("Ingresa usuario de MikroTik")
        if not self.mikrotik_port.get().strip().isdigit():
            raise ValueError("Puerto de MikroTik invalido")

    def _refresh_validation(self):
        secret = self.secret_name.get().strip()
        if not secret:
            self.validation_text.set("Sin validar")
            self.lbl_validation.config(fg="gray")
            self.btn_delete.config(state="disabled")
            return

        if secret in self._loaded_secrets_set:
            self.validation_text.set("OK - existe en el nodo")
            self.lbl_validation.config(fg="green")
            self.btn_delete.config(state="normal")
        else:
            self.validation_text.set("No existe en el nodo")
            self.lbl_validation.config(fg="red")
            self.btn_delete.config(state="disabled")

    def _load_secrets_worker(self):
        try:
            self._validate_connection_inputs()
            self._write("[INFO] Consultando /ppp/secret en nodo MikroTik...")
            secrets = list_mikrotik_ppp_secrets(
                host=self.mikrotik_host.get().strip(),
                username=self.mikrotik_user.get().strip(),
                password=self.mikrotik_pass.get(),
                port=int(self.mikrotik_port.get().strip()),
            )
            self._loaded_secrets = secrets
            self._loaded_secrets_set = set(secrets)
            self.lbl_count.config(text=f"Secrets cargados: {len(secrets)}")
            self._refresh_validation()
            self._write(f"[OK] Secrets cargados: {len(secrets)}")
        except Exception as exc:
            self._write(f"[ERROR] Error al cargar secrets: {exc}")
            messagebox.showerror("Error", str(exc), parent=self)
        finally:
            self.btn_load.config(state="normal")

    def _on_load_secrets(self):
        self.btn_load.config(state="disabled")
        threading.Thread(target=self._load_secrets_worker, daemon=True).start()

    def _delete_secret_worker(self, secret: str):
        try:
            self._validate_connection_inputs()
            self._write(f"[INFO] Borrando secret '{secret}'...")
            deleted = delete_mikrotik_ppp_secret(
                host=self.mikrotik_host.get().strip(),
                username=self.mikrotik_user.get().strip(),
                password=self.mikrotik_pass.get(),
                secret_name=secret,
                port=int(self.mikrotik_port.get().strip()),
            )
            if not deleted:
                self._write(f"[WARN] El secret '{secret}' no existe en el nodo")
                messagebox.showwarning("No encontrado", f"El secret '{secret}' no existe en el nodo.", parent=self)
                return

            self._loaded_secrets_set.discard(secret)
            self._loaded_secrets = [s for s in self._loaded_secrets if s != secret]
            self.lbl_count.config(text=f"Secrets cargados: {len(self._loaded_secrets)}")
            self._refresh_validation()
            self._audit_deleted_secret(secret)
            self._write(f"[OK] Secret '{secret}' eliminado correctamente")
            messagebox.showinfo("Exito", f"Secret '{secret}' eliminado correctamente.", parent=self)
        except Exception as exc:
            self._write(f"[ERROR] Error al borrar secret: {exc}")
            messagebox.showerror("Error", str(exc), parent=self)
        finally:
            self.btn_delete.config(state="normal" if self.secret_name.get().strip() in self._loaded_secrets_set else "disabled")

    def _on_delete_secret(self):
        secret = self.secret_name.get().strip()
        if not secret:
            messagebox.showwarning("Falta dato", "Ingresa un nombre de secret.", parent=self)
            return

        if secret not in self._loaded_secrets_set:
            messagebox.showwarning(
                "No validado",
                "El secret no esta en la lista cargada. Carga secrets y valida antes de borrar.",
                parent=self,
            )
            return

        confirmed = messagebox.askyesno(
            "Confirmar borrado",
            f"Se va a borrar el secret '{secret}'.\n\nDeseas continuar?",
            parent=self,
        )
        if not confirmed:
            return

        self.btn_delete.config(state="disabled")
        threading.Thread(target=lambda: self._delete_secret_worker(secret), daemon=True).start()
