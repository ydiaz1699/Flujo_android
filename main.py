#!/usr/bin/env python3
"""
main.py - Punto de entrada del Android TV Bot.

Bot de automatizacion para MGAndroid en Android TV.
Navega la app, captura pantallas, extrae informacion de la UI.

Uso:
    python main.py                  # Menu interactivo
    python main.py --scan           # Escaneo completo automatico
    python main.py --categories     # Recorrer categorias
    python main.py --channels 20    # Capturar 20 canales en vivo
    python main.py --info           # Info del dispositivo + app
    python main.py --dump           # Solo dump UI de la pantalla actual
"""

import argparse
import sys
import time
import logging
from pathlib import Path

from adb import ADB, ADBError
from parser import UIParser
from navigation import Navigator, NavigationError
from capture import CaptureSession

# ─── Configuracion de logging ─────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── Constantes ───────────────────────────────────────────────────────

PACKAGE = "com.android.mgandroid"
PROJECT_DIR = Path(__file__).parent


# ─── Funciones principales ────────────────────────────────────────────

def check_connection(adb):
    """Verifica conexion ADB y muestra info del dispositivo."""
    print("\n" + "=" * 60)
    print("  ANDROID TV BOT - MGAndroid")
    print("=" * 60)

    if not adb.is_connected():
        print("\n  [!] No se detecto ningun dispositivo.")
        print("      Verifica que ADB esta habilitado en el TV box.")
        print("      Comando: adb connect <IP_DEL_DISPOSITIVO>")
        return False

    info = adb.get_device_info()
    print(f"\n  Dispositivo conectado:")
    print(f"    Modelo:   {info['model']}")
    print(f"    Android:  {info['android_version']}")
    print(f"    SDK:      {info['sdk']}")
    print(f"    Pantalla: {info['resolution']}")
    print(f"    Densidad: {info['density']}")
    print("=" * 60)
    return True


def show_app_info(nav):
    """Muestra informacion de la app en pantalla."""
    print("\n--- Informacion de la App ---")

    info = nav.get_screen_info()

    print(f"  Version:       {info.get('version', 'N/A')}")
    print(f"  Canal actual:  {info.get('channel', 'N/A')}")
    print(f"  Elementos UI:  {info.get('total_elements', 0)}")
    print(f"  Clickeables:   {info.get('clickable_count', 0)}")
    print(f"  Scrolleables:  {info.get('scrollable_count', 0)}")

    print(f"\n  Textos visibles:")
    for text in info.get("texts", []):
        print(f"    - {text}")


def scan_categories(nav, session):
    """Escanea todas las categorias con captura."""
    print("\n--- Escaneando Categorias ---\n")

    results = session.capture_all_categories(nav, wait=3.0)

    print(f"\n--- Resultados ---")
    for name, result in results.items():
        texts = result.get("texts", [])
        print(f"\n  [{name}]")
        print(f"    Elementos: {result.get('element_count', '?')}")
        print(f"    Textos:    {len(texts)}")
        if texts[:5]:
            for t in texts[:5]:
                print(f"      - {t}")
            if len(texts) > 5:
                print(f"      ... (+{len(texts)-5} mas)")

    # Guardar log
    session.save_log()
    session.export_texts()

    print(f"\n  Archivos guardados en: {session.dumps_dir}")
    return results


def scan_channels(nav, session, count=10):
    """Escanea canales en vivo."""
    print(f"\n--- Escaneando {count} Canales en Vivo ---\n")

    channels = session.capture_channel_list(nav, num_channels=count, wait=2.0)

    print(f"\n--- Canales Encontrados ---")
    for ch in channels:
        print(f"  {ch['index']:3d}. {ch['name']}")

    session.save_log()
    print(f"\n  Log guardado en: {session.dumps_dir}")
    return channels


def full_scan(nav, session):
    """Escaneo completo: info + categorias + canales."""
    print("\n" + "=" * 60)
    print("  ESCANEO COMPLETO")
    print("=" * 60)

    # 1. Info de la app
    show_app_info(nav)

    # 2. Captura de home
    session.capture(label="home")

    # 3. Categorias
    scan_categories(nav, session)

    # Volver a home para canales
    nav.go_home()
    time.sleep(3)

    # 4. Canales (primeros 10)
    scan_channels(nav, session, count=10)

    # Resumen final
    print("\n" + "=" * 60)
    print("  ESCANEO COMPLETADO")
    print("=" * 60)
    summary = session.get_summary()
    print(f"  Sesion:    {summary['session']}")
    print(f"  Capturas:  {summary['total_captures']}")
    print(f"  Carpeta:   {summary['dumps_dir']}")
    print("=" * 60 + "\n")


