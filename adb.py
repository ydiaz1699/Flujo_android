"""
adb.py - Wrapper completo para comandos ADB.

Proporciona una interfaz Python limpia para interactuar con dispositivos
Android TV via ADB (Android Debug Bridge).
"""

import subprocess
import time
import logging

logger = logging.getLogger(__name__)


class ADBError(Exception):
    """Error al ejecutar un comando ADB."""
    pass


class ADB:
    """Clase wrapper para comandos ADB."""

    def __init__(self, device_serial=None, timeout=30):
        """
        Args:
            device_serial: Serial del dispositivo (None = usar el unico conectado).
            timeout: Timeout en segundos para comandos ADB.
        """
        self.device_serial = device_serial
        self.timeout = timeout

    @property
    def _base_cmd(self):
        """Construye el comando base de ADB con serial opcional."""
        cmd = ["adb"]
        if self.device_serial:
            cmd += ["-s", self.device_serial]
        return cmd

    def run(self, command, timeout=None):
        """
        Ejecuta un comando ADB generico.

        Args:
            command: Comando como string (se splitea) o lista.
            timeout: Override del timeout por defecto.

        Returns:
            stdout del comando.

        Raises:
            ADBError: Si el comando falla.
        """
        if isinstance(command, str):
            cmd = self._base_cmd + command.split()
        else:
            cmd = self._base_cmd + command

        timeout = timeout or self.timeout

        logger.debug(f"ADB: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0 and result.stderr.strip():
                logger.warning(f"ADB stderr: {result.stderr.strip()}")

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise ADBError(f"Timeout ({timeout}s) ejecutando: {' '.join(cmd)}")
        except FileNotFoundError:
            raise ADBError(
                "ADB no encontrado. Asegurate de tener Android SDK "
                "instalado y 'adb' en el PATH."
            )

    # ─── Verificacion de conexion ─────────────────────────────────────

    def is_connected(self):
        """Verifica si hay un dispositivo conectado."""
        output = self.run("devices")
        lines = [
            l for l in output.splitlines()[1:]
            if l.strip() and "device" in l
        ]
        if self.device_serial:
            return any(self.device_serial in l for l in lines)
        return len(lines) > 0

    def wait_for_device(self, max_wait=60):
        """
        Espera hasta que un dispositivo este disponible.

        Args:
            max_wait: Segundos maximos de espera.

        Raises:
            ADBError: Si no se conecta en el tiempo limite.
        """
        logger.info("Esperando dispositivo ADB...")
        start = time.time()
        while time.time() - start < max_wait:
            if self.is_connected():
                logger.info("Dispositivo conectado.")
                return True
            time.sleep(2)
        raise ADBError(f"No se detecto dispositivo en {max_wait}s.")

    def get_device_info(self):
        """Obtiene informacion basica del dispositivo."""
        return {
            "model": self.run("shell getprop ro.product.model"),
            "android_version": self.run("shell getprop ro.build.version.release"),
            "sdk": self.run("shell getprop ro.build.version.sdk"),
            "resolution": self.run("shell wm size").replace("Physical size: ", ""),
            "density": self.run("shell wm density").replace("Physical density: ", ""),
        }

    # ─── Entrada (tap, swipe, teclas) ─────────────────────────────────

    def tap(self, x, y):
        """Toca en las coordenadas (x, y)."""
        self.run(f"shell input tap {x} {y}")
        logger.debug(f"Tap en ({x}, {y})")

    def long_press(self, x, y, duration_ms=1000):
        """Mantiene presionado en (x, y) durante duration_ms."""
        self.run(f"shell input swipe {x} {y} {x} {y} {duration_ms}")

    def swipe(self, x1, y1, x2, y2, duration_ms=300):
        """Desliza de (x1,y1) a (x2,y2)."""
        self.run(f"shell input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    def key(self, keycode):
        """
        Envia un keyevent.

        Keycodes comunes:
            KEYCODE_HOME = 3
            KEYCODE_BACK = 4
            KEYCODE_DPAD_UP = 19
            KEYCODE_DPAD_DOWN = 20
            KEYCODE_DPAD_LEFT = 21
            KEYCODE_DPAD_RIGHT = 22
            KEYCODE_DPAD_CENTER / ENTER = 23 / 66
            KEYCODE_MENU = 82
        """
        self.run(f"shell input keyevent {keycode}")
        logger.debug(f"Key: {keycode}")

    def text(self, text_input):
        """Escribe texto (para campos de busqueda, etc)."""
        # Escapar espacios para shell
        safe = text_input.replace(" ", "%s")
        self.run(f"shell input text {safe}")

    # ─── Keycodes de acceso rapido (Android TV) ───────────────────────

    def home(self):
        self.key(3)

    def back(self):
        self.key(4)

    def dpad_up(self):
        self.key(19)

    def dpad_down(self):
        self.key(20)

    def dpad_left(self):
        self.key(21)

    def dpad_right(self):
        self.key(22)

    def dpad_center(self):
        """Equivale a presionar OK/Enter en el control remoto."""
        self.key(23)

    def enter(self):
        self.key(66)

    def menu(self):
        self.key(82)

    # ─── Gestion de aplicaciones ──────────────────────────────────────

    def start_app(self, package, wait=True):
        """
        Abre una aplicacion por su package name.

        Args:
            package: Nombre del paquete (ej: com.android.mgandroid).
            wait: Si espera a que la actividad se inicie.
        """
        logger.info(f"Abriendo app: {package}")
        self.run(
            f"shell monkey -p {package} "
            f"-c android.intent.category.LAUNCHER 1"
        )

    def force_stop(self, package):
        """Fuerza el cierre de una aplicacion."""
        self.run(f"shell am force-stop {package}")
        logger.info(f"App detenida: {package}")

    def is_app_running(self, package):
        """Verifica si una app esta en primer plano."""
        output = self.run("shell dumpsys window windows")
        return package in output

    def get_current_activity(self):
        """Obtiene la actividad actual en pantalla."""
        output = self.run(
            "shell dumpsys activity activities | grep mResumedActivity"
        )
        return output

    # ─── UI Automator ─────────────────────────────────────────────────

    def dump_ui(self, remote_path="/sdcard/ui.xml"):
        """
        Ejecuta uiautomator dump en el dispositivo.

        Args:
            remote_path: Ruta en el dispositivo donde se guarda el XML.

        Returns:
            La ruta remota del archivo.
        """
        self.run(f"shell uiautomator dump {remote_path}")
        logger.debug(f"UI dump guardado en: {remote_path}")
        return remote_path

    def pull_file(self, remote_path, local_path):
        """
        Descarga un archivo del dispositivo al PC.

        Args:
            remote_path: Ruta en el dispositivo.
            local_path: Ruta local destino.
        """
        self.run(f"pull {remote_path} {local_path}")
        logger.debug(f"Archivo descargado: {remote_path} -> {local_path}")

    def push_file(self, local_path, remote_path):
        """Sube un archivo al dispositivo."""
        self.run(f"push {local_path} {remote_path}")

    # ─── Screenshots ──────────────────────────────────────────────────

    def screenshot(self, local_path, remote_path="/sdcard/tmp_screen.png"):
        """
        Toma una captura de pantalla.

        Args:
            local_path: Ruta local donde guardar la imagen.
            remote_path: Ruta temporal en el dispositivo.
        """
        self.run(f"shell screencap -p {remote_path}")
        self.pull_file(remote_path, local_path)
        self.run(f"shell rm {remote_path}")
        logger.info(f"Screenshot guardado: {local_path}")

    # ─── Utilidades ───────────────────────────────────────────────────

    def sleep(self, seconds):
        """Pausa con log (wrapper de time.sleep)."""
        logger.debug(f"Esperando {seconds}s...")
        time.sleep(seconds)

    def shell(self, command):
        """Ejecuta un comando shell directamente en el dispositivo."""
        return self.run(f"shell {command}")
