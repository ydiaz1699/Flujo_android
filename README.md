# MGAndroid Driver

Framework de automatizacion para **MGAndroid** en Android TV via ADB.

Navega la interfaz de forma inteligente usando el arbol de UI (`uiautomator dump`).  
**No depende de coordenadas fijas** — busca elementos por texto/ID, sube al contenedor clickeable padre, y calcula el centro automaticamente.

---

## Arquitectura

```
mgandroid-driver/
├── node.py          # Nodo UI con jerarquia padre/hijo
├── selector.py      # Motor de busqueda (texto, id, clase, atributos)
├── ui.py            # Parser de ui.xml → arbol de nodos
├── device.py        # ADB + tap inteligente (busca target clickeable)
├── app.py           # Ciclo de vida de la app (open, close, wait_ready)
├── mgandroid.py     # API de alto nivel (go_movies, go_live, etc)
├── crawler.py       # Recorrido automatico + exportacion
├── main.py          # CLI + menu interactivo
├── dumps/           # UI dumps XML
├── screenshots/     # Capturas de pantalla
└── crawl_output/    # Resultados de crawls (JSON, CSV, TXT)
```

---

## Como Funciona (el nucleo)

En lugar de `tap(666, 690)` con coordenadas hardcodeadas:

```
1. uiautomator dump → ui.xml
2. Parsear XML → arbol de UINode con relaciones padre/hijo
3. Buscar nodo con texto "PELICULA"
4. El TextView NO es clickeable, pero su contenedor SI
5. Subir al padre clickeable (find_clickable_parent)
6. Leer bounds del padre → [569,678][763,702]
7. Calcular centro → (666, 690)
8. adb shell input tap 666 690
```

```python
# Todo esto sucede internamente con:
mg.device.click_text("PELÍCULA")
```

---

## Requisitos

- **Python 3.7+**
- **ADB** instalado y en PATH
- Dispositivo Android TV con **depuracion USB/red habilitada**
- App **MGAndroid** (`com.android.mgandroid`) instalada

---

## Instalacion

```bash
# Clonar
git clone https://github.com/ydiaz1699/Flujo_android.git
cd Flujo_android

# Conectar dispositivo
adb connect 192.168.1.XXX:5555
adb devices
```

No tiene dependencias externas (solo stdlib de Python).

---

## Uso Rapido

### Como libreria (lo mas potente)

```python
from mgandroid import MGAndroid

mg = MGAndroid()
mg.open()

# Navegar por categorias
mg.go_movies()
mg.go_series()
mg.go_anime()
mg.go_live()

# Acciones rapidas
mg.open_history()
mg.open_favorites()
mg.open_settings()

# Canales en vivo
print(mg.current_channel())
mg.channel_up()
mg.channel_down()
channels = mg.list_channels(count=20)

# Volver al inicio
mg.back_home()

# Estado completo
print(mg.status())
```

### CLI

```bash
# Menu interactivo (por defecto)
python main.py

# Crawl completo (categorias + canales + capturas)
python main.py --crawl

# Solo categorias
python main.py --categories

# Recorrer 20 canales
python main.py --channels 20

# Estado actual
python main.py --status

# Dispositivo especifico
python main.py --crawl --device 192.168.1.100:5555

# Debug verbose
python main.py --crawl -v
```

---

## Modulos en Detalle

### `node.py` — UINode

Cada elemento de la UI es un UINode con:
- Atributos (text, id, class, clickable, focused, bounds...)
- Relacion padre/hijo bidireccional
- `find_clickable_parent()` — sube al primer ancestro clickeable
- `get_tap_target()` — retorna (nodo_target, (x, y))
- `center`, `width`, `height`, `area`
- `tree_str()` — representacion visual del subarbol

```python
node = tree.find_text("PELÍCULA").first()
target, (x, y) = node.get_tap_target()
# target es el RelativeLayout clickeable padre
# (x, y) es su centro calculado
```

### `selector.py` — Selector

Query builder para buscar nodos:

```python
# Encadenamiento de filtros
sel = tree.select()
result = sel.text("ANIME").clickable().first()

# Busqueda flexible
sel.by_id("vod_category_name").has_text().all()
sel.by_class("TextView").in_region(0, 500, 1400, 720).texts()
sel.clickable().larger_than(5000).sort_by_position()

# Filtro personalizado
sel.where(lambda n: "HD" in n.text and n.clickable)
```

### `ui.py` — UITree

Parser que construye el arbol completo:

```python
from ui import UITree

tree = UITree()
tree.parse_file("dumps/home.xml")

# Consultas directas
tree.get_categories()     # {'VIVO': node, 'SERIE': node, ...}
tree.get_live_channel()   # "Discovery World HD+"
tree.get_version()        # "8.7.2"
tree.get_all_texts()      # ["8.7.2", "15:05", "VIVO", ...]

# Selector
tree.select().text("SERIE").first()
tree.find_id("history_btn").first()

# Debug
tree.summary()
tree.print_tree(max_depth=3)
```

