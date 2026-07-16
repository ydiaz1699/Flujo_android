#!/usr/bin/env python3
"""
main.py - CLI y demo del framework mgandroid-driver.

Punto de entrada principal. Proporciona:
- Menu interactivo para controlar MGAndroid.
- Comandos CLI para automatizacion.
- Ejemplos de uso del framework.

Uso:
    python main.py                  # Menu interactivo
    python main.py --crawl          # Crawl completo
    python main.py --categories     # Solo categorias
    python main.py --channels 20    # Listar 20 canales
    python main.py --status         # Estado actual
"""

import argparse
import sys
import time
import logging

from device import Device, DeviceError
from mgandroid import MGAndroid
from crawler import Crawler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def print_header():
    print("\n" + "=" * 55)
    print("   MGAndroid Driver - Framework de Automatizacion")
    print("=" * 55)


def check_device(mg):
    """Verifica conexion al dispositivo."""
    if not mg.device.is_connected():
        print("\n  [!] Sin dispositivo conectado.")
        print("      adb connect <IP>:5555")
        return False

    info = mg.device.info()
    print(f"\n  Dispositivo: {info['model']} (Android {info['android']})")
    print(f"  Resolucion:  {info['resolution']}")
    return True


def cmd_status(mg):
    """Muestra estado actual de la app."""
    print("\n--- Estado de MGAndroid ---")
    try:
        status = mg.status()
        print(f"  Running:     {status['running']}")
        print(f"  On Home:     {status['on_home']}")
        print(f"  Version:     {status['version']}")
        print(f"  Canal:       {status['channel']}")
        print(f"  Velocidad:   {status['speed']}")
        print(f"  Categorias:  {status['categories']}")
        print(f"\n  Textos visibles ({len(status['texts'])}):")
        for t in status['texts']:
            print(f"    - {t}")
    except DeviceError as e:
        print(f"  Error: {e}")


def cmd_categories(mg):
    """Lista y navega categorias."""
    print("\n--- Categorias ---")
    cats = mg.categories()
    for name, node in cats.items():
        print(f"  {name:12s} -> centro: {node.center}")
    return cats


def cmd_crawl(mg, channels_count=10):
    """Crawl completo."""
    crawler = Crawler(mg=mg)
    data = crawler.crawl_all(channels_count=channels_count)
    crawler.summary()
    return data


def cmd_channels(mg, count=10):
    """Lista canales en vivo."""
    print(f"\n--- Recorriendo {count} canales ---\n")
    channels = mg.list_channels(count=count)
    print(f"\n  Total: {len(channels)} canales")
    return channels


def interactive_menu(mg):
    """Menu interactivo."""
    while True:
        print("\n" + "-" * 40)
        print("  MENU - MGAndroid Driver")
        print("-" * 40)
        print("  1. Estado de la app")
        print("  2. Abrir app")
        print("  3. Categorias")
        print("  4. Ir a categoria...")
        print("  5. Canales en vivo")
        print("  6. Historial")
        print("  7. Favoritos")
        print("  8. Crawl completo")
        print("  9. Screenshot")
        print("  10. Dump UI (arbol)")
        print("  11. Click por texto...")
        print("  12. Reiniciar app")
        print("  0. Salir")
        print("-" * 40)

        try:
            opt = input("  > ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        try:
            if opt == "1":
                cmd_status(mg)
            elif opt == "2":
                mg.open()
                print("  App abierta.")
            elif opt == "3":
                cmd_categories(mg)
            elif opt == "4":
                cats = mg.categories()
                print(f"  Disponibles: {list(cats.keys())}")
                name = input("  Categoria: ").strip()
                if name:
                    mg.device.click_text(name, wait=3.0)
                    print(f"  Navegado a: {name}")
            elif opt == "5":
                n = input("  Cantidad [10]: ").strip()
                cmd_channels(mg, int(n) if n else 10)
            elif opt == "6":
                mg.open_history()
                print("  Historial abierto.")
            elif opt == "7":
                mg.open_favorites()
                print("  Favoritos abiertos.")
            elif opt == "8":
                cmd_crawl(mg)
            elif opt == "9":
                mg.screenshot("screenshots/manual_capture.png")
                print("  Captura guardada.")
            elif opt == "10":
                mg.device.refresh()
                mg.device.tree.print_tree(max_depth=3)
            elif opt == "11":
                text = input("  Texto: ").strip()
                if text:
                    mg.device.click_text(text)
                    print(f"  Tap en: {text}")
            elif opt == "12":
                mg.restart()
                print("  App reiniciada.")
            elif opt == "0":
                print("  Bye!")
                break
            else:
                print("  Opcion invalida.")
        except DeviceError as e:
            print(f"\n  [ERROR] {e}")
        except Exception as e:
            print(f"\n  [ERROR] {e}")


def main():
    parser = argparse.ArgumentParser(
        description="MGAndroid Driver - Framework de Automatizacion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python main.py                   Menu interactivo
  python main.py --crawl           Crawl completo
  python main.py --categories      Listar categorias
  python main.py --channels 20     Recorrer 20 canales
  python main.py --status          Estado actual

Uso como libreria:
  from mgandroid import MGAndroid
  mg = MGAndroid()
  mg.open()
  mg.go_movies()
        """,
    )
    parser.add_argument("--crawl", action="store_true", help="Crawl completo")
    parser.add_argument("--categories", action="store_true", help="Listar categorias")
    parser.add_argument("--channels", type=int, metavar="N", help="Recorrer N canales")
    parser.add_argument("--status", action="store_true", help="Estado de la app")
    parser.add_argument("--device", "-s", type=str, help="Serial del dispositivo")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Inicializar
    mg = MGAndroid(serial=args.device)

    print_header()
    if not check_device(mg):
        sys.exit(1)

    try:
        if args.crawl:
            cmd_crawl(mg)
        elif args.categories:
            cmd_categories(mg)
        elif args.channels:
            cmd_channels(mg, args.channels)
        elif args.status:
            cmd_status(mg)
        else:
            interactive_menu(mg)
    except KeyboardInterrupt:
        print("\n  Interrumpido.")
    except DeviceError as e:
        print(f"\n  [FATAL] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
