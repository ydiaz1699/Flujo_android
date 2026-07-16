"""
ui.py - Parser de ui.xml que construye arbol con relaciones padre-hijo.

Lee el XML de uiautomator y construye un arbol de UINode donde cada nodo
conoce a su padre y sus hijos. Permite busqueda via Selector.
"""

import xml.etree.ElementTree as ET
import logging
from typing import List, Optional
from pathlib import Path

from node import UINode
from selector import Selector

logger = logging.getLogger(__name__)


class UITree:
    """
    Arbol de UI completo.

    Parsea ui.xml y mantiene el arbol con relaciones
    padre-hijo para busqueda inteligente.
    """

    def __init__(self):
        self.root: Optional[UINode] = None
        self.all_nodes: List[UINode] = []
        self._source_file: Optional[str] = None

    def parse_file(self, filepath):
        """
        Parsea un archivo ui.xml.

        Args:
            filepath: Ruta al archivo XML.

        Returns:
            self (para encadenamiento).
        """
        filepath = str(filepath)
        self._source_file = filepath
        logger.info(f"Parseando UI: {filepath}")

        tree = ET.parse(filepath)
        xml_root = tree.getroot()

        self.all_nodes = []
        self.root = self._build_tree(xml_root, parent=None, depth=0)

        logger.info(f"Arbol construido: {len(self.all_nodes)} nodos")
        return self

    def parse_string(self, xml_string):
        """Parsea XML desde un string."""
        xml_root = ET.fromstring(xml_string)
        self.all_nodes = []
        self.root = self._build_tree(xml_root, parent=None, depth=0)
        return self


    def _build_tree(self, xml_node, parent, depth):
        """
        Construye el arbol recursivamente.

        Args:
            xml_node: Nodo XML de ElementTree.
            parent: UINode padre (None para root).
            depth: Profundidad actual.

        Returns:
            UINode construido.
        """
        # Crear UINode desde atributos XML
        ui_node = UINode.from_xml_attribs(xml_node.attrib)
        ui_node.depth = depth
        ui_node.parent = parent

        # Registrar
        self.all_nodes.append(ui_node)

        # Procesar hijos recursivamente
        for xml_child in xml_node:
            child = self._build_tree(xml_child, parent=ui_node, depth=depth + 1)
            ui_node.children.append(child)

        return ui_node

    # ─── Selectores (acceso rapido) ───────────────────────────────────

    def select(self):
        """
        Retorna un Selector con todos los nodos.

        Ejemplo:
            tree.select().text("PELICULA").first()
        """
        return Selector(self.all_nodes)

    def find_text(self, text, exact=True):
        """Atajo: buscar por texto."""
        return self.select().text(text, exact=exact)

    def find_id(self, resource_id, partial=True):
        """Atajo: buscar por resource-id."""
        return self.select().by_id(resource_id, partial=partial)

    def find_class(self, class_name):
        """Atajo: buscar por clase."""
        return self.select().by_class(class_name)


    # ─── Consultas especificas de MGAndroid ───────────────────────────

    def get_categories(self):
        """
        Obtiene las categorias de la pantalla principal.

        Returns:
            Dict {nombre: UINode}
        """
        cats = self.find_id("vod_category_name", partial=True).all()
        return {n.text: n for n in cats if n.text}

    def get_live_channel(self):
        """Obtiene el nombre del canal en vivo."""
        node = self.find_id("tv_live_title").first()
        return node.text if node else None

    def get_version(self):
        """Obtiene la version de la app."""
        node = self.find_id("tv_version").first()
        return node.text if node else None

    def get_speed(self):
        """Obtiene la velocidad de red mostrada."""
        node = self.find_id("tv_main_speed").first()
        return node.text if node else None

    # ─── Info y debug ─────────────────────────────────────────────────

    def get_all_texts(self):
        """Retorna todos los textos visibles."""
        return [n.text for n in self.all_nodes if n.text]

    def get_clickable(self):
        """Retorna nodos clickeables."""
        return [n for n in self.all_nodes if n.clickable]

    def get_focused(self):
        """Retorna el nodo enfocado (si hay)."""
        for n in self.all_nodes:
            if n.focused:
                return n
        return None

    @property
    def node_count(self):
        return len(self.all_nodes)

    def summary(self):
        """Imprime resumen del arbol."""
        texts = self.get_all_texts()
        clickable = self.get_clickable()
        focused = self.get_focused()

        print(f"\n{'='*55}")
        print(f"  UI TREE - {self.node_count} nodos")
        if self._source_file:
            print(f"  Fuente: {Path(self._source_file).name}")
        print(f"{'='*55}")
        print(f"  Clickeables:  {len(clickable)}")
        print(f"  Con texto:    {len(texts)}")
        print(f"  Focused:      {focused.display_name if focused else 'ninguno'}")
        print(f"\n  Textos visibles:")
        for t in texts:
            print(f"    - {t}")
        print(f"{'='*55}\n")

    def print_tree(self, max_depth=None):
        """Imprime el arbol visual."""
        if self.root:
            print(self.root.tree_str(max_depth=max_depth))

    def __repr__(self):
        return f"UITree({self.node_count} nodes)"
