"""
parser.py - Parser de UI XML (uiautomator dump).

Analiza el archivo ui.xml generado por `uiautomator dump` y permite
buscar elementos por texto, resource-id, clase, etc. Calcula
automaticamente las coordenadas centrales para hacer tap.
"""

import xml.etree.ElementTree as ET
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class UIElement:
    """Representa un elemento de la interfaz de Android."""

    text: str = ""
    resource_id: str = ""
    class_name: str = ""
    package: str = ""
    content_desc: str = ""
    checkable: bool = False
    checked: bool = False
    clickable: bool = False
    enabled: bool = True
    focusable: bool = False
    focused: bool = False
    scrollable: bool = False
    long_clickable: bool = False
    selected: bool = False
    bounds_raw: str = ""
    # Bounds parseados
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0
    # Nodo XML original
    _node: object = field(default=None, repr=False)

    @property
    def center(self):
        """Calcula el punto central del elemento (para tap)."""
        cx = (self.x1 + self.x2) // 2
        cy = (self.y1 + self.y2) // 2
        return (cx, cy)

    @property
    def width(self):
        return self.x2 - self.x1

    @property
    def height(self):
        return self.y2 - self.y1

    @property
    def area(self):
        return self.width * self.height

    def __str__(self):
        parts = []
        if self.text:
            parts.append(f'text="{self.text}"')
        if self.resource_id:
            parts.append(f'id="{self.resource_id}"')
        if self.content_desc:
            parts.append(f'desc="{self.content_desc}"')
        parts.append(f"center={self.center}")
        parts.append(f"bounds=[{self.x1},{self.y1}][{self.x2},{self.y2}]")
        return f"UIElement({', '.join(parts)})"