def quick_dump(adb):
    """Hace un dump rapido de la UI actual y muestra el resumen."""
    print("\n--- Quick UI Dump ---\n")

    parser = UIParser()
    adb.dump_ui("/sdcard/ui.xml")
    adb.pull_file("/sdcard/ui.xml", str(PROJECT_DIR / "dumps" / "quick_dump.xml"))

    parser.parse_file(str(PROJECT_DIR / "dumps" / "quick_dump.xml"))
    parser.summary()

    print("\n  Arbol de UI (profundidad 3):")
    parser.print_tree(max_depth=3)


def interactive_menu(adb, nav, session):
    """Menu interactivo para controlar el bot."""
    while True:
        print("\n" + "-" * 40)
        print("  MENU PRINCIPAL")
        print("-" * 40)
        print("  1. Info del dispositivo y app")
        print("  2. Escanear categorias")
        print("  3. Escanear canales en vivo")
        print("  4. Escaneo completo")
        print("  5. Quick dump (UI actual)")
        print("  6. Screenshot")
        print("  7. Navegar a categoria...")
        print("  8. Tap por texto...")
        print("  9. Abrir/reiniciar app")
        print("  0. Salir")
        print("-" * 40)

        try:
            choice = input("  Opcion: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Saliendo...")
            break

        try:
            if choice == "1":
                show_app_info(nav)

            elif choice == "2":
                scan_categories(nav, session)

            elif choice == "3":
                count = input("  Cantidad de canales [10]: ").strip()
                count = int(count) if count else 10
                scan_channels(nav, session, count)

            elif choice == "4":
                full_scan(nav, session)

            elif choice == "5":
                quick_dump(adb)

            elif choice == "6":
                label = input("  Nombre [screenshot]: ").strip() or "screenshot"
                result = session.screenshot(label=label)
                print(f"  Guardado: {result['screenshot_path']}")

            elif choice == "7":
                cats = nav.get_categories()
                print(f"  Categorias: {list(cats.keys())}")
                cat = input("  Categoria: ").strip()
                if cat:
                    nav.go_to_category(cat)
                    session.capture(label=f"nav_{cat}")
                    print(f"  Navegado a: {cat}")

            elif choice == "8":
                text = input("  Texto del boton: ").strip()
                if text:
                    elem = nav.tap_text(text, exact=False)
                    print(f"  Tap en: {elem}")

            elif choice == "9":
                adb.force_stop(PACKAGE)
                time.sleep(1)
                adb.start_app(PACKAGE)
                time.sleep(4)
                print("  App reiniciada.")

            elif choice == "0":
                print("  Hasta luego!")
                break

            else:
                print("  Opcion no valida.")

        except NavigationError as e:
            print(f"\n  [ERROR NAV] {e}")
        except ADBError as e:
            print(f"\n  [ERROR ADB] {e}")
        except Exception as e:
            print(f"\n  [ERROR] {e}")


# ─── Punto de entrada ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Android TV Bot - Automatizacion de MGAndroid",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python main.py                  Menu interactivo
  python main.py --scan           Escaneo completo
  python main.py --categories     Solo categorias
  python main.py --channels 15    Capturar 15 canales
  python main.py --info           Mostrar info
  python main.py --dump           Quick dump de UI
        """,
    )

    parser.add_argument(
        "--scan", action="store_true",
        help="Escaneo completo automatico"
    )
    parser.add_argument(
        "--categories", action="store_true",
        help="Escanear todas las categorias"
    )
    parser.add_argument(
        "--channels", type=int, metavar="N",
        help="Capturar N canales en vivo"
    )
    parser.add_argument(
        "--info", action="store_true",
        help="Mostrar info del dispositivo y app"
    )
    parser.add_argument(
        "--dump", action="store_true",
        help="Quick dump de la UI actual"
    )
    parser.add_argument(
        "--device", "-s", type=str, default=None,
        help="Serial del dispositivo ADB"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Logging detallado (DEBUG)"
    )

    args = parser.parse_args()

    # Nivel de log
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Inicializar ADB
    adb = ADB(device_serial=args.device)

    # Verificar conexion
    if not check_connection(adb):
        sys.exit(1)

    # Inicializar navegador y sesion de captura
    nav = Navigator(adb=adb, dumps_dir=str(PROJECT_DIR / "dumps"))
    session = CaptureSession(adb=adb, base_dir=str(PROJECT_DIR))

    # Ejecutar segun argumentos
    try:
        if args.scan:
            full_scan(nav, session)

        elif args.categories:
            scan_categories(nav, session)

        elif args.channels:
            scan_channels(nav, session, count=args.channels)

        elif args.info:
            show_app_info(nav)

        elif args.dump:
            quick_dump(adb)

        else:
            # Menu interactivo por defecto
            interactive_menu(adb, nav, session)

    except KeyboardInterrupt:
        print("\n\n  Interrumpido por el usuario.")
    except ADBError as e:
        print(f"\n  [ERROR ADB] {e}")
        sys.exit(1)

    # Guardar log si hay capturas
    if session.captures_log:
        session.save_log()
        print(f"\n  Log guardado: {session.dumps_dir}/session_log.json")


if __name__ == "__main__":
    main()
