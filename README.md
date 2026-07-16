# Android TV Bot

Bot de automatizacion para **MGAndroid** en Android TV via ADB.

Navega la interfaz de forma inteligente usando el arbol de UI (`uiautomator dump`) en lugar de coordenadas fijas, lo que lo hace resistente a cambios de resolucion o layout.

## Estructura del Proyecto

```
android-tv-bot/
├── main.py            # Punto de entrada (CLI + menu interactivo)
├── adb.py             # Wrapper de ADB (tap, key, swipe, apps, etc)
├── parser.py          # Parser de ui.xml (buscar por texto/id/clase)
├── navigation.py      # Navegacion inteligente basada en UI
├── capture.py         # Sesiones de captura (screenshots + dumps)
├── dumps/             # UI dumps XML (organizados por sesion)
├── screenshots/       # Capturas de pantalla (organizadas por sesion)
└── README.md
```

## Requisitos

- **Python 3.7+** (usa dataclasses, f-strings, pathlib)
- **ADB** (Android Debug Bridge) instalado y en el PATH
- Dispositivo Android TV con **depuracion USB/red habilitada**
- App **MGAndroid** (`com.android.mgandroid`) instalada en el dispositivo

### Instalar ADB

```bash
# Ubuntu/Debian
sudo apt install adb

# macOS (con Homebrew)
brew install android-platform-tools

# Windows: descargar de https://developer.android.com/tools/releases/platform-tools
```

## Conexion al Dispositivo

```bash
# Por red (TV Box)
adb connect 192.168.1.XXX:5555

# Verificar conexion
adb devices
```

## Uso

### Menu Interactivo (por defecto)

```bash
python main.py
```

Muestra un menu con opciones:
1. Info del dispositivo y app
2. Escanear categorias
3. Escanear canales en vivo
4. Escaneo completo
5. Quick dump (UI actual)
6. Screenshot
7. Navegar a categoria
8. Tap por texto
9. Abrir/reiniciar app

### Linea de Comandos

```bash
# Escaneo completo automatico (categorias + canales)
python main.py --scan

# Solo escanear categorias (VIVO, SERIE, PELICULA, ANIME, ESPECIAL)
python main.py --categories

# Capturar N canales en vivo
python main.py --channels 20

# Mostrar info del dispositivo y app
python main.py --info

# Quick dump de la pantalla actual
python main.py --dump

# Especificar dispositivo (si hay multiples)
python main.py --scan --device 192.168.1.100:5555

# Modo verbose (debug)
python main.py --scan -v
```

## Como Funciona

### Enfoque Basado en UI (no coordenadas fijas)

En lugar de hacer `tap(500, 300)` con coordenadas hardcodeadas, el bot:

```
1. Ejecuta uiautomator dump → obtiene ui.xml
2. Parsea el XML → encuentra el elemento por texto/id
3. Lee sus bounds → [x1,y1][x2,y2]
4. Calcula el centro → (x1+x2)/2, (y1+y2)/2
5. Hace tap en el centro calculado
```

Esto significa que si cambia la resolucion, el layout, o las posiciones, **el bot sigue funcionando** sin modificar codigo.

### Ejemplo: Navegar a "PELICULA"

```python
from adb import ADB
from navigation import Navigator

adb = ADB()
nav = Navigator(adb=adb)

# El bot busca "PELICULA" en la UI y calcula donde hacer tap
nav.go_to_category("PELICULA")
```

### Ejemplo: Buscar y tocar cualquier texto

```python
# Busca el texto en pantalla y toca automaticamente
nav.tap_text("Discovery World HD+")
```

### Ejemplo: Esperar a que aparezca un elemento

```python
# Espera hasta 15 segundos a que el texto aparezca
element = nav.wait_for_text("Cargando...", timeout=15)
```

## Uso como Libreria

```python
from adb import ADB
from parser import UIParser
from navigation import Navigator
from capture import CaptureSession

# Inicializar
adb = ADB(device_serial="192.168.1.100:5555")
nav = Navigator(adb=adb)
session = CaptureSession(adb=adb)

# Verificar conexion
assert adb.is_connected()

# Abrir la app
adb.start_app("com.android.mgandroid")
adb.sleep(5)

# Obtener categorias disponibles
cats = nav.get_categories()
print(cats)  # {'VIVO': UIElement(...), 'SERIE': ..., ...}

# Navegar a una categoria
nav.go_to_category("ANIME")

# Capturar pantalla actual
session.capture(label="anime_home")

# Ver que canal esta en vivo
channel = nav.get_current_channel()
print(f"Canal: {channel}")

# Recorrer todas las categorias con capturas
session.capture_all_categories(nav)

# Guardar log JSON de la sesion
session.save_log()
```