class UIParser:
    """Parser de archivos ui.xml generados por uiautomator."""

    # Regex para extraer bounds: [x1,y1][x2,y2]
    BOUNDS_PATTERN = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")

    def __init__(self):
        self.elements = []
        self.tree = None
        self.root = None

    def parse_file(self, filepath):
        """
        Lee y parsea un archivo ui.xml.

        Args:
            filepath: Ruta al archivo XML.

        Returns:
            self (para encadenamiento).
        """
        logger.info(f"Parseando: {filepath}")
        self.tree = ET.parse(filepath)
        self.root = self.tree.getroot()
        self.elements = []
        self._walk(self.root)
        logger.info(f"Elementos encontrados: {len(self.elements)}")
        return self

    def parse_string(self, xml_string):
        """
        Parsea XML desde un string.

        Args:
            xml_string: Contenido XML como string.

        Returns:
            self (para encadenamiento).
        """
        self.root = ET.fromstring(xml_string)
        self.elements = []
        self._walk(self.root)
        return self

    def _walk(self, node):
        """Recorre recursivamente el arbol XML y extrae elementos."""
        element = self._node_to_element(node)
        if element:
            self.elements.append(element)

        for child in node:
            self._walk(child)

    def _node_to_element(self, node):
        """Convierte un nodo XML en un UIElement."""
        bounds_raw = node.get("bounds", "")
        match = self.BOUNDS_PATTERN.match(bounds_raw)

        if not match:
            return None

        x1, y1, x2, y2 = [int(v) for v in match.groups()]

        return UIElement(
            text=node.get("text", ""),
            resource_id=node.get("resource-id", ""),
            class_name=node.get("class", ""),
            package=node.get("package", ""),
            content_desc=node.get("content-desc", ""),
            checkable=node.get("checkable") == "true",
            checked=node.get("checked") == "true",
            clickable=node.get("clickable") == "true",
            enabled=node.get("enabled") == "true",
            focusable=node.get("focusable") == "true",
            focused=node.get("focused") == "true",
            scrollable=node.get("scrollable") == "true",
            long_clickable=node.get("long-clickable") == "true",
            selected=node.get("selected") == "true",
            bounds_raw=bounds_raw,
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            _node=node,
        )

    # ─── Metodos de busqueda ──────────────────────────────────────────

    def find_by_text(self, text, exact=True):
        """
        Busca elementos por texto visible.

        Args:
            text: Texto a buscar.
            exact: Si True, coincidencia exacta. Si False, busca substring.

        Returns:
            Lista de UIElement que coinciden.
        """
        if exact:
            results = [e for e in self.elements if e.text == text]
        else:
            text_lower = text.lower()
            results = [e for e in self.elements if text_lower in e.text.lower()]

        logger.debug(f"find_by_text('{text}'): {len(results)} resultados")
        return results

    def find_by_id(self, resource_id, partial=False):
        """
        Busca elementos por resource-id.

        Args:
            resource_id: ID del recurso (ej: com.android.mgandroid:id/tv_live_title).
            partial: Si True, busca coincidencia parcial.

        Returns:
            Lista de UIElement que coinciden.
        """
        if partial:
            results = [e for e in self.elements if resource_id in e.resource_id]
        else:
            results = [e for e in self.elements if e.resource_id == resource_id]

        logger.debug(f"find_by_id('{resource_id}'): {len(results)} resultados")
        return results

    def find_by_class(self, class_name):
        """Busca elementos por nombre de clase Android."""
        return [e for e in self.elements if e.class_name == class_name]

    def find_by_content_desc(self, desc, exact=True):
        """Busca elementos por content-description (accesibilidad)."""
        if exact:
            return [e for e in self.elements if e.content_desc == desc]
        return [e for e in self.elements if desc.lower() in e.content_desc.lower()]

    def find_clickable(self):
        """Retorna todos los elementos clickeables."""
        return [e for e in self.elements if e.clickable]

    def find_focused(self):
        """Retorna el elemento actualmente enfocado (si hay)."""
        focused = [e for e in self.elements if e.focused]
        return focused[0] if focused else None

    def find_scrollable(self):
        """Retorna elementos scrolleables (listas, viewpagers, etc)."""
        return [e for e in self.elements if e.scrollable]

    # ─── Busqueda avanzada ────────────────────────────────────────────

    def find(self, **kwargs):
        """
        Busqueda flexible por multiples atributos.

        Ejemplo:
            parser.find(text="VIVO", clickable=True)
            parser.find(resource_id="com.android.mgandroid:id/vod_category_name")

        Args:
            **kwargs: Atributos a coincidir.

        Returns:
            Lista de UIElement que cumplen TODOS los criterios.
        """
        results = self.elements[:]

        for attr, value in kwargs.items():
            results = [e for e in results if getattr(e, attr, None) == value]

        return results

    def find_one(self, **kwargs):
        """
        Como find() pero retorna solo el primer resultado o None.
        """
        results = self.find(**kwargs)
        return results[0] if results else None

    # ─── Utilidades ───────────────────────────────────────────────────

    def get_all_texts(self):
        """Retorna todos los textos visibles en pantalla."""
        return [e.text for e in self.elements if e.text]

    def get_categories(self):
        """
        Extrae categorias de la pantalla principal de MGAndroid.

        Busca elementos con resource-id 'vod_category_name'.

        Returns:
            Dict {nombre_categoria: UIElement}
        """
        categories = {}
        cat_elements = self.find_by_id(
            "com.android.mgandroid:id/vod_category_name", partial=False
        )
        for elem in cat_elements:
            if elem.text:
                categories[elem.text] = elem

        logger.info(f"Categorias encontradas: {list(categories.keys())}")
        return categories

    def get_live_channel_name(self):
        """Obtiene el nombre del canal en vivo actualmente visible."""
        results = self.find_by_id("com.android.mgandroid:id/tv_live_title")
        if results:
            return results[0].text
        return None

    def get_app_version(self):
        """Obtiene la version de la app desde la UI."""
        results = self.find_by_id("com.android.mgandroid:id/tv_version")
        if results:
            return results[0].text
        return None

    def summary(self):
        """Imprime un resumen de los elementos encontrados."""
        print(f"\n{'='*60}")
        print(f"  UI DUMP SUMMARY")
        print(f"{'='*60}")
        print(f"  Total elementos: {len(self.elements)}")
        print(f"  Clickeables:     {len(self.find_clickable())}")
        print(f"  Scrolleables:    {len(self.find_scrollable())}")
        print(f"  Con texto:       {len([e for e in self.elements if e.text])}")
        print(f"\n  Textos visibles:")
        for text in self.get_all_texts():
            print(f"    - {text}")
        print(f"{'='*60}\n")

    def print_tree(self, max_depth=None):
        """
        Imprime el arbol de UI de forma legible.

        Args:
            max_depth: Profundidad maxima a mostrar (None = todo).
        """
        if self.root is not None:
            self._print_node(self.root, depth=0, max_depth=max_depth)

    def _print_node(self, node, depth=0, max_depth=None):
        """Helper recursivo para print_tree."""
        if max_depth is not None and depth > max_depth:
            return

        indent = "  " * depth
        text = node.get("text", "")
        rid = node.get("resource-id", "")
        cls = node.get("class", "").split(".")[-1]  # Solo el nombre corto

        label = cls
        if text:
            label += f' "{text}"'
        if rid:
            short_id = rid.split("/")[-1] if "/" in rid else rid
            label += f" [{short_id}]"

        print(f"{indent}{label}")

        for child in node:
            self._print_node(child, depth + 1, max_depth)
