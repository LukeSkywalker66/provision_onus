import tkinter as tk
import logging
from tkinter import filedialog, scrolledtext, messagebox

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Provision ONUs (SmartOLT → OLT Huawei)")
        self.geometry("900x520")
        self.csv_path = tk.StringVar()
        self.eliminar_wan_pppoe = tk.BooleanVar()
        self.crear_wan_ip = tk.BooleanVar()
        self.rollback_serviceport = tk.BooleanVar() # borrar serviceport de la vlan150
        self.skip_tr069_configured = tk.BooleanVar() # saltar ONUs ya configuradas con TR-069
        self._build()

    def _build(self):
        frm = tk.Frame(self)
        frm.pack(padx=10, pady=8, fill="x")

        tk.Label(frm, text="Archivo CSV:").pack(side="left")
        tk.Entry(frm, textvariable=self.csv_path, width=70).pack(side="left", padx=6)
        tk.Button(frm, text="Examinar…", command=self.browse).pack(side="left")
        frm_checks = tk.Frame(self)
        frm_checks.pack(padx=10, pady=0, anchor="w", fill="x")
        tk.Checkbutton(frm_checks, text="eliminar wan pppoe", variable=self.eliminar_wan_pppoe).pack(side="left", padx=10)
        tk.Checkbutton(frm_checks, text="crear wan ip", variable=self.crear_wan_ip).pack(side="left", padx=10)
        tk.Checkbutton(frm_checks, text="eliminar serviceport(vlan150)", variable=self.rollback_serviceport).pack(side="left", padx=10)
        tk.Checkbutton(frm_checks, text="skip TR-069 ya configurado", variable=self.skip_tr069_configured).pack(side="left", padx=10)
        self.progress = tk.Label(self, text="0/0 ONUs procesadas")
        self.progress.pack(pady=4)
        self.stats = tk.Label(self, text="", font=("TkDefaultFont", 10, "bold"), fg="darkgreen")
        self.stats.pack(pady=2)
        actions = tk.Frame(self)
        actions.pack(pady=6)
        self.btn_run = tk.Button(actions, text="Ejecutar", width=18)
        self.btn_run.pack(side="left", padx=4)
        self.btn_migration = tk.Button(actions, text="Preparar Migracion BDCOM", width=26)
        self.btn_migration.pack(side="left", padx=4)
        self.btn_zte_injection = tk.Button(actions, text="Inyeccion ZTE", width=18)
        self.btn_zte_injection.pack(side="left", padx=4)
        self.btn_huawei_injection = tk.Button(
            actions,
            text="Inyeccion Huawei (Pre-Aprovisionamiento)",
            width=36,
        )
        self.btn_huawei_injection.pack(side="left", padx=4)

        self.log = scrolledtext.ScrolledText(self, height=24, width=110, state="normal")
        self.log.pack(padx=10, pady=8)
        # Define tags de color
        self.log.tag_config("error", foreground="red")
        self.log.tag_config("warn", foreground="orange")
        self.log.tag_config("ok", foreground="green")
        self.log.tag_config("info", foreground="black")

    def browse(self):
        p = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if p:
            self.csv_path.set(p)

    def write_log(self, msg):
        # Mostrar en GUI
        # self.log.insert(tk.END, msg + "\n")
        # self.log.see(tk.END)
        # self.log.update_idletasks()
        # Persistir en archivo con el nivel apropiado
        try:
            # Mostrar en GUI con color según el tipo de mensaje
            if msg.startswith("[ERROR]"):
                self.log.insert(tk.END, msg + "\n", "error")
                logging.error(msg)
            elif msg.startswith("[WARN]"):
                self.log.insert(tk.END, msg + "\n", "warn")
                logging.warning(msg)
            elif msg.startswith("[OK]"):
                self.log.insert(tk.END, msg + "\n", "ok")
                logging.info(msg)
            else:
                self.log.insert(tk.END, msg + "\n", "info")
                logging.info(msg)
            self.log.see(tk.END)
            self.log.update_idletasks()
        except Exception:
            pass

    def error(self, title, msg):
        messagebox.showerror(title, msg)
        logging.error(f"{title}: {msg}")
    def update_progress(self, done, total, avg=None, eta=None, provisioned=None, skipped=None):
        text = f"{done}/{total} ONUs procesadas"
        if avg and eta:
            text += f" – Promedio: {avg:.1f}s – ETA: {int(eta//60)}m{int(eta%60)}s"
        self.progress.config(text=text)
        if provisioned is not None or skipped is not None:
            stats_text = ""
            if provisioned is not None:
                stats_text += f"✓ Provisioned: {provisioned}"
            if skipped is not None:
                if stats_text:
                    stats_text += "  •  "
                stats_text += f"⊘ Skipped: {skipped}"
            self.stats.config(text=stats_text)
        self.progress.update_idletasks()
        self.stats.update_idletasks()


