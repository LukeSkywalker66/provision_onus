import threading
import os, logging
import sys  # opcional si algún día lo empaquetas con PyInstaller
import time
import pathlib
import json
import time

from gui import App
from csv_logic import parse_smartolt_csv
from ssh_client import connect_olt, close_olt
from config import OLT_MAP
from omci import provision_onu, rollback_onu_serviceport   # NUEVO
from datetime import datetime



# Parámetros configurables
RECONNECT_THRESHOLD = 200
RECONNECT_DELAY = 2
RECONNECT_RETRIES = 3
RECONNECT_BACKOFF = 5
CHECKPOINT_DIR = pathlib.Path("checkpoints")
CHECKPOINT_DIR.mkdir(exist_ok=True)

class SessionManager:
    def __init__(self, olt_name, connect_fn, close_fn, logger, threshold=RECONNECT_THRESHOLD,
                 delay=RECONNECT_DELAY, retries=RECONNECT_RETRIES, backoff=RECONNECT_BACKOFF, post_connect_hook=None):
        self.olt_name = olt_name
        self.connect_fn = connect_fn
        self.close_fn = close_fn
        self.logger = logger
        self.threshold = threshold
        self.delay = delay
        self.retries = retries
        self.backoff = backoff
        self.post_connect_hook = post_connect_hook
        self.conn = None
        self.counter = 0
        self.cks_path = CHECKPOINT_DIR / f"{self._safe_name(olt_name)}.ckp"
        


    def _safe_name(self, name):
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

    def load_checkpoint(self):
        if self.cks_path.exists():
            try:
                val = int(self.cks_path.read_text().strip())
                self.counter = val
                self.logger(f"[INFO] Cargado checkpoint {self.counter} para {self.olt_name}")
            except Exception as e:
                self.logger(f"[WARN] No se pudo leer checkpoint {self.cks_path}: {e}")

    def save_checkpoint(self):
        try:
            self.cks_path.write_text(str(self.counter))
        except Exception as e:
            self.logger(f"[WARN] Error guardando checkpoint {self.cks_path}: {e}")

    def open(self, *connect_args, **connect_kwargs):
        last_exc = None
        for attempt in range(1, self.retries + 1):
            try:
                self.conn = self.connect_fn(*connect_args, **connect_kwargs)
                self.logger(f"[OK] Conectado a {self.olt_name} (intent {attempt})")
                if self.post_connect_hook:
                    self.post_connect_hook(self.olt_name, self.conn, self.logger)
                return
            except Exception as e:
                last_exc = e
                self.logger(f"[WARN] Falló conexión a {self.olt_name} (intent {attempt}): {e}")
                time.sleep(self.backoff)
        self.logger(f"[ERROR] No se pudo conectar a {self.olt_name} después de {self.retries} intentos")
        raise last_exc

    def close(self):
        try:
            if self.conn:
                self.close_fn(self.conn)
                self.logger(f"[.] Desconectado de {self.olt_name}")
        except Exception as e:
            self.logger(f"[WARN] Error cerrando conexión a {self.olt_name}: {e}")
        finally:
            self.conn = None

    def increment_and_rotate(self, connect_args=(), connect_kwargs={}):
        # incrementar contador y decidir si rotar
        self.counter += 1
        # persistir cada N (puede ajustarse)
        if self.counter % 10 == 0:
            self.save_checkpoint()
        if self.threshold > 0 and (self.counter % self.threshold) == 0:
            self.logger(f"[INFO] Umbral {self.threshold} alcanzado ({self.counter}). Rotando conexión.")
            try:
                self.close()
            finally:
                time.sleep(self.delay)
                self.open(*connect_args, **connect_kwargs)
        return self.conn

def init_logging():
    os.makedirs("logs", exist_ok=True)
    log_filename = datetime.now().strftime("logs/ejecucion_%Y%m%d-%H%M%S.log")
    logging.basicConfig(
        filename=log_filename,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        encoding="utf-8"
    )
    logging.getLogger().setLevel(logging.INFO)
    logging.captureWarnings(True)
    return log_filename
