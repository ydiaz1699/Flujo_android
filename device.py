"""
device.py - Abstraccion del dispositivo Android.

Combina ADB + UITree para hacer tap inteligente:
busca el elemento, encuentra el contenedor clickeable padre,
calcula su centro y toca ahi.
"""

import subprocess
import time
import logging
from pathlib import Path
from typing import Optional

from node import UINode
from ui import UITree

logger = logging.getLogger(__name__)


class DeviceError(Exception):
    """Error de comunicacion con el dispositivo."""
    pass


class Device:
    """
    Abstraccion de un dispositivo Android TV.

    Combina operaciones ADB de bajo nivel con el arbol de UI
    para ejecutar acciones inteligentes.
    """

    def __init__(self, serial=None, timeout=30):
        """
        Args:
            serial: Serial del dispositivo (None = unico conectado).
            timeout: Timeout en segundos para comandos ADB.
        """
        self.serial = serial
        self.timeout = timeout
        self.tree = UITree()
        self._dumps_dir = Path("dumps")
        self._dumps_dir.mkdir(exist_ok=True)
        self._dump_count = 0

    # ─── ADB bajo nivel ───────────────────────────────────────────────

    def _adb(self, command, timeout=None):
        """Ejecuta un comando ADB."""
        cmd = ["adb"]
        if self.serial:
            cmd += ["-s", self.serial]

        if isinstance(command, str):
            cmd += command.split()
        else:
            cmd += command

        timeout = timeout or self.timeout
        logger.debug(f"$ {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            if result.returncode != 0 and result.stderr.strip():
                logger.warning(f"stderr: {result.stderr.strip()}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise DeviceError(f"Timeout: {' '.join(cmd)}")
        except FileNotFoundError:
            raise DeviceError("ADB no encontrado en PATH")

    def shell(self, command):
        """Ejecuta un comando shell en el dispositivo."""
        return self._adb(f"shell {command}")


    # ─── Conexion ─────────────────────────────────────────────────────

    def is_connected(self):
        """Verifica si hay un dispositivo conectado."""
        output = self._adb("devices")
        lines = [l for l in output.splitlines()[1:] if l.strip() and "device" in l]
        if self.serial:
            return any(self.serial in l for l in lines)
        return len(lines) > 0

    def wait_for_device(self, max_wait=60):
        """Espera a que un dispositivo este disponible."""
        start = time.time()
        while time.time() - start < max_wait:
            if self.is_connected():
                return True
            time.sleep(2)
        raise DeviceError(f"Sin dispositivo en {max_wait}s")

    def info(self):
        """Informacion del dispositivo."""
        return {
            "model": self.shell("getprop ro.product.model"),
            "android": self.shell("getprop ro.build.version.release"),
            "sdk": self.shell("getprop ro.build.version.sdk"),
            "resolution": self.shell("wm size").replace("Physical size: ", ""),
        }

    # ─── UI Dump ──────────────────────────────────────────────────────

    def refresh(self, save_as=None):
        """
        Refresca el arbol de UI.

        1. Ejecuta uiautomator dump.
        2. Descarga el XML.
        3. Parsea y construye el arbol.

        Args:
            save_as: Nombre para guardar el dump (sin extension).

        Returns:
            UITree actualizado.
        """
        self._dump_count += 1

        # Nombre local
        name = save_as or f"dump_{self._dump_count:03d}"
        local_path = self._dumps_dir / f"{name}.xml"

        # Dump + pull
        self._adb("shell uiautomator dump /sdcard/ui.xml")
        self._adb(f"pull /sdcard/ui.xml {local_path}")

        # Parsear
        self.tree.parse_file(str(local_path))
        logger.info(f"UI refrescada: {self.tree.node_count} nodos")
        return self.tree


    # ─── Tap inteligente ──────────────────────────────────────────────

    def tap(self, x, y):
        """Tap en coordenadas."""
        self._adb(f"shell input tap {x} {y}")
        logger.debug(f"tap({x}, {y})")

    def click_text(self, text, exact=True, wait=2.0, refresh=True):
        """
        Busca un texto en la UI y toca su contenedor clickeable.

        Flujo:
        1. Refresh UI (dump).
        2. Buscar nodo con el texto.
        3. Subir al padre clickeable.
        4. Calcular centro.
        5. Tap.

        Args:
            text: Texto visible del elemento.
            exact: Coincidencia exacta o parcial.
            wait: Segundos a esperar despues del tap.
            refresh: Si refrescar la UI antes.

        Returns:
            UINode en el que se hizo tap.

        Raises:
            DeviceError: Si no se encuentra el texto.
        """
        if refresh:
            self.refresh()

        # Buscar nodo
        results = self.tree.find_text(text, exact=exact)
        node = results.first()

        if node is None:
            available = self.tree.get_all_texts()
            raise DeviceError(
                f"Texto '{text}' no encontrado.\n"
                f"Disponibles: {available}"
            )

        # Obtener target clickeable
        target, (cx, cy) = node.get_tap_target()
        logger.info(f"click_text('{text}') -> {target.display_name} ({cx},{cy})")

        self.tap(cx, cy)
        time.sleep(wait)
        return target

    def click_id(self, resource_id, wait=2.0, refresh=True):
        """
        Busca un elemento por ID y toca su contenedor clickeable.

        Args:
            resource_id: ID completo o parcial.
            wait: Segundos a esperar.
            refresh: Si refrescar la UI antes.

        Returns:
            UINode en el que se hizo tap.
        """
        if refresh:
            self.refresh()

        results = self.tree.find_id(resource_id, partial=True)
        node = results.first()

        if node is None:
            raise DeviceError(f"ID '{resource_id}' no encontrado.")

        target, (cx, cy) = node.get_tap_target()
        logger.info(f"click_id('{resource_id}') -> ({cx},{cy})")

        self.tap(cx, cy)
        time.sleep(wait)
        return target

    def click_node(self, node, wait=2.0):
        """Toca directamente un UINode (busca su target clickeable)."""
        target, (cx, cy) = node.get_tap_target()
        self.tap(cx, cy)
        time.sleep(wait)
        return target


    # ─── Esperas inteligentes ─────────────────────────────────────────

    def wait_for_text(self, text, timeout=15, interval=2):
        """Espera hasta que un texto aparezca en pantalla."""
        start = time.time()
        while time.time() - start < timeout:
            self.refresh()
            node = self.tree.find_text(text, exact=False).first()
            if node:
                return node
            time.sleep(interval)
        raise DeviceError(f"Texto '{text}' no aparecio en {timeout}s")

    def wait_for_id(self, resource_id, timeout=15, interval=2):
        """Espera hasta que un elemento con cierto ID aparezca."""
        start = time.time()
        while time.time() - start < timeout:
            self.refresh()
            node = self.tree.find_id(resource_id).first()
            if node:
                return node
            time.sleep(interval)
        raise DeviceError(f"ID '{resource_id}' no aparecio en {timeout}s")

    # ─── Input (teclado, dpad) ────────────────────────────────────────

    def key(self, keycode):
        """Envia un keyevent."""
        self._adb(f"shell input keyevent {keycode}")

    def back(self):
        self.key(4)

    def home(self):
        self.key(3)

    def dpad_up(self):
        self.key(19)

    def dpad_down(self):
        self.key(20)

    def dpad_left(self):
        self.key(21)

    def dpad_right(self):
        self.key(22)

    def dpad_center(self):
        """OK / Enter en el control remoto."""
        self.key(23)

    def enter(self):
        self.key(66)

    def menu(self):
        self.key(82)

    def text_input(self, text):
        """Escribe texto."""
        safe = text.replace(" ", "%s")
        self._adb(f"shell input text {safe}")

    # ─── Gestos ───────────────────────────────────────────────────────

    def swipe(self, x1, y1, x2, y2, duration_ms=300):
        """Desliza de un punto a otro."""
        self._adb(f"shell input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    def scroll_down(self):
        self.swipe(698, 500, 698, 200, 300)

    def scroll_up(self):
        self.swipe(698, 200, 698, 500, 300)

    def scroll_right(self):
        self.swipe(1000, 360, 400, 360, 300)

    def scroll_left(self):
        self.swipe(400, 360, 1000, 360, 300)

    # ─── Gestion de apps ──────────────────────────────────────────────

    def start_app(self, package):
        """Abre una app."""
        self._adb(
            f"shell monkey -p {package} "
            f"-c android.intent.category.LAUNCHER 1"
        )

    def stop_app(self, package):
        """Fuerza cierre de una app."""
        self._adb(f"shell am force-stop {package}")

    def is_app_foreground(self, package):
        """Verifica si la app esta en primer plano."""
        output = self._adb("shell dumpsys window windows")
        return package in output

    # ─── Screenshots ──────────────────────────────────────────────────

    def screenshot(self, local_path):
        """Captura de pantalla."""
        self._adb("shell screencap -p /sdcard/tmp_screen.png")
        self._adb(f"pull /sdcard/tmp_screen.png {local_path}")
        self._adb("shell rm /sdcard/tmp_screen.png")
        logger.info(f"Screenshot: {local_path}")

    # ─── Utilidades ───────────────────────────────────────────────────

    def sleep(self, seconds):
        """Pausa."""
        time.sleep(seconds)

    def pull(self, remote, local):
        """Descarga archivo del dispositivo."""
        self._adb(f"pull {remote} {local}")

    def push(self, local, remote):
        """Sube archivo al dispositivo."""
        self._adb(f"push {local} {remote}")
