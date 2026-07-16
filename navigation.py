"""
navigation.py - Navegacion inteligente basada en UI.

En lugar de usar coordenadas fijas, este modulo:
1. Hace un dump de la UI actual.
2. Busca el elemento deseado por texto/id.
3. Calcula su centro.
4. Hace tap automaticamente.

Esto hace que el bot sea resistente a cambios de resolucion o layout.
"""

import time
import logging
from pathlib import Path

from adb import ADB, ADBError
from parser import UIParser, UIElement

logger = logging.getLogger(__name__)


class NavigationError(Exception):
    """Error durante la navegacion."""
    pass


class Navigator:
    """
    Navegador inteligente para Android TV.

    Combina ADB + UIParser para navegar la interfaz
    sin depender de coordenadas fijas.
    """

    # Package de la app MGAndroid
    PACKAGE = "com.android.mgandroid"

    # Tiempo de espera por defecto despues de cada accion
    DEFAULT_WAIT = 2.0

    # Ruta temporal del dump en el dispositivo
    REMOTE_DUMP = "/sdcard/ui.xml"

    def __init__(self, adb=None, dumps_dir="dumps"):
        """
        Args:
            adb: Instancia de ADB (crea una nueva si no se pasa).
            dumps_dir: Directorio local para guardar dumps XML.
        """
        self.adb = adb or ADB()
        self.parser = UIParser()
        self.dumps_dir = Path(dumps_dir)
        self.dumps_dir.mkdir(parents=True, exist_ok=True)

        # Contador para nombrar dumps secuencialmente
        self._dump_count = 0

    # ─── Refresh de UI ────────────────────────────────────────────────

    def refresh_ui(self, save_as=None):
        """
        Obtiene el estado actual de la UI.

        1. Ejecuta uiautomator dump en el dispositivo.
        2. Descarga el XML.
        3. Lo parsea.

        Args:
            save_as: Nombre opcional para guardar el dump (sin extension).

        Returns:
            UIParser con los elementos cargados.
        """
        self._dump_count += 1

        # Nombre del archivo local
        if save_as:
            local_name = f"{save_as}.xml"
        else:
            local_name = f"dump_{self._dump_count:03d}.xml"

        local_path = self.dumps_dir / local_name

        # Dump + pull
        self.adb.dump_ui(self.REMOTE_DUMP)
        self.adb.pull_file(self.REMOTE_DUMP, str(local_path))

        # Parsear
        self.parser.parse_file(str(local_path))

        logger.info(
            f"UI refrescada: {len(self.parser.elements)} elementos "
            f"({local_name})"
        )
        return self.parser

    # ─── Navegacion por texto ─────────────────────────────────────────

    def tap_text(self, text, exact=True, wait=None, refresh=True):
        """
        Busca un elemento por texto y hace tap en su centro.

        Args:
            text: Texto visible del elemento.
            exact: Coincidencia exacta o parcial.
            wait: Segundos a esperar despues del tap.
            refresh: Si hacer refresh de UI antes de buscar.

        Returns:
            UIElement en el que se hizo tap.

        Raises:
            NavigationError: Si no se encuentra el elemento.
        """
        if refresh:
            self.refresh_ui()

        elements = self.parser.find_by_text(text, exact=exact)

        if not elements:
            raise NavigationError(
                f"No se encontro elemento con texto: '{text}'\n"
                f"Textos disponibles: {self.parser.get_all_texts()}"
            )

        # Si hay multiples, preferir el clickeable
        target = None
        for elem in elements:
            if elem.clickable:
                target = elem
                break
        if target is None:
            target = elements[0]

        self._tap_element(target, wait)
        return target

    def tap_id(self, resource_id, wait=None, refresh=True):
        """
        Busca un elemento por resource-id y hace tap.

        Args:
            resource_id: ID completo o parcial del recurso.
            wait: Segundos a esperar despues del tap.
            refresh: Si hacer refresh de UI antes de buscar.

        Returns:
            UIElement en el que se hizo tap.
        """
        if refresh:
            self.refresh_ui()

        elements = self.parser.find_by_id(resource_id, partial=True)

        if not elements:
            raise NavigationError(
                f"No se encontro elemento con id: '{resource_id}'"
            )

        target = elements[0]
        self._tap_element(target, wait)
        return target

    def tap_element(self, element, wait=None):
        """
        Hace tap directamente en un UIElement ya conocido.

        Args:
            element: UIElement con bounds validos.
            wait: Segundos a esperar despues.
        """
        self._tap_element(element, wait)

    def _tap_element(self, element, wait=None):
        """Ejecuta el tap en un elemento."""
        cx, cy = element.center
        logger.info(
            f"Tap en: {element.text or element.resource_id} -> ({cx}, {cy})"
        )
        self.adb.tap(cx, cy)
        time.sleep(wait or self.DEFAULT_WAIT)

    # ─── Navegacion por categorias (MGAndroid) ────────────────────────

    def get_categories(self, refresh=True):
        """
        Obtiene las categorias disponibles en la pantalla principal.

        Returns:
            Dict {nombre: UIElement} de categorias.
        """
        if refresh:
            self.refresh_ui(save_as="home")

        return self.parser.get_categories()

    def go_to_category(self, category_name, wait=None):
        """
        Navega a una categoria especifica (VIVO, SERIE, PELICULA, etc).

        Args:
            category_name: Nombre de la categoria (case-sensitive).
            wait: Tiempo de espera tras navegar.

        Returns:
            UIElement de la categoria.
        """
        categories = self.get_categories()

        if category_name not in categories:
            # Intentar busqueda case-insensitive
            for name, elem in categories.items():
                if name.upper() == category_name.upper():
                    category_name = name
                    break
            else:
                raise NavigationError(
                    f"Categoria '{category_name}' no encontrada. "
                    f"Disponibles: {list(categories.keys())}"
                )

        target = categories[category_name]
        # Tap en el contenedor padre (fr_slide) para mejor respuesta
        # Pero usamos el centro del texto que ya conocemos
        self._tap_element(target, wait or 3.0)

        logger.info(f"Navegado a categoria: {category_name}")
        return target

    def iterate_categories(self, callback=None, wait_between=3.0):
        """
        Recorre todas las categorias de la pantalla principal.

        Args:
            callback: Funcion a ejecutar en cada categoria.
                      Recibe (nombre, parser) como argumentos.
            wait_between: Tiempo entre categorias.

        Returns:
            Dict {nombre: UIParser} con el estado de cada pantalla.
        """
        results = {}

        # Primero obtener categorias desde home
        categories = self.get_categories()

        for name, elem in categories.items():
            logger.info(f"\n{'─'*40}")
            logger.info(f"Entrando a: {name}")
            logger.info(f"{'─'*40}")

            # Tap en la categoria
            self._tap_element(elem, wait_between)

            # Refresh para ver la nueva pantalla
            parser = self.refresh_ui(save_as=f"cat_{name}")
            results[name] = parser

            # Ejecutar callback si existe
            if callback:
                try:
                    callback(name, parser)
                except Exception as e:
                    logger.error(f"Error en callback para '{name}': {e}")

            # Volver atras
            self.adb.back()
            time.sleep(self.DEFAULT_WAIT)

        return results

    # ─── Canal en vivo ────────────────────────────────────────────────

    def get_current_channel(self, refresh=True):
        """Obtiene el nombre del canal en vivo actual."""
        if refresh:
            self.refresh_ui()
        return self.parser.get_live_channel_name()

    def change_channel_up(self, wait=2.0):
        """Cambia al canal siguiente (dpad arriba)."""
        self.adb.dpad_up()
        time.sleep(wait)

    def change_channel_down(self, wait=2.0):
        """Cambia al canal anterior (dpad abajo)."""
        self.adb.dpad_down()
        time.sleep(wait)

    # ─── Navegacion generica ──────────────────────────────────────────

    def wait_for_text(self, text, timeout=15, interval=2):
        """
        Espera hasta que un texto aparezca en pantalla.

        Args:
            text: Texto a esperar.
            timeout: Segundos maximos de espera.
            interval: Intervalo entre intentos.

        Returns:
            UIElement cuando aparece.

        Raises:
            NavigationError: Si el texto no aparece en el tiempo limite.
        """
        start = time.time()
        while time.time() - start < timeout:
            self.refresh_ui()
            elements = self.parser.find_by_text(text, exact=False)
            if elements:
                logger.info(f"Texto '{text}' encontrado.")
                return elements[0]
            time.sleep(interval)

        raise NavigationError(
            f"Texto '{text}' no aparecio en {timeout}s."
        )

    def wait_for_id(self, resource_id, timeout=15, interval=2):
        """
        Espera hasta que un elemento con cierto ID aparezca.

        Args:
            resource_id: ID del recurso a esperar.
            timeout: Segundos maximos.
            interval: Intervalo entre intentos.

        Returns:
            UIElement cuando aparece.
        """
        start = time.time()
        while time.time() - start < timeout:
            self.refresh_ui()
            elements = self.parser.find_by_id(resource_id, partial=True)
            if elements:
                return elements[0]
            time.sleep(interval)

        raise NavigationError(
            f"Elemento con id '{resource_id}' no aparecio en {timeout}s."
        )

    def go_home(self):
        """Vuelve a la pantalla principal de la app."""
        self.adb.home()
        time.sleep(1)
        self.adb.start_app(self.PACKAGE)
        time.sleep(3)
        logger.info("Regresado a pantalla principal.")

    def back(self, times=1, wait=1.0):
        """
        Presiona back N veces.

        Args:
            times: Cantidad de veces.
            wait: Espera entre cada back.
        """
        for _ in range(times):
            self.adb.back()
            time.sleep(wait)

    # ─── Scroll / Exploracion ─────────────────────────────────────────

    def scroll_down(self, steps=1):
        """Scroll hacia abajo en la pantalla actual."""
        for _ in range(steps):
            # Swipe desde el centro-abajo hacia el centro-arriba
            self.adb.swipe(698, 500, 698, 200, 300)
            time.sleep(1)

    def scroll_up(self, steps=1):
        """Scroll hacia arriba."""
        for _ in range(steps):
            self.adb.swipe(698, 200, 698, 500, 300)
            time.sleep(1)

    def scroll_right(self, steps=1):
        """Scroll horizontal hacia la derecha."""
        for _ in range(steps):
            self.adb.swipe(1000, 360, 400, 360, 300)
            time.sleep(1)

    def scroll_left(self, steps=1):
        """Scroll horizontal hacia la izquierda."""
        for _ in range(steps):
            self.adb.swipe(400, 360, 1000, 360, 300)
            time.sleep(1)

    # ─── Informacion de estado ────────────────────────────────────────

    def is_on_home(self):
        """Verifica si estamos en la pantalla principal de MGAndroid."""
        self.refresh_ui()
        # La home tiene las categorias y el logo
        has_categories = bool(self.parser.get_categories())
        has_logo = bool(
            self.parser.find_by_id("com.android.mgandroid:id/iv_logo")
        )
        return has_categories and has_logo

    def get_screen_info(self, refresh=True):
        """
        Retorna un resumen del estado actual de la pantalla.

        Returns:
            Dict con informacion de la pantalla.
        """
        if refresh:
            self.refresh_ui()

        return {
            "texts": self.parser.get_all_texts(),
            "clickable_count": len(self.parser.find_clickable()),
            "scrollable_count": len(self.parser.find_scrollable()),
            "total_elements": len(self.parser.elements),
            "channel": self.parser.get_live_channel_name(),
            "version": self.parser.get_app_version(),
        }
