"""
channel_extractor.py - Extractor completo de canales de MGAndroid.

Recorre el menu lateral de TV en vivo, entra a cada categoria,
hace scroll para descubrir todos los canales, y exporta a CSV/JSON.

Estructura de la UI descubierta:
- Panel izquierdo: categorias (ll_channel_root → tv_live_name)
- Panel derecho: lista de canales (recycler_channel → ll_root)
  - tv_live_pos: numero del canal
  - tv_live_name: nombre del canal
  - tv_live_epg: info EPG (programa actual)
  - iv_fav: presente si es favorito
  - animation_view: presente si esta reproduciendo

Uso:
    from channel_extractor import ChannelExtractor
    from mgandroid import MGAndroid

    mg = MGAndroid()
    mg.open()

    extractor = ChannelExtractor(mg)
    extractor.extract_all()
    extractor.export_csv("canales.csv")
    extractor.export_json("canales.json")
    extractor.print_table()
"""

import time
import json
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from device import Device, DeviceError
from node import UINode

logger = logging.getLogger(__name__)


class Channel:
    """Representa un canal de TV."""

    def __init__(self, number="", name="", epg="", category="",
                 is_favorite=False, is_playing=False, is_selected=False):
        self.number = number
        self.name = name
        self.epg = epg
        self.category = category
        self.is_favorite = is_favorite
        self.is_playing = is_playing
        self.is_selected = is_selected

    def to_dict(self):
        return {
            "number": self.number,
            "name": self.name,
            "epg": self.epg,
            "category": self.category,
            "favorite": self.is_favorite,
            "playing": self.is_playing,
            "selected": self.is_selected,
        }

    @property
    def status_icon(self):
        """Icono de estado para tabla."""
        if self.is_playing:
            return "🔴 Reproduciendo"
        if self.is_selected:
            return "► Seleccionado"
        if self.is_favorite:
            return "⭐ Favorito"
        return ""

    def __repr__(self):
        return f"Channel({self.number} | {self.name} | {self.status_icon})"

    def __eq__(self, other):
        """Dos canales son iguales si tienen el mismo nombre."""
        if isinstance(other, Channel):
            return self.name == other.name
        return False

    def __hash__(self):
        return hash(self.name)