## Modulos

### `adb.py` - Wrapper ADB

| Metodo | Descripcion |
|--------|-------------|
| `run(cmd)` | Ejecuta comando ADB generico |
| `is_connected()` | Verifica si hay dispositivo |
| `tap(x, y)` | Toca coordenadas |
| `key(keycode)` | Envia keyevent |
| `swipe(x1,y1,x2,y2)` | Gesto de deslizar |
| `start_app(pkg)` | Abre aplicacion |
| `force_stop(pkg)` | Cierra aplicacion |
| `dump_ui()` | Ejecuta uiautomator dump |
| `screenshot(path)` | Captura de pantalla |
| `dpad_up/down/left/right()` | Control remoto virtual |
| `home()` / `back()` | Botones de navegacion |

### `parser.py` - Parser de UI XML

| Metodo | Descripcion |
|--------|-------------|
| `parse_file(path)` | Carga y parsea ui.xml |
| `find_by_text(text)` | Busca por texto visible |
| `find_by_id(id)` | Busca por resource-id |
| `find_clickable()` | Elementos clickeables |
| `find_focused()` | Elemento con foco |
| `find(**kwargs)` | Busqueda flexible multi-atributo |
| `get_categories()` | Categorias de MGAndroid |
| `get_all_texts()` | Todos los textos en pantalla |
| `summary()` | Resumen visual de la UI |
| `print_tree()` | Arbol de elementos |

### `navigation.py` - Navegacion Inteligente

| Metodo | Descripcion |
|--------|-------------|
| `refresh_ui()` | Actualiza estado de la UI |
| `tap_text(text)` | Busca texto y hace tap |
| `tap_id(id)` | Busca por ID y hace tap |
| `go_to_category(name)` | Navega a categoria |
| `iterate_categories()` | Recorre todas las categorias |
| `wait_for_text(text)` | Espera que aparezca texto |
| `get_current_channel()` | Canal en vivo actual |
| `scroll_down/up/left/right()` | Gestos de scroll |
| `go_home()` | Vuelve al inicio |
| `is_on_home()` | Verifica si esta en home |

### `capture.py` - Sesiones de Captura

| Metodo | Descripcion |
|--------|-------------|
| `capture(label)` | Screenshot + dump con etiqueta |
| `screenshot(label)` | Solo captura de pantalla |
| `dump(label)` | Solo UI dump |
| `capture_all_categories()` | Recorre y captura categorias |
| `capture_channel_list(n)` | Captura N canales |
| `save_log()` | Guarda log JSON de sesion |
| `export_texts()` | Exporta textos encontrados |

## Keycodes Utiles (Android TV)

| Keycode | Valor | Descripcion |
|---------|-------|-------------|
| HOME | 3 | Ir al inicio |
| BACK | 4 | Retroceder |
| DPAD_UP | 19 | Arriba |
| DPAD_DOWN | 20 | Abajo |
| DPAD_LEFT | 21 | Izquierda |
| DPAD_RIGHT | 22 | Derecha |
| DPAD_CENTER | 23 | OK / Enter |
| ENTER | 66 | Enter |
| MENU | 82 | Menu |
| VOLUME_UP | 24 | Subir volumen |
| VOLUME_DOWN | 25 | Bajar volumen |
| MUTE | 164 | Silenciar |
| MEDIA_PLAY_PAUSE | 85 | Play/Pausa |
| MEDIA_STOP | 86 | Detener |

## Salida

Los archivos se organizan por sesion:

```
dumps/
└── session_20260716_150500/
    ├── 001_home.xml
    ├── 002_cat_VIVO.xml
    ├── 003_cat_SERIE.xml
    ├── ...
    ├── session_log.json
    └── texts_report.txt

screenshots/
└── session_20260716_150500/
    ├── 001_home.png
    ├── 002_cat_VIVO.png
    └── ...
```

## Proximos Pasos

- [ ] Extraer lista completa de canales por categoria
- [ ] Automatizar reproduccion y validacion de streams
- [ ] Detectar errores de carga / buffering
- [ ] Exportar lista de canales a CSV/JSON
- [ ] Agregar soporte para EPG (guia de programacion)
- [ ] Notificaciones (Telegram/Discord) si un canal falla
