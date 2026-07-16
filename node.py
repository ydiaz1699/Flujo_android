"""
node.py - Clase UINode con jerarquia padre/hijo.

Representa un nodo del arbol de UI de Android (uiautomator dump).
Soporta navegacion por el arbol: buscar padre clickeable, hijos,
hermanos, y calcular coordenadas de tap.
"""

import re
from typing import Optional, List


class UINode:
    """
    Nodo de la interfaz de Android.

    Cada nodo corresponde a un elemento del XML generado por
    `uiautomator dump`. Mantiene referencia a su padre e hijos
    para permitir navegacion bidireccional del arbol.
    """

    # Regex para parsear bounds: [x1,y1][x2,y2]
    _BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")

    def __init__(
        self,
        text="",
        resource_id="",
        class_name="",
        package="",
        content_desc="",
        checkable=False,
        checked=False,
        clickable=False,
        enabled=True,
        focusable=False,
        focused=False,
        scrollable=False,
        long_clickable=False,
        password=False,
        selected=False,
        bounds="",
        naf=False,
        index=0,
    ):
        # Atributos del nodo
        self.text = text
        self.resource_id = resource_id
        self.class_name = class_name
        self.package = package
        self.content_desc = content_desc
        self.checkable = checkable
        self.checked = checked
        self.clickable = clickable
        self.enabled = enabled
        self.focusable = focusable
        self.focused = focused
        self.scrollable = scrollable
        self.long_clickable = long_clickable
        self.password = password
        self.selected = selected
        self.naf = naf  # Not Accessible Friendly
        self.index = index

        # Bounds
        self.bounds_raw = bounds
        self.x1, self.y1, self.x2, self.y2 = self._parse_bounds(bounds)

        # Relaciones
        self.parent: Optional["UINode"] = None
        self.children: List["UINode"] = []

        # Profundidad en el arbol (se asigna durante el parsing)
        self.depth = 0

    # ─── Bounds y coordenadas ─────────────────────────────────────────

    @staticmethod
    def _parse_bounds(bounds_str):
        """Parsea '[x1,y1][x2,y2]' a (x1, y1, x2, y2)."""
        match = UINode._BOUNDS_RE.match(bounds_str)
        if match:
            return tuple(int(v) for v in match.groups())
        return (0, 0, 0, 0)

    @property
    def center(self):
        """Coordenadas centrales del nodo (x, y)."""
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

    @property
    def bounds(self):
        """Retorna bounds como tupla (x1, y1, x2, y2)."""
        return (self.x1, self.y1, self.x2, self.y2)

    def contains_point(self, x, y):
        """Verifica si el punto (x,y) esta dentro del nodo."""
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    def overlaps(self, other):
        """Verifica si este nodo se superpone con otro."""
        return not (
            self.x2 < other.x1
            or self.x1 > other.x2
            or self.y2 < other.y1
            or self.y1 > other.y2
        )

    # ─── Navegacion por el arbol ──────────────────────────────────────

    def add_child(self, child):
        """Agrega un hijo y establece la relacion padre."""
        child.parent = self
        child.depth = self.depth + 1
        self.children.append(child)

    @property
    def siblings(self):
        """Retorna los hermanos de este nodo (sin incluirse)."""
        if self.parent is None:
            return []
        return [c for c in self.parent.children if c is not self]

    @property
    def is_leaf(self):
        """Verifica si es un nodo hoja (sin hijos)."""
        return len(self.children) == 0

    @property
    def is_root(self):
        """Verifica si es el nodo raiz."""
        return self.parent is None

    def ancestors(self):
        """Retorna la cadena de ancestros (del padre al root)."""
        result = []
        current = self.parent
        while current is not None:
            result.append(current)
            current = current.parent
        return result

    def descendants(self):
        """Retorna todos los descendientes (BFS)."""
        result = []
        queue = list(self.children)
        while queue:
            node = queue.pop(0)
            result.append(node)
            queue.extend(node.children)
        return result

    # ─── Buscar padre clickeable (clave del framework) ────────────────

    def find_clickable_parent(self):
        """
        Sube por el arbol hasta encontrar el primer ancestro clickeable.

        Este es el metodo clave: cuando queremos tocar "PELICULA",
        el TextView no es clickeable, pero su contenedor si.
        Este metodo encuentra ese contenedor.

        Returns:
            UINode clickeable mas cercano, o self si ya es clickeable.
            None si no hay ningun ancestro clickeable.
        """
        # Si el nodo mismo es clickeable, usarlo
        if self.clickable:
            return self

        # Subir por el arbol
        current = self.parent
        while current is not None:
            if current.clickable:
                return current
            current = current.parent

        # Si no hay padre clickeable, retornar self como fallback
        # (el tap igualmente funcionara en las coordenadas)
        return self

    def find_focusable_parent(self):
        """Busca el primer ancestro focusable (para navegacion con dpad)."""
        if self.focusable:
            return self

        current = self.parent
        while current is not None:
            if current.focusable:
                return current
            current = current.parent
        return self

    def get_tap_target(self):
        """
        Obtiene el mejor nodo para hacer tap.

        Estrategia:
        1. Si el nodo es clickeable -> usarlo.
        2. Si tiene un padre clickeable -> usar el padre.
        3. Fallback: usar el propio nodo.

        Returns:
            Tupla (UINode objetivo, (x, y) centro).
        """
        target = self.find_clickable_parent()
        return (target, target.center)

    # ─── Busqueda en hijos ────────────────────────────────────────────

    def find_child_by_text(self, text, exact=True):
        """Busca un hijo (directo o descendiente) por texto."""
        for node in self.descendants():
            if exact and node.text == text:
                return node
            elif not exact and text.lower() in node.text.lower():
                return node
        return None

    def find_child_by_id(self, resource_id, partial=False):
        """Busca un hijo por resource-id."""
        for node in self.descendants():
            if partial and resource_id in node.resource_id:
                return node
            elif node.resource_id == resource_id:
                return node
        return None

    def find_children_by_class(self, class_name):
        """Busca hijos directos por clase."""
        return [c for c in self.children if c.class_name == class_name]

    # ─── Utilidades ───────────────────────────────────────────────────

    @property
    def short_class(self):
        """Nombre corto de la clase (sin package)."""
        if "." in self.class_name:
            return self.class_name.rsplit(".", 1)[-1]
        return self.class_name

    @property
    def short_id(self):
        """ID corto (sin el package prefix)."""
        if "/" in self.resource_id:
            return self.resource_id.split("/", 1)[-1]
        return self.resource_id

    @property
    def display_name(self):
        """Nombre legible para logs y debug."""
        if self.text:
            return f'"{self.text}"'
        if self.resource_id:
            return f"[{self.short_id}]"
        if self.content_desc:
            return f'desc:"{self.content_desc}"'
        return self.short_class

    def to_dict(self):
        """Convierte a diccionario (para JSON export)."""
        return {
            "text": self.text,
            "resource_id": self.resource_id,
            "class": self.class_name,
            "content_desc": self.content_desc,
            "clickable": self.clickable,
            "focusable": self.focusable,
            "focused": self.focused,
            "scrollable": self.scrollable,
            "bounds": self.bounds_raw,
            "center": self.center,
            "depth": self.depth,
            "children_count": len(self.children),
        }

    def tree_str(self, max_depth=None, _current_depth=0):
        """Representacion en forma de arbol (para debug)."""
        if max_depth is not None and _current_depth > max_depth:
            return ""

        indent = "  " * _current_depth
        prefix = "├─ " if _current_depth > 0 else ""

        # Construir etiqueta
        label = self.short_class
        if self.text:
            label += f' "{self.text}"'
        if self.resource_id:
            label += f" [{self.short_id}]"

        flags = []
        if self.clickable:
            flags.append("click")
        if self.focusable:
            flags.append("focus")
        if self.focused:
            flags.append("FOCUSED")
        if self.scrollable:
            flags.append("scroll")
        if flags:
            label += f" ({', '.join(flags)})"

        result = f"{indent}{prefix}{label}\n"

        for child in self.children:
            result += child.tree_str(max_depth, _current_depth + 1)

        return result

    def __repr__(self):
        return (
            f"UINode({self.display_name}, "
            f"center={self.center}, "
            f"click={self.clickable})"
        )

    def __str__(self):
        return self.__repr__()

    # ─── Creacion desde XML ───────────────────────────────────────────

    @classmethod
    def from_xml_attribs(cls, attribs):
        """
        Crea un UINode a partir de los atributos de un nodo XML.

        Args:
            attribs: Dict de atributos del ElementTree.

        Returns:
            UINode con todos los atributos mapeados.
        """
        def to_bool(val):
            return val == "true"

        return cls(
            text=attribs.get("text", ""),
            resource_id=attribs.get("resource-id", ""),
            class_name=attribs.get("class", ""),
            package=attribs.get("package", ""),
            content_desc=attribs.get("content-desc", ""),
            checkable=to_bool(attribs.get("checkable", "false")),
            checked=to_bool(attribs.get("checked", "false")),
            clickable=to_bool(attribs.get("clickable", "false")),
            enabled=to_bool(attribs.get("enabled", "true")),
            focusable=to_bool(attribs.get("focusable", "false")),
            focused=to_bool(attribs.get("focused", "false")),
            scrollable=to_bool(attribs.get("scrollable", "false")),
            long_clickable=to_bool(attribs.get("long-clickable", "false")),
            password=to_bool(attribs.get("password", "false")),
            selected=to_bool(attribs.get("selected", "false")),
            bounds=attribs.get("bounds", ""),
            naf=to_bool(attribs.get("NAF", "false")),
            index=int(attribs.get("index", "0")),
        )