### `device.py` — Device

Combina ADB + UITree para tap inteligente:

```python
from device import Device

dev = Device(serial="192.168.1.100:5555")
dev.refresh()  # dump + parse

# Tap inteligente (busca texto → padre clickeable → centro → tap)
dev.click_text("PELÍCULA")
dev.click_id("history_btn")

# Esperas
dev.wait_for_text("Cargando...", timeout=15)

# Control remoto virtual
dev.dpad_up()
dev.dpad_down()
dev.dpad_center()
dev.back()
dev.home()

# Gestos
dev.scroll_down()
dev.swipe(100, 300, 900, 300, 500)
```

### `app.py` — App

Gestiona el ciclo de vida de MGAndroid:

```python
from app import App

app = App(device)
app.open(wait=5)
app.wait_ready(timeout=20)
app.is_on_home()
app.ensure_home()  # Vuelve a home sin importar donde este
app.restart()
app.close()
```

### `mgandroid.py` — MGAndroid

API semantica de alto nivel:

| Metodo | Descripcion |
|--------|-------------|
| `mg.open()` | Abre y espera a que cargue |
| `mg.go_movies()` | Navega a PELICULA |
| `mg.go_series()` | Navega a SERIE |
| `mg.go_anime()` | Navega a ANIME |
| `mg.go_live()` | Navega a VIVO |
| `mg.go_special()` | Navega a ESPECIAL |
| `mg.open_history()` | Abre historial |
| `mg.open_favorites()` | Abre favoritos |
| `mg.open_settings()` | Abre ajustes |
| `mg.current_channel()` | Canal en vivo actual |
| `mg.list_channels(20)` | Recorre 20 canales |
| `mg.search("texto")` | Busca contenido |
| `mg.play_first_result()` | Reproduce primer item |
| `mg.back_home()` | Vuelve a pantalla principal |
| `mg.status()` | Estado completo (dict) |
| `mg.screenshot(path)` | Captura de pantalla |
| `mg.dump()` | UI dump |

### `crawler.py` — Crawler

Recorrido automatico con exportacion:

```python
from crawler import Crawler
from mgandroid import MGAndroid

mg = MGAndroid()
mg.open()

crawler = Crawler(mg=mg)

# Crawl completo
data = crawler.crawl_all(channels_count=15)

# Solo categorias
crawler.crawl_categories()

# Solo canales
channels = crawler.crawl_channels(count=30)
crawler.export_channels_csv(channels)

# Exportar
crawler.save_report()
crawler.export_texts()
crawler.summary()
```

---

## Elementos Conocidos de MGAndroid

| Elemento | resource-id | Notas |
|----------|-------------|-------|
| Logo | `iv_logo` | Pantalla principal |
| Version | `tv_version` | "8.7.2" |
| Hora | `tv_time` | Reloj |
| Ajustes | `iv_setting` | Boton (clickable) |
| Banner | `banner_root` | Carousel principal |
| Historial | `history_btn` | Boton (clickable) |
| Favoritos | `fav_btn` | Boton (clickable) |
| Player | `main_focus_root` | Area de video en vivo |
| Canal | `tv_live_title` | Nombre del canal actual |
| Velocidad | `tv_main_speed` | "82Kb/s" |
| Categorias | `vod_category_name` | VIVO, SERIE, PELICULA... |

---

## Salida del Crawler

```
crawl_output/
└── crawl_20260716_150500/
    ├── dumps/
    │   ├── 001_home.xml
    │   ├── 002_cat_VIVO.xml
    │   ├── 003_cat_SERIE.xml
    │   └── ...
    ├── screenshots/
    │   ├── 001_home.png
    │   └── ...
    ├── report.json          # Datos estructurados
    ├── report.txt           # Resumen legible
    ├── channels.csv         # Lista de canales
    └── all_texts.txt        # Textos unicos encontrados
```

---

## Keycodes Android TV

| Keycode | Valor | Metodo |
|---------|-------|--------|
| HOME | 3 | `dev.home()` |
| BACK | 4 | `dev.back()` |
| DPAD_UP | 19 | `dev.dpad_up()` |
| DPAD_DOWN | 20 | `dev.dpad_down()` |
| DPAD_LEFT | 21 | `dev.dpad_left()` |
| DPAD_RIGHT | 22 | `dev.dpad_right()` |
| DPAD_CENTER | 23 | `dev.dpad_center()` |
| ENTER | 66 | `dev.enter()` |
| MENU | 82 | `dev.menu()` |

---

## Roadmap

- [ ] Extraer EPG (guia de programacion)
- [ ] Monitorear streams (detectar buffering/errores)
- [ ] Exportar lista completa de canales a JSON/CSV
- [ ] Soporte multi-dispositivo simultaneo
- [ ] Notificaciones (Telegram/Discord) si un canal falla
- [ ] Web dashboard para ver estado en tiempo real
- [ ] Automatizar tests de QoS por canal
