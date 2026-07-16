"""
mgandroid.py - API de alto nivel para MGAndroid.

Proporciona metodos semanticos para interactuar con la app:
go_movies(), go_live(), open_history(), play_first_result(), etc.

Uso:
    from mgandroid import MGAndroid

    mg = MGAndroid()
    mg.open()
    mg.go_movies()
    mg.go_live()
    mg.open_history()
    mg.back_home()
"""

import time
import logging
from typing import Dict, List, Optional

from device import Device, DeviceError
from app import App
from node import UINode

logger = logging.getLogger(__name__)


class MGAndroid:
    """
    Controlador de alto nivel para MGAndroid.

    Ejemplo:
        mg = MGAndroid()
        mg.open()
        mg.go_movies()
        for item in mg.current_items():
            print(item.title)
    """

    # Mapeo de categorias (nombre interno -> posibles textos en UI)
    CATEGORY_MAP = {
        "live": "VIVO",
        "series": "SERIE",
        "movies": "PELÍCULA",
        "anime": "ANIME",
        "special": "ESPECIAL",
    }

    # IDs conocidos de la app
    IDS = {
        "settings": "iv_setting",
        "history": "history_btn",
        "favorites": "fav_btn",
        "banner": "banner_root",
        "player": "main_focus_root",
        "live_title": "tv_live_title",
        "speed": "tv_main_speed",
        "category_name": "vod_category_name",
        "logo": "iv_logo",
        "version": "tv_version",
    }

    def __init__(self, device=None, serial=None):
        """
        Args:
            device: Instancia de Device (crea una nueva si no se da).
            serial: Serial del dispositivo ADB.
        """
        self.device = device or Device(serial=serial)
        self.app = App(self.device)


    # ─── Ciclo de vida ────────────────────────────────────────────────

    def open(self, wait=5.0):
        """Abre MGAndroid y espera a que este lista."""
        self.app.open(wait=wait)
        self.app.wait_ready(timeout=20)

    def close(self):
        """Cierra MGAndroid."""
        self.app.close()

    def restart(self):
        """Reinicia la app."""
        self.app.restart()
        self.app.wait_ready()

    # ─── Navegacion por categorias ────────────────────────────────────

    def go_live(self, wait=3.0):
        """Navega a la seccion VIVO (TV en vivo)."""
        return self._go_category("VIVO", wait)

    def go_series(self, wait=3.0):
        """Navega a la seccion SERIE."""
        return self._go_category("SERIE", wait)

    def go_movies(self, wait=3.0):
        """Navega a la seccion PELICULA."""
        return self._go_category("PELÍCULA", wait)

    def go_anime(self, wait=3.0):
        """Navega a la seccion ANIME."""
        return self._go_category("ANIME", wait)

    def go_special(self, wait=3.0):
        """Navega a la seccion ESPECIAL."""
        return self._go_category("ESPECIAL", wait)

    def _go_category(self, text, wait=3.0):
        """
        Navega a una categoria por texto.

        Busca el texto, sube al padre clickeable, tap.
        """
        self.app.ensure_home()
        self.device.click_text(text, wait=wait)
        logger.info(f"Navegado a: {text}")
        return text

    def categories(self, refresh=True):
        """
        Obtiene las categorias disponibles.

        Returns:
            Dict {nombre: UINode}
        """
        if refresh:
            self.app.ensure_home()
            self.device.refresh()
        return self.device.tree.get_categories()

    # ─── Acciones rapidas ─────────────────────────────────────────────

    def open_settings(self, wait=2.0):
        """Abre el panel de ajustes."""
        self.device.click_id(self.IDS["settings"], wait=wait)

    def open_history(self, wait=2.0):
        """Abre el historial de reproduccion."""
        self.device.click_id(self.IDS["history"], wait=wait)

    def open_favorites(self, wait=2.0):
        """Abre los favoritos."""
        self.device.click_id(self.IDS["favorites"], wait=wait)

    def click_banner(self, wait=3.0):
        """Toca el banner principal."""
        self.device.click_id(self.IDS["banner"], wait=wait)

    def click_player(self, wait=2.0):
        """Toca el reproductor principal (fullscreen)."""
        self.device.click_id(self.IDS["player"], wait=wait)


    # ─── Navegacion generica ──────────────────────────────────────────

    def back(self, times=1, wait=1.0):
        """Presiona back N veces."""
        for _ in range(times):
            self.device.back()
            time.sleep(wait)

    def back_home(self):
        """Vuelve a la pantalla principal."""
        self.app.ensure_home()

    # ─── Canales en vivo ──────────────────────────────────────────────

    def current_channel(self):
        """Obtiene el nombre del canal en vivo actual."""
        self.device.refresh()
        return self.device.tree.get_live_channel()

    def channel_up(self, wait=2.0):
        """Cambia al canal siguiente."""
        self.device.dpad_up()
        time.sleep(wait)

    def channel_down(self, wait=2.0):
        """Cambia al canal anterior."""
        self.device.dpad_down()
        time.sleep(wait)

    def list_channels(self, count=10, wait=2.0):
        """
        Recorre N canales y obtiene sus nombres.

        Args:
            count: Cantidad de canales a recorrer.
            wait: Espera entre cambios de canal.

        Returns:
            Lista de nombres de canales.
        """
        channels = []
        for i in range(count):
            self.device.refresh()
            name = self.device.tree.get_live_channel()
            channels.append(name or f"Canal #{i+1}")
            logger.info(f"  Canal {i+1}: {name}")
            self.channel_down(wait=wait)
        return channels

    # ─── Busqueda ─────────────────────────────────────────────────────

    def search(self, query, wait=3.0):
        """
        Busca contenido en la app.

        Nota: Requiere que la app tenga campo de busqueda accesible.
        """
        # Intentar encontrar campo de busqueda
        try:
            self.device.click_id("search", wait=1.0)
            time.sleep(1)
            self.device.text_input(query)
            self.device.enter()
            time.sleep(wait)
            logger.info(f"Buscando: {query}")
        except DeviceError:
            logger.warning("No se encontro campo de busqueda")

    # ─── Reproduccion ─────────────────────────────────────────────────

    def play_first_result(self, wait=5.0):
        """
        Reproduce el primer item visible en la pantalla actual.

        Busca el primer elemento clickeable grande (probable poster/thumbnail)
        y lo toca.
        """
        self.device.refresh()

        # Buscar elementos clickeables con area razonable (no botones chicos)
        clickable = self.device.tree.select().clickable().larger_than(5000)
        target = clickable.first()

        if target:
            self.device.click_node(target, wait=wait)
            logger.info(f"Reproduciendo: {target.display_name}")
        else:
            # Fallback: dpad center
            self.device.dpad_center()
            time.sleep(wait)

    # ─── Info ─────────────────────────────────────────────────────────

    def version(self):
        """Version de la app."""
        return self.app.get_version()

    def speed(self):
        """Velocidad de red actual."""
        self.device.refresh()
        return self.device.tree.get_speed()

    def status(self):
        """Estado completo actual."""
        self.device.refresh()
        return {
            "running": self.app.is_running(),
            "on_home": self.app.is_on_home(refresh=False),
            "version": self.device.tree.get_version(),
            "channel": self.device.tree.get_live_channel(),
            "speed": self.device.tree.get_speed(),
            "categories": list(self.device.tree.get_categories().keys()),
            "texts": self.device.tree.get_all_texts(),
        }

    # ─── Dump y captura ───────────────────────────────────────────────

    def dump(self, save_as=None):
        """Genera un dump de la UI y retorna el arbol."""
        return self.device.refresh(save_as=save_as)

    def screenshot(self, path="screenshots/capture.png"):
        """Toma captura de pantalla."""
        from pathlib import Path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.device.screenshot(path)

    # ─── Iteracion de items ───────────────────────────────────────────

    def current_items(self, refresh=True):
        """
        Obtiene los items visibles en la pantalla actual.

        Busca nodos con imagen + texto que parecen ser contenido
        (peliculas, series, canales).

        Returns:
            Lista de dicts con info de cada item.
        """
        if refresh:
            self.device.refresh()

        items = []
        # Buscar TextViews con texto dentro de contenedores clickeables
        text_nodes = (
            self.device.tree.select()
            .has_text()
            .by_class("TextView")
            .all()
        )

        # Filtrar los que no son UI del sistema (version, hora, etc)
        system_ids = {"tv_version", "tv_time", "tv_date", "tv_week", "tv_main_speed"}
        for node in text_nodes:
            if node.short_id in system_ids:
                continue
            if node.short_id == "vod_category_name":
                continue
            if node.text and len(node.text) > 1:
                items.append({
                    "title": node.text,
                    "node": node,
                    "center": node.center,
                    "clickable_parent": node.find_clickable_parent(),
                })

        return items

    def __repr__(self):
        return "MGAndroid()"