class ChannelExtractor:
    """
    Extractor de canales de MGAndroid.

    Navega automaticamente por las categorias del menu lateral,
    hace scroll en la lista de canales, y extrae toda la info.
    """

    # IDs conocidos de la vista de canales
    IDS = {
        "channel_list": "recycler_channel",
        "channel_name": "tv_live_name",
        "channel_number": "tv_live_pos",
        "channel_epg": "tv_live_epg",
        "channel_fav": "iv_fav",
        "channel_playing": "animation_view",
        "channel_row": "ll_root",
        "channel_click": "fr_click",
        "menu_root": "ll_channel_root",
        "menu_name": "tv_live_name",
        "menu_container": "ll_live_channel",
        "scroll_bar": "scroll_bar",
    }

    # Categorias del menu lateral (opciones especiales vs categorias de canales)
    SPECIAL_MENU = ["Buscar", "Favorito", "Reserva"]

    def __init__(self, mg, output_dir="channel_data"):
        """
        Args:
            mg: Instancia de MGAndroid.
            output_dir: Carpeta para guardar exportaciones.
        """
        self.mg = mg
        self.device = mg.device
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Resultados
        self.categories: Dict[str, List[Channel]] = {}
        self.all_channels: List[Channel] = []
        self.menu_items: List[str] = []

    # ─── Extraccion del menu lateral ──────────────────────────────────

    def extract_menu(self, refresh=True):
        """
        Extrae las opciones del menu lateral (categorias de live TV).

        Returns:
            Lista de nombres de categorias.
        """
        if refresh:
            self.device.refresh()

        # El menu lateral usa ll_channel_root con tv_live_name dentro
        # Primero buscar el contenedor del menu (panel izquierdo)
        menu_nodes = self._find_menu_items()

        self.menu_items = [node.text for node in menu_nodes if node.text]
        logger.info(f"Menu lateral: {self.menu_items}")
        return self.menu_items

    def _find_menu_items(self):
        """
        Encuentra los items del menu lateral.

        El menu esta en el panel izquierdo (x < 302) y usa
        ll_channel_root → ll_live_root → tv_live_name.
        """
        # Buscar todos los tv_live_name que estan en el panel izquierdo
        all_names = self.device.tree.find_id("tv_live_name").all()

        # Filtrar: los del menu lateral estan a la izquierda (x2 <= 302)
        menu_items = [n for n in all_names if n.x2 <= 302]

        return menu_items

    # ─── Extraccion de canales ────────────────────────────────────────

    def extract_visible_channels(self):
        """
        Extrae los canales visibles en la pantalla actual.

        Returns:
            Lista de Channel encontrados en la vista actual.
        """
        self.device.refresh()
        channels = self._parse_channel_list()
        return channels

    def _parse_channel_list(self):
        """
        Parsea la lista de canales del panel derecho.

        Busca cada fila de canal (ll_root dentro de recycler_channel)
        y extrae: numero, nombre, EPG, favorito, reproduciendo.
        """
        channels = []

        # Buscar todos los ll_root que son filas de canales (panel derecho, x > 302)
        rows = self.device.tree.find_id("ll_root").all()
        channel_rows = [r for r in rows if r.x1 >= 302 and r.clickable]

        for row in channel_rows:
            channel = self._parse_channel_row(row)
            if channel and channel.name:
                channels.append(channel)

        return channels

    def _parse_channel_row(self, row_node):
        """
        Extrae informacion de una fila de canal.

        Args:
            row_node: UINode de la fila (ll_root).

        Returns:
            Channel o None si no se puede parsear.
        """
        channel = Channel()

        # Buscar numero (tv_live_pos)
        pos_node = row_node.find_child_by_id("tv_live_pos", partial=True)
        if pos_node:
            channel.number = pos_node.text

        # Buscar nombre (tv_live_name)
        name_node = row_node.find_child_by_id("tv_live_name", partial=True)
        if name_node:
            channel.name = name_node.text
            # Verificar si esta seleccionado
            if name_node.selected:
                channel.is_selected = True

        # Buscar EPG (tv_live_epg)
        epg_node = row_node.find_child_by_id("tv_live_epg", partial=True)
        if epg_node:
            channel.epg = epg_node.text

        # Verificar si es favorito (tiene iv_fav)
        fav_node = row_node.find_child_by_id("iv_fav", partial=True)
        if fav_node:
            channel.is_favorite = True

        # Verificar si esta reproduciendo (tiene animation_view)
        anim_node = row_node.find_child_by_id("animation_view", partial=True)
        if anim_node:
            channel.is_playing = True

        # Verificar focused
        if row_node.focused:
            channel.is_selected = True

        return channel

    # ─── Extraccion completa con scroll ───────────────────────────────

    def extract_category(self, category_name, max_scrolls=50, wait=1.5):
        """
        Extrae TODOS los canales de una categoria haciendo scroll.

        Args:
            category_name: Nombre de la categoria en el menu lateral.
            max_scrolls: Maximo de scrolls para evitar loop infinito.
            wait: Espera entre scrolls.

        Returns:
            Lista de Channel de la categoria.
        """
        logger.info(f"\n{'─'*50}")
        logger.info(f"  Extrayendo: {category_name}")
        logger.info(f"{'─'*50}")

        # Click en la categoria del menu lateral
        self.device.click_text(category_name, wait=wait)

        # Recopilar canales con scroll
        all_channels = []
        seen_names = set()
        no_new_count = 0

        for scroll_num in range(max_scrolls):
            # Extraer canales visibles
            visible = self.extract_visible_channels()

            # Agregar solo los nuevos
            new_count = 0
            for ch in visible:
                if ch.name and ch.name not in seen_names:
                    ch.category = category_name
                    all_channels.append(ch)
                    seen_names.add(ch.name)
                    new_count += 1

            logger.info(
                f"  Scroll {scroll_num+1}: "
                f"{new_count} nuevos, {len(all_channels)} total"
            )

            # Si no hay nuevos canales, posiblemente llegamos al final
            if new_count == 0:
                no_new_count += 1
                if no_new_count >= 3:
                    logger.info(f"  Fin de la lista ({len(all_channels)} canales)")
                    break
            else:
                no_new_count = 0

            # Scroll hacia abajo en la lista de canales
            # La lista esta en el panel derecho (x: 302-719)
            self._scroll_channel_list()
            time.sleep(wait)

        self.categories[category_name] = all_channels
        return all_channels

    def _scroll_channel_list(self):
        """
        Hace scroll en la lista de canales (panel derecho).

        Usa dpad_down varias veces para mover el cursor,
        lo que hace scroll automatico en el RecyclerView.
        """
        # Mover el foco al panel derecho si no esta ahi
        # Usar dpad_down para scrollear (mas confiable que swipe en TV)
        for _ in range(6):
            self.device.dpad_down()
            time.sleep(0.15)

    # ─── Extraccion de TODAS las categorias ───────────────────────────

    def extract_all(self, skip_special=True, max_scrolls=50, wait=1.5):
        """
        Extrae canales de TODAS las categorias.

        Args:
            skip_special: Si True, salta Buscar/Favorito/Reserva.
            max_scrolls: Max scrolls por categoria.
            wait: Espera entre acciones.

        Returns:
            Dict {categoria: [Channel, ...]}
        """
        logger.info("\n" + "=" * 55)
        logger.info("  EXTRACCION COMPLETA DE CANALES")
        logger.info("=" * 55)

        # Abrir el panel de canales
        if not self._open_channel_panel():
            logger.error("No se pudo abrir el panel de canales.")
            return {}

        # Extraer menu lateral
        self.extract_menu()

        if not self.menu_items:
            logger.error("Menu lateral vacio. El panel no se abrio correctamente.")
            return {}

        # Recorrer cada categoria
        categories_to_scan = self.menu_items[:]
        if skip_special:
            categories_to_scan = [
                c for c in categories_to_scan
                if c not in self.SPECIAL_MENU
            ]

        for cat_name in categories_to_scan:
            try:
                self.extract_category(
                    cat_name,
                    max_scrolls=max_scrolls,
                    wait=wait
                )
            except DeviceError as e:
                logger.error(f"  Error en '{cat_name}': {e}")
                # Intentar volver al estado anterior
                self.device.back()
                time.sleep(1)

        # Consolidar todos los canales (sin duplicados)
        self._consolidate()

        logger.info(f"\n{'='*55}")
        logger.info(f"  EXTRACCION COMPLETA")
        logger.info(f"  Categorias: {len(self.categories)}")
        logger.info(f"  Canales unicos: {len(self.all_channels)}")
        logger.info(f"{'='*55}\n")

        return self.categories

    def _open_channel_panel(self, max_attempts=5):
        """
        Abre el panel de canales en la seccion VIVO.

        Intenta varias estrategias para abrir el panel:
        1. Si ya esta en la vista de canales (program_view visible) → listo
        2. Si esta en home → ir a VIVO
        3. Presionar OK para abrir panel
        4. Si no funciona, presionar MENU
        5. Si no funciona, presionar OK de nuevo

        Returns:
            True si el panel se abrio correctamente.
        """
        logger.info("Abriendo panel de canales...")

        # Verificar si ya estamos en la vista de canales
        self.device.refresh()
        if self._is_channel_panel_open():
            logger.info("Panel de canales ya esta abierto.")
            return True

        # Verificar si estamos en home (tiene categorias VIVO/SERIE/etc)
        cats = self.device.tree.get_categories()
        if cats:
            logger.info("En home. Navegando a VIVO...")
            # Click en VIVO para entrar a la seccion de TV en vivo
            vivo_node = cats.get("VIVO")
            if vivo_node:
                self.device.click_node(vivo_node, wait=3.0)
            else:
                self.device.click_text("VIVO", wait=3.0)

        # Ahora estamos en la vista del reproductor (fullscreen o con panel)
        # Intentar abrir el panel de canales
        for attempt in range(max_attempts):
            self.device.refresh()

            if self._is_channel_panel_open():
                logger.info(f"Panel abierto (intento {attempt+1}).")
                return True

            # Estrategia segun intento
            if attempt == 0:
                # Primer intento: presionar OK (suele abrir el panel)
                logger.info("  Intentando OK...")
                self.device.dpad_center()
                time.sleep(2)
            elif attempt == 1:
                # Segundo intento: presionar OK de nuevo
                logger.info("  Intentando OK de nuevo...")
                self.device.dpad_center()
                time.sleep(2)
            elif attempt == 2:
                # Tercer intento: MENU
                logger.info("  Intentando MENU...")
                self.device.menu()
                time.sleep(2)
            elif attempt == 3:
                # Cuarto intento: tap en el centro de la pantalla
                logger.info("  Intentando tap en centro...")
                self.device.tap(698, 360)
                time.sleep(2)
            else:
                # Ultimo intento: back y reintentar
                logger.info("  Intentando BACK + OK...")
                self.device.back()
                time.sleep(1)
                self.device.dpad_center()
                time.sleep(2)

        # Ultimo check
        self.device.refresh()
        return self._is_channel_panel_open()

    def _is_channel_panel_open(self):
        """
        Verifica si el panel de canales esta abierto.

        Indicadores:
        - Existe program_view o ll_program_root
        - Existe recycler_channel
        - Hay nodos tv_live_name con x > 300 (canales, no menu)
        - El arbol tiene mas de 50 nodos (panel abierto vs 20 en fullscreen)
        """
        # Check rapido por cantidad de nodos
        if self.device.tree.node_count < 30:
            return False

        # Buscar indicadores del panel
        indicators = [
            "program_view",
            "ll_program_root",
            "recycler_channel",
            "ll_live_channel",
        ]

        for indicator in indicators:
            if self.device.tree.find_id(indicator).first():
                return True

        # Buscar tv_live_name (presente tanto en menu como en canales)
        names = self.device.tree.find_id("tv_live_name").all()
        if len(names) >= 3:
            return True

        return False

    def extract_favorites(self):
        """Extrae solo los canales favoritos."""
        logger.info("Extrayendo favoritos...")
        if not self._open_channel_panel():
            logger.error("No se pudo abrir el panel de canales.")
            return []
        return self.extract_category("Favorito", max_scrolls=20)

    # ─── Consolidacion ────────────────────────────────────────────────

    def _consolidate(self):
        """Consolida todos los canales en una lista unica sin duplicados."""
        seen = set()
        self.all_channels = []

        for cat_name, channels in self.categories.items():
            for ch in channels:
                if ch.name not in seen:
                    self.all_channels.append(ch)
                    seen.add(ch.name)

        # Ordenar por numero (los que tienen)
        def sort_key(ch):
            try:
                return int(ch.number)
            except (ValueError, TypeError):
                return 99999

        self.all_channels.sort(key=sort_key)

    # ─── Exportacion ──────────────────────────────────────────────────

    def export_csv(self, filename=None):
        """
        Exporta todos los canales a CSV.

        Args:
            filename: Nombre del archivo (default: canales_TIMESTAMP.csv)

        Returns:
            Ruta del archivo generado.
        """
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"canales_{ts}.csv"

        filepath = self.output_dir / filename

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Numero", "Canal", "Categoria", "EPG",
                "Favorito", "Reproduciendo", "Estado"
            ])

            for ch in self.all_channels:
                writer.writerow([
                    ch.number,
                    ch.name,
                    ch.category,
                    ch.epg,
                    "Si" if ch.is_favorite else "",
                    "Si" if ch.is_playing else "",
                    ch.status_icon,
                ])

        logger.info(f"CSV exportado: {filepath} ({len(self.all_channels)} canales)")
        return str(filepath)

    def export_json(self, filename=None):
        """
        Exporta todos los canales a JSON.

        Args:
            filename: Nombre del archivo.

        Returns:
            Ruta del archivo generado.
        """
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"canales_{ts}.json"

        filepath = self.output_dir / filename

        data = {
            "timestamp": datetime.now().isoformat(),
            "total_channels": len(self.all_channels),
            "total_categories": len(self.categories),
            "menu_items": self.menu_items,
            "categories": {},
            "channels": [ch.to_dict() for ch in self.all_channels],
        }

        # Agregar canales por categoria
        for cat_name, channels in self.categories.items():
            data["categories"][cat_name] = {
                "count": len(channels),
                "channels": [ch.to_dict() for ch in channels],
            }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"JSON exportado: {filepath}")
        return str(filepath)

    def export_txt(self, filename=None):
        """
        Exporta un reporte legible en texto plano.

        Returns:
            Ruta del archivo.
        """
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"canales_{ts}.txt"

        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("=" * 65 + "\n")
            f.write("  LISTA DE CANALES - MGAndroid\n")
            f.write(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"  Total: {len(self.all_channels)} canales\n")
            f.write("=" * 65 + "\n\n")

            for cat_name, channels in self.categories.items():
                f.write(f"\n{'─'*55}\n")
                f.write(f"  {cat_name} ({len(channels)} canales)\n")
                f.write(f"{'─'*55}\n")
                f.write(f"  {'#':<6} {'Canal':<30} {'Estado'}\n")
                f.write(f"  {'─'*5} {'─'*29} {'─'*20}\n")

                for ch in channels:
                    num = ch.number or "—"
                    f.write(f"  {num:<6} {ch.name:<30} {ch.status_icon}\n")

                f.write("\n")

        logger.info(f"TXT exportado: {filepath}")
        return str(filepath)

    # ─── Mostrar en consola ───────────────────────────────────────────

    def print_table(self, category=None):
        """
        Imprime una tabla formateada de canales.

        Args:
            category: Si se especifica, solo muestra esa categoria.
        """
        if category:
            cats_to_show = {category: self.categories.get(category, [])}
        else:
            cats_to_show = self.categories

        for cat_name, channels in cats_to_show.items():
            print(f"\n{'═'*60}")
            print(f"  {cat_name} ({len(channels)} canales)")
            print(f"{'═'*60}")
            print(f"  {'#':<6} {'Canal':<32} {'Estado'}")
            print(f"  {'─'*5} {'─'*31} {'─'*20}")

            for ch in channels:
                num = ch.number or "—"
                estado = ch.status_icon
                print(f"  {num:<6} {ch.name:<32} {estado}")

        # Resumen
        print(f"\n{'─'*60}")
        print(f"  Total: {len(self.all_channels)} canales unicos")
        print(f"  Categorias: {list(self.categories.keys())}")
        favs = sum(1 for ch in self.all_channels if ch.is_favorite)
        if favs:
            print(f"  Favoritos: {favs}")
        print(f"{'─'*60}\n")

    def print_menu(self):
        """Imprime el menu lateral."""
        print(f"\n  Menu Lateral de TV en Vivo:")
        print(f"  {'─'*30}")
        for i, item in enumerate(self.menu_items, 1):
            icon = "📂" if item not in self.SPECIAL_MENU else "⚙️"
            print(f"  {i}. {icon} {item}")
        print()

    # ─── Resumen ──────────────────────────────────────────────────────

    def summary(self):
        """Imprime resumen de la extraccion."""
        print(f"\n{'═'*55}")
        print(f"  RESUMEN DE EXTRACCION")
        print(f"{'═'*55}")
        print(f"  Categorias encontradas: {len(self.categories)}")
        print(f"  Canales unicos totales: {len(self.all_channels)}")
        print(f"  Archivos en: {self.output_dir}")

        for cat_name, channels in self.categories.items():
            favs = sum(1 for c in channels if c.is_favorite)
            fav_str = f" ({favs} ⭐)" if favs else ""
            print(f"    {cat_name}: {len(channels)} canales{fav_str}")

        print(f"{'═'*55}\n")

    def __repr__(self):
        return (
            f"ChannelExtractor("
            f"categories={len(self.categories)}, "
            f"channels={len(self.all_channels)})"
        )
