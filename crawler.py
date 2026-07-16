"""
crawler.py - Recorrido automatico de pantallas con exportacion.

Navega sistematicamente por la app, capturando la estructura
de cada pantalla y exportando los datos encontrados.
"""

import time
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Callable

from device import Device
from mgandroid import MGAndroid
from node import UINode

logger = logging.getLogger(__name__)


class CrawlResult:
    """Resultado de una pantalla crawleada."""

    def __init__(self, label, texts, nodes_count, screenshot_path=None, dump_path=None):
        self.label = label
        self.texts = texts
        self.nodes_count = nodes_count
        self.screenshot_path = screenshot_path
        self.dump_path = dump_path
        self.timestamp = datetime.now().isoformat()
        self.children_results: List["CrawlResult"] = []

    def to_dict(self):
        return {
            "label": self.label,
            "timestamp": self.timestamp,
            "texts": self.texts,
            "nodes_count": self.nodes_count,
            "screenshot": self.screenshot_path,
            "dump": self.dump_path,
            "children": [c.to_dict() for c in self.children_results],
        }


class Crawler:
    """
    Crawler automatico para MGAndroid.

    Recorre pantallas, captura datos y exporta resultados.
    """

    def __init__(self, mg: MGAndroid = None, output_dir="crawl_output"):
        """
        Args:
            mg: Instancia de MGAndroid.
            output_dir: Directorio base para resultados.
        """
        self.mg = mg or MGAndroid()
        self.device = self.mg.device

        # Directorio de salida con timestamp
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = Path(output_dir) / f"crawl_{ts}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "dumps").mkdir(exist_ok=True)
        (self.output_dir / "screenshots").mkdir(exist_ok=True)

        self.results: List[CrawlResult] = []
        self._step = 0


    def _capture(self, label):
        """Captura screenshot + dump de la pantalla actual."""
        self._step += 1
        safe = label.replace(" ", "_").lower()
        name = f"{self._step:03d}_{safe}"

        # Screenshot
        ss_path = str(self.output_dir / "screenshots" / f"{name}.png")
        try:
            self.device.screenshot(ss_path)
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            ss_path = None

        # Dump
        dump_path = str(self.output_dir / "dumps" / f"{name}.xml")
        try:
            self.device._adb("shell uiautomator dump /sdcard/ui.xml")
            self.device._adb(f"pull /sdcard/ui.xml {dump_path}")
            self.device.tree.parse_file(dump_path)
        except Exception as e:
            logger.error(f"Dump error: {e}")
            dump_path = None

        texts = self.device.tree.get_all_texts()
        count = self.device.tree.node_count

        result = CrawlResult(
            label=label,
            texts=texts,
            nodes_count=count,
            screenshot_path=ss_path,
            dump_path=dump_path,
        )
        self.results.append(result)
        return result

    # ─── Crawl de categorias ──────────────────────────────────────────

    def crawl_categories(self, wait=3.0):
        """
        Recorre todas las categorias de la app.

        Returns:
            Dict {categoria: CrawlResult}
        """
        logger.info("\n" + "=" * 50)
        logger.info("  CRAWLING CATEGORIAS")
        logger.info("=" * 50)

        # Capturar home
        self.mg.back_home()
        time.sleep(1)
        home_result = self._capture("home")

        categories = self.mg.categories(refresh=False)
        cat_results = {}

        for name, node in categories.items():
            logger.info(f"\n  >> Entrando a: {name}")

            # Tap en la categoria
            self.device.click_node(node, wait=wait)

            # Capturar
            result = self._capture(f"cat_{name}")
            cat_results[name] = result
            home_result.children_results.append(result)

            # Volver
            self.device.back()
            time.sleep(1.5)

        logger.info(f"\n  Categorias crawleadas: {len(cat_results)}")
        return cat_results


    # ─── Crawl de canales ─────────────────────────────────────────────

    def crawl_channels(self, count=10, wait=2.0):
        """
        Recorre N canales en vivo.

        Args:
            count: Cantidad de canales.
            wait: Espera entre cambios.

        Returns:
            Lista de dicts con info de canales.
        """
        logger.info(f"\n  CRAWLING {count} CANALES")

        channels = []
        for i in range(count):
            self.device.refresh()
            name = self.device.tree.get_live_channel()
            speed = self.device.tree.get_speed()

            ch = {
                "index": i + 1,
                "name": name or "Desconocido",
                "speed": speed,
            }
            channels.append(ch)
            logger.info(f"    {i+1:3d}. {ch['name']} ({speed})")

            # Captura cada 5 canales
            if (i + 1) % 5 == 0 or i == 0:
                self._capture(f"channel_{i+1:02d}_{name or 'unknown'}")

            self.mg.channel_down(wait=wait)

        return channels

    # ─── Crawl completo ───────────────────────────────────────────────

    def crawl_all(self, channels_count=10):
        """
        Crawl completo: home + categorias + canales.

        Returns:
            Dict con todos los resultados.
        """
        logger.info("\n" + "#" * 55)
        logger.info("  CRAWL COMPLETO - MGAndroid")
        logger.info("#" * 55 + "\n")

        all_data = {
            "session": self.output_dir.name,
            "started": datetime.now().isoformat(),
            "device": {},
            "app_version": None,
            "categories": {},
            "channels": [],
        }

        # Info del dispositivo
        try:
            all_data["device"] = self.device.info()
        except Exception:
            pass

        # Version
        all_data["app_version"] = self.mg.version()

        # Categorias
        cat_results = self.crawl_categories()
        all_data["categories"] = {
            name: r.to_dict() for name, r in cat_results.items()
        }

        # Canales
        self.mg.back_home()
        time.sleep(2)
        all_data["channels"] = self.crawl_channels(count=channels_count)

        # Timestamp final
        all_data["finished"] = datetime.now().isoformat()

        # Guardar
        self.save_report(all_data)
        return all_data

    # ─── Crawl personalizado ──────────────────────────────────────────

    def crawl_category_items(self, category_name, max_items=20, wait=2.0):
        """
        Entra a una categoria y recorre sus items con scroll.

        Args:
            category_name: Nombre de la categoria (VIVO, SERIE, etc).
            max_items: Maximo de items a intentar descubrir.
            wait: Espera entre scrolls.

        Returns:
            Lista de textos/items encontrados.
        """
        # Navegar a la categoria
        self.mg.back_home()
        time.sleep(1)
        self.device.click_text(category_name, wait=wait)

        all_texts = set()
        no_change_count = 0

        for i in range(max_items):
            self.device.refresh()
            new_texts = set(self.device.tree.get_all_texts())

            # Ver si hay textos nuevos
            prev_count = len(all_texts)
            all_texts.update(new_texts)

            if len(all_texts) == prev_count:
                no_change_count += 1
                if no_change_count >= 3:
                    logger.info("  Sin contenido nuevo, finalizando.")
                    break
            else:
                no_change_count = 0

            self._capture(f"{category_name}_scroll_{i+1}")

            # Scroll para ver mas
            self.device.scroll_down()
            time.sleep(wait)

        self.device.back()
        return sorted(all_texts)


    # ─── Exportacion ──────────────────────────────────────────────────

    def save_report(self, data=None):
        """
        Guarda reporte JSON y texto del crawl.

        Args:
            data: Dict con los datos (o genera uno basico).
        """
        if data is None:
            data = {
                "session": self.output_dir.name,
                "results": [r.to_dict() for r in self.results],
            }

        # JSON
        json_path = self.output_dir / "report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"  Reporte JSON: {json_path}")

        # Texto plano
        txt_path = self.output_dir / "report.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"CRAWL REPORT - {self.output_dir.name}\n")
            f.write("=" * 60 + "\n\n")

            for result in self.results:
                f.write(f"--- {result.label} ---\n")
                f.write(f"    Nodos: {result.nodes_count}\n")
                f.write(f"    Textos:\n")
                for t in result.texts:
                    f.write(f"      - {t}\n")
                f.write("\n")

        logger.info(f"  Reporte TXT: {txt_path}")

        return str(json_path)

    def export_channels_csv(self, channels):
        """Exporta lista de canales a CSV."""
        csv_path = self.output_dir / "channels.csv"
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("index,name,speed\n")
            for ch in channels:
                name = ch.get("name", "").replace(",", ";")
                f.write(f"{ch['index']},{name},{ch.get('speed', '')}\n")
        logger.info(f"  Canales CSV: {csv_path}")
        return str(csv_path)

    def export_texts(self):
        """Exporta todos los textos unicos encontrados."""
        all_texts = set()
        for result in self.results:
            all_texts.update(result.texts)

        txt_path = self.output_dir / "all_texts.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            for text in sorted(all_texts):
                f.write(f"{text}\n")
        logger.info(f"  Textos exportados: {txt_path} ({len(all_texts)} unicos)")
        return sorted(all_texts)

    # ─── Resumen ──────────────────────────────────────────────────────

    def summary(self):
        """Imprime resumen del crawl."""
        print(f"\n{'='*55}")
        print(f"  CRAWL SUMMARY")
        print(f"{'='*55}")
        print(f"  Sesion:     {self.output_dir.name}")
        print(f"  Capturas:   {len(self.results)}")
        print(f"  Directorio: {self.output_dir}")
        print(f"\n  Pantallas:")
        for r in self.results:
            print(f"    - {r.label} ({r.nodes_count} nodos, {len(r.texts)} textos)")
        print(f"{'='*55}\n")
