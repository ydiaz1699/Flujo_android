"""
selector.py - Motor de busqueda flexible para nodos UI.

Permite buscar nodos por texto, id, clase, atributos, o combinaciones.
Inspirado en selectores CSS / XPath pero adaptado a UI Android.
"""

from typing import List, Optional, Callable
from node import UINode


class Selector:
    """
    Selector de nodos UI.

    Permite construir consultas complejas encadenando filtros.
    Similar a un query builder para la UI de Android.

    Ejemplo:
        sel = Selector(nodes)
        result = sel.text("PELICULA").clickable().first()

        # O busqueda directa
        result = sel.by_id("vod_category_name").with_text("ANIME").first()
    """

    def __init__(self, nodes=None):
        """
        Args:
            nodes: Lista inicial de UINode a filtrar.
        """
        self._nodes: List[UINode] = nodes or []

    def set_nodes(self, nodes):
        """Actualiza la lista de nodos base."""
        self._nodes = nodes
        return self

    @property
    def results(self):
        """Retorna los nodos que cumplen todos los filtros aplicados."""
        return self._nodes

    @property
    def count(self):
        """Cantidad de resultados."""
        return len(self._nodes)

    # ─── Resultados ───────────────────────────────────────────────────

    def first(self) -> Optional[UINode]:
        """Retorna el primer resultado o None."""
        return self._nodes[0] if self._nodes else None

    def last(self) -> Optional[UINode]:
        """Retorna el ultimo resultado o None."""
        return self._nodes[-1] if self._nodes else None

    def all(self) -> List[UINode]:
        """Retorna todos los resultados."""
        return self._nodes

    def at(self, index) -> Optional[UINode]:
        """Retorna el resultado en la posicion index."""
        if 0 <= index < len(self._nodes):
            return self._nodes[index]
        return None

    # ─── Filtros por texto ────────────────────────────────────────────

    def text(self, value, exact=True):
        """
        Filtra por texto visible.

        Args:
            value: Texto a buscar.
            exact: True = coincidencia exacta, False = contiene.
        """
        if exact:
            filtered = [n for n in self._nodes if n.text == value]
        else:
            val_lower = value.lower()
            filtered = [n for n in self._nodes if val_lower in n.text.lower()]
        return Selector(filtered)

    def text_contains(self, value):
        """Filtra nodos cuyo texto contiene el valor (case-insensitive)."""
        return self.text(value, exact=False)

    def text_starts_with(self, value):
        """Filtra nodos cuyo texto empieza con el valor."""
        filtered = [n for n in self._nodes if n.text.startswith(value)]
        return Selector(filtered)

    def text_matches(self, pattern):
        """Filtra nodos cuyo texto coincide con un patron regex."""
        import re
        compiled = re.compile(pattern)
        filtered = [n for n in self._nodes if compiled.search(n.text)]
        return Selector(filtered)

    def with_text(self, value):
        """Alias de text() para encadenamiento mas legible."""
        return self.text(value)

    def has_text(self):
        """Filtra nodos que tienen algun texto visible."""
        return Selector([n for n in self._nodes if n.text])

    # ─── Filtros por resource-id ──────────────────────────────────────

    def by_id(self, resource_id, partial=True):
        """
        Filtra por resource-id.

        Args:
            resource_id: ID completo o parcial.
            partial: Si True, busca substring.
        """
        if partial:
            filtered = [n for n in self._nodes if resource_id in n.resource_id]
        else:
            filtered = [n for n in self._nodes if n.resource_id == resource_id]
        return Selector(filtered)

    def id_exact(self, full_id):
        """Filtra por ID exacto (incluye package)."""
        return self.by_id(full_id, partial=False)

    # ─── Filtros por clase ────────────────────────────────────────────

    def by_class(self, class_name, short=True):
        """
        Filtra por nombre de clase.

        Args:
            class_name: Nombre de la clase (corto o completo).
            short: Si True, compara solo el nombre corto.
        """
        if short:
            filtered = [
                n for n in self._nodes
                if n.short_class == class_name or n.class_name == class_name
            ]
        else:
            filtered = [n for n in self._nodes if n.class_name == class_name]
        return Selector(filtered)

    def textview(self):
        """Filtra solo TextViews."""
        return self.by_class("TextView")

    def imageview(self):
        """Filtra solo ImageViews."""
        return self.by_class("ImageView")

    def button(self):
        """Filtra solo Buttons."""
        return self.by_class("Button")

    def layout(self):
        """Filtra solo Layouts (Linear, Relative, Frame, Constraint)."""
        return Selector([
            n for n in self._nodes
            if "Layout" in n.class_name
        ])

    # ─── Filtros por content-desc ─────────────────────────────────────

    def by_desc(self, desc, exact=True):
        """Filtra por content-description (accesibilidad)."""
        if exact:
            filtered = [n for n in self._nodes if n.content_desc == desc]
        else:
            d = desc.lower()
            filtered = [n for n in self._nodes if d in n.content_desc.lower()]
        return Selector(filtered)

    # ─── Filtros por atributos booleanos ──────────────────────────────

    def clickable(self, value=True):
        """Filtra por clickable."""
        return Selector([n for n in self._nodes if n.clickable == value])

    def focusable(self, value=True):
        """Filtra por focusable."""
        return Selector([n for n in self._nodes if n.focusable == value])

    def focused(self, value=True):
        """Filtra por focused."""
        return Selector([n for n in self._nodes if n.focused == value])

    def scrollable(self, value=True):
        """Filtra por scrollable."""
        return Selector([n for n in self._nodes if n.scrollable == value])

    def enabled(self, value=True):
        """Filtra por enabled."""
        return Selector([n for n in self._nodes if n.enabled == value])

    def selected(self, value=True):
        """Filtra por selected."""
        return Selector([n for n in self._nodes if n.selected == value])

    def long_clickable(self, value=True):
        """Filtra por long-clickable."""
        return Selector([n for n in self._nodes if n.long_clickable == value])

    # ─── Filtros por posicion / geometria ─────────────────────────────

    def in_region(self, x1, y1, x2, y2):
        """Filtra nodos cuyo centro esta dentro de una region."""
        filtered = []
        for n in self._nodes:
            cx, cy = n.center
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                filtered.append(n)
        return Selector(filtered)

    def larger_than(self, min_area):
        """Filtra nodos con area mayor a min_area."""
        return Selector([n for n in self._nodes if n.area > min_area])

    def smaller_than(self, max_area):
        """Filtra nodos con area menor a max_area."""
        return Selector([n for n in self._nodes if n.area < max_area])

    def visible(self):
        """Filtra nodos con area > 0 (visibles)."""
        return Selector([n for n in self._nodes if n.area > 0])

    # ─── Filtros por jerarquia ────────────────────────────────────────

    def with_parent_id(self, parent_id):
        """Filtra nodos cuyo padre tiene un ID especifico."""
        filtered = [
            n for n in self._nodes
            if n.parent and parent_id in n.parent.resource_id
        ]
        return Selector(filtered)

    def at_depth(self, depth):
        """Filtra por profundidad en el arbol."""
        return Selector([n for n in self._nodes if n.depth == depth])

    def is_leaf(self):
        """Filtra nodos hoja (sin hijos)."""
        return Selector([n for n in self._nodes if n.is_leaf])

    def has_children(self):
        """Filtra nodos que tienen hijos."""
        return Selector([n for n in self._nodes if not n.is_leaf])

    # ─── Filtros personalizados ───────────────────────────────────────

    def where(self, predicate: Callable[[UINode], bool]):
        """
        Filtra con una funcion personalizada.

        Args:
            predicate: Funcion que recibe un UINode y retorna bool.

        Ejemplo:
            sel.where(lambda n: n.text and "HD" in n.text)
        """
        return Selector([n for n in self._nodes if predicate(n)])

    # ─── Combinadores ─────────────────────────────────────────────────

    def union(self, other):
        """Combina resultados de dos selectores (OR)."""
        combined = list(self._nodes)
        for n in other._nodes:
            if n not in combined:
                combined.append(n)
        return Selector(combined)

    def intersect(self, other):
        """Interseccion de dos selectores (AND)."""
        other_set = set(id(n) for n in other._nodes)
        filtered = [n for n in self._nodes if id(n) in other_set]
        return Selector(filtered)

    # ─── Transformaciones ─────────────────────────────────────────────

    def get_clickable_targets(self):
        """
        Para cada nodo, obtiene su target clickeable (padre o si mismo).

        Retorna un nuevo Selector con los targets (sin duplicados).
        """
        targets = []
        seen_ids = set()
        for n in self._nodes:
            target = n.find_clickable_parent()
            if id(target) not in seen_ids:
                targets.append(target)
                seen_ids.add(id(target))
        return Selector(targets)

    def get_parents(self):
        """Retorna los padres de todos los nodos."""
        parents = []
        seen = set()
        for n in self._nodes:
            if n.parent and id(n.parent) not in seen:
                parents.append(n.parent)
                seen.add(id(n.parent))
        return Selector(parents)

    def get_children(self):
        """Retorna todos los hijos directos de los nodos."""
        children = []
        for n in self._nodes:
            children.extend(n.children)
        return Selector(children)

    # ─── Ordenamiento ─────────────────────────────────────────────────

    def sort_by_position(self, left_to_right=True):
        """Ordena por posicion (izquierda a derecha, arriba a abajo)."""
        if left_to_right:
            sorted_nodes = sorted(self._nodes, key=lambda n: (n.y1, n.x1))
        else:
            sorted_nodes = sorted(self._nodes, key=lambda n: (n.x1, n.y1))
        return Selector(sorted_nodes)

    def sort_by_area(self, largest_first=True):
        """Ordena por area."""
        sorted_nodes = sorted(
            self._nodes, key=lambda n: n.area, reverse=largest_first
        )
        return Selector(sorted_nodes)

    # ─── Info y debug ─────────────────────────────────────────────────

    def describe(self):
        """Imprime descripcion de los resultados."""
        print(f"\n{'─'*50}")
        print(f"  Selector: {self.count} resultado(s)")
        print(f"{'─'*50}")
        for i, node in enumerate(self._nodes):
            print(f"  [{i}] {node}")
        print(f"{'─'*50}\n")
        return self

    def texts(self):
        """Retorna lista de textos de los resultados."""
        return [n.text for n in self._nodes if n.text]

    def ids(self):
        """Retorna lista de resource-ids de los resultados."""
        return [n.resource_id for n in self._nodes if n.resource_id]

    def __len__(self):
        return len(self._nodes)

    def __iter__(self):
        return iter(self._nodes)

    def __getitem__(self, index):
        return self._nodes[index]

    def __bool__(self):
        return len(self._nodes) > 0

    def __repr__(self):
        return f"Selector({self.count} nodes)"