def enter_config_mode(olt_name, conn, logger):
    try:
        match olt_name:
            case "ZTE C600":
                out = conn.send_command_timing("configure terminal")
                logger(out.strip() if out.strip() else "Modo Configuración activo")
            case ("OLT(San_Jose)" | "Villa Dolores 2" | "OLTHUAWEI"):
                out = conn.send_command_timing("enable")
                logger(out.strip() if out.strip() else "Modo Privilegiado activo #")
                out = conn.send_command_timing("config")
                logger(out.strip() if out.strip() else "Modo Configuración activo")
            case _:
                logger(f"[WARN] No se definió modo configuración para {olt_name}")
    except Exception as e:
        logger(f"[ERROR] Falló entrada a modo configuración en {olt_name}: {e}")

def main():
    ui = App()

    # Inicializar logging antes de cualquier procesamiento
    log_path = init_logging()
    ui.write_log(f"[log] Registrando en: {log_path}")

    def run():
        path = ui.csv_path.get()
        if not path:
            ui.error("CSV requerido", "Selecciona un archivo CSV.")
            return
        try:
            records = parse_smartolt_csv(path)
        except Exception as e:
            ui.error("CSV inválido", str(e))
            return
        if not records:
            ui.error("CSV vacío", "No hay ONUs válidas para procesar.")
            return

        ui.write_log(f"[+] Procesando {len(records)} ONUs desde {path}")
        ui.update_progress(0, len(records))

        # Agrupar por OLT para abrir/cerrar SSH por cada OLT una sola vez
        by_olt = {}
        for r in records:
            by_olt.setdefault(r["olt_name"], []).append(r)

        for olt_name, items in by_olt.items():
            cfg = OLT_MAP.get(olt_name)
            if not cfg:
                ui.write_log(f"[WARN] OLT '{olt_name}' no mapeada en config.py. Saltando.")
                continue
            ui.write_log(f"[+] Preparando procesado para {olt_name} ({cfg['ip']})")

            mgr = SessionManager(
                olt_name,
                lambda ip, user, pw, port: connect_olt(ip, user, pw, port),
                close_olt,
                ui.write_log,
                threshold=RECONNECT_THRESHOLD,
                post_connect_hook=enter_config_mode
            )

            mgr.load_checkpoint()
            try:
                mgr.open(cfg["ip"], cfg["user"], cfg["password"], cfg.get("port", 22))
            except Exception:
                ui.write_log(f"[ERROR] No se pudo conectar a {olt_name}: abortando OLT")
                continue

            # Entrar en modos según vendor una sola vez tras abrir conexión
            conn = mgr.conn
            # match olt_name:
            #     case "ZTE C600":
            #         out = conn.send_command_timing("configure terminal")
            #         ui.write_log(out.strip() if out.strip() else "Modo Configuración activo")
            #     case ("OLT(San_Jose)" | "Villa Dolores 2" | "OLTHUAWEI"):
            #         out = conn.send_command_timing("enable")
            #         ui.write_log(out.strip() if out.strip() else "Modo Privilegiado activo #")
            #         out = conn.send_command_timing("config")
            #         ui.write_log(out.strip() if out.strip() else "Modo Configuración activo")

            # Procesado de items con rotación por N
            total_items = len(items)
            done_local = 0
            elapsed_total = 0.0
            for r in items:
                start = time.time()
                try:
                    conn = mgr.conn  # conexión vigente
                    if ui.rollback_serviceport.get():
                        rollback_onu_serviceport(
                            conn,
                            olt_name,
                            r["slot"],
                            r["port"],
                            r["onu_id"],
                            r["vlan"],
                            ui.write_log
                        )
                    else:
                        provision_onu(
                            conn,
                            olt_name,
                            r["slot"],
                            r["port"],
                            r["onu_id"],
                            r["onu_type"],
                            r.get("pppoe_user"),
                            r["vlan"],
                            ui.write_log,
                            eliminar_wan_pppoe=ui.eliminar_wan_pppoe.get(),
                            crear_wan_ip=ui.crear_wan_ip.get()
                        )
                except Exception as e:
                    ui.write_log(f"[ERROR] Error procesando {r.get('onu_id')} en {olt_name}: {e}")
                finally:
                    elapsed = time.time() - start
                    elapsed_total += elapsed
                    done_local += 1
                    # actualizar progreso global: sum de items procesados por OLT + mgr.counter para ETA aproximada
                    ui.update_progress(done_local, total_items, elapsed_total / done_local, (elapsed_total / done_local) * (total_items - done_local))
                    # incrementar contador global del manager y rotar si hace falta
                    mgr.increment_and_rotate(connect_args=(cfg["ip"], cfg["user"], cfg["password"], cfg.get("port", 22)))
            # Fin for r in items

            # Guardar checkpoint final y cerrar
            mgr.save_checkpoint()
            mgr.close()
            # cfg = OLT_MAP.get(olt_name)
            # if not cfg:
            #     ui.write_log(f"[WARN] OLT '{olt_name}' no mapeada en config.py. Saltando.")
            #     continue
            # ui.write_log(f"[+] Conectando a {olt_name} ({cfg['ip']})")
            # try:
            #     conn = connect_olt(cfg["ip"], cfg["user"], cfg["password"], cfg["port"])
                
            #     ui.write_log(f"[OK] Conectado a {olt_name} ({cfg['ip']})")
            # except Exception as e:
            #     ui.write_log(f"[ERROR] No se pudo conectar a {olt_name}: {e}")
            #     continue
            # match olt_name:
            #     case "ZTE C600":
            #         conn.send_command_timing("configure terminal")
            #         ui.write_log(out.strip() if out.strip() else "Modo Configuración activo")
            #     case ("OLT(San_Jose)" | "Villa Dolores 2" | "OLTHUAWEI"):
            #         out = conn.send_command_timing("enable")
            #         ui.write_log(out.strip() if out.strip() else "Modo Privilegiado activo #")
            #         out = conn.send_command_timing("config")
            #         ui.write_log(out.strip()if out.strip() else "Modo Configuración activo")
            
            # done = 0
            # elapsed_total = 0
            # for r in items:
            #     start = time.time()
            #     try:
            #         if ui.rollback_serviceport.get():   # NUEVO
            #             rollback_onu_serviceport(
            #                 conn,
            #                 olt_name,
            #                 r["slot"],
            #                 r["port"],
            #                 r["onu_id"],
            #                 r["vlan"],
            #                 ui.write_log
            #             )
            #         else:
            #             provision_onu(
            #                 conn,
            #                 olt_name,
            #                 r["slot"],
            #                 r["port"],
            #                 r["onu_id"],
            #                 r["onu_type"],
            #                 r["pppoe_user"],
            #                 r["vlan"],
            #                 ui.write_log,
            #                 eliminar_wan_pppoe=ui.eliminar_wan_pppoe.get(),
            #                 crear_wan_ip=ui.crear_wan_ip.get()
            #             )
            #     finally:
            #         elapsed = time.time() - start
            #         elapsed_total += elapsed
            #         done += 1
            #         #ui.update_progress(done, len(records))
            #         avg = elapsed_total / done
            #         remaining = len(records) - done
            #         eta = avg * remaining
            #         ui.update_progress(done, len(records), avg, eta)
            # # for r in items:
            # #     provision_onu(conn, olt_name, r["slot"], r["port"], r["onu_id"], r["onu_type"], r["pppoe_user"], r["vlan"], ui.write_log, eliminar_wan_pppoe=ui.eliminar_wan_pppoe.get(), crear_wan_ip=ui.crear_wan_ip.get(), eliminar_serviceport=ui.eliminar_serviceport.get())
                
            # close_olt(conn)
            # ui.write_log(f"[.] Desconectado de {olt_name}")

    # Wire del botón Ejecutar
    def on_click():
        ui.btn_run.config(state="disabled")
        t = threading.Thread(target=lambda: (run(), ui.btn_run.config(state="normal")))
        t.daemon = True
        t.start()

    ui.btn_run.configure(command=on_click)
    ui.mainloop()

if __name__ == "__main__":
    main()
