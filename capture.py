"""
capture.py - Captura de screenshots y UI dumps organizados.

Maneja la captura sistematica de pantallas y dumps XML,
organizandolos por timestamp, categoria o sesion para
facilitar el analisis posterior.
"""

import time
import json
import logging
from pathlib import Path
from datetime import datetime

from adb import ADB
from parser import UIParser

logger = logging.getLogger(__name__)


class CaptureSession:
    """
    Sesion de captura organizada.

    Genera una carpeta por sesion con screenshots, dumps XML
    y un log JSON con metadata de cada captura.
    """

    def __init__(self, adb=None, base_dir=".", session_name=None):
        """
        Args:
            adb: Instancia de ADB.
            base_dir: Directorio base del proyecto.
            session_name: Nombre de la sesion (auto-genera si no se da).
        """
        self.adb = adb or ADB()
        self.parser = UIParser()
        self.base_dir = Path(base_dir)

        # Crear nombre de sesion con timestamp
        if session_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_name = f"session_{timestamp}"

        self.session_name = session_name

        # Directorios
        self.screenshots_dir = self.base_dir / "screenshots" / session_name
        self.dumps_dir = self.base_dir / "dumps" / session_name

        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.dumps_dir.mkdir(parents=True, exist_ok=True)

        # Log de capturas
        self.captures_log = []
        self._capture_count = 0

        logger.info(f"Sesion de captura: {session_name}")
        logger.info(f"  Screenshots: {self.screenshots_dir}")
        logger.info(f"  Dumps:       {self.dumps_dir}")

    # ─── Captura completa ─────────────────────────────────────────────

    def capture(self, label=None, screenshot=True, dump=True):
        """
        Realiza una captura completa (screenshot + UI dump).

        Args:
            label: Etiqueta descriptiva (ej: "home", "categoria_vivo").
            screenshot: Si tomar captura de pantalla.
            dump: Si hacer UI dump.

        Returns:
            Dict con rutas y metadata de la captura.
        """
        self._capture_count += 1
        timestamp = datetime.now().strftime("%H%M%S")

        # Generar nombre base
        if label:
            safe_label = label.replace(" ", "_").lower()
            base_name = f"{self._capture_count:03d}_{safe_label}"
        else:
            base_name = f"{self._capture_count:03d}_{timestamp}"

        result = {
            "index": self._capture_count,
            "label": label or base_name,
            "timestamp": datetime.now().isoformat(),
            "screenshot_path": None,
            "dump_path": None,
            "texts": [],
            "channel": None,
        }

        # Screenshot
        if screenshot:
            screenshot_path = self.screenshots_dir / f"{base_name}.png"
            try:
                self.adb.screenshot(str(screenshot_path))
                result["screenshot_path"] = str(screenshot_path)
                logger.info(f"Screenshot: {screenshot_path.name}")
            except Exception as e:
                logger.error(f"Error en screenshot: {e}")

        # UI Dump
        if dump:
            dump_path = self.dumps_dir / f"{base_name}.xml"
            try:
                self.adb.dump_ui("/sdcard/ui.xml")
                self.adb.pull_file("/sdcard/ui.xml", str(dump_path))
                result["dump_path"] = str(dump_path)

                # Parsear para extraer info
                self.parser.parse_file(str(dump_path))
                result["texts"] = self.parser.get_all_texts()
                result["channel"] = self.parser.get_live_channel_name()
                result["element_count"] = len(self.parser.elements)
                result["clickable_count"] = len(self.parser.find_clickable())

                logger.info(
                    f"UI Dump: {dump_path.name} "
                    f"({len(self.parser.elements)} elementos)"
                )
            except Exception as e:
                logger.error(f"Error en UI dump: {e}")

        # Agregar al log
        self.captures_log.append(result)

        return result

    # ─── Captura solo screenshot ──────────────────────────────────────

    def screenshot(self, label=None):
        """Toma solo un screenshot (sin dump XML)."""
        return self.capture(label=label, screenshot=True, dump=False)

    # ─── Captura solo dump ────────────────────────────────────────────

    def dump(self, label=None):
        """Hace solo un UI dump (sin screenshot)."""
        return self.capture(label=label, screenshot=False, dump=True)

    # ─── Captura multiple (recorrer pantallas) ────────────────────────

    def capture_all_categories(self, navigator, wait=3.0):
        """
        Captura screenshot + dump de cada categoria de la app.

        Args:
            navigator: Instancia de Navigator.
            wait: Segundos a esperar tras entrar a cada categoria.

        Returns:
            Dict {categoria: resultado_captura}
        """
        results = {}

        # Capturar home primero
        self.capture(label="home")

        # Obtener categorias
        categories = navigator.get_categories()

        for name, elem in categories.items():
            logger.info(f"\nCapturando categoria: {name}")

            # Entrar a la categoria
            navigator.tap_element(elem, wait=wait)

            # Capturar
            result = self.capture(label=f"cat_{name}")
            results[name] = result

            # Volver
            navigator.back()
            time.sleep(1.5)

        # Captura final (verificar que volvimos)
        self.capture(label="home_final")

        logger.info(f"\nCapturas completadas: {len(results)} categorias")
        return results

    def capture_channel_list(self, navigator, num_channels=10, wait=2.0):
        """
        Captura informacion de multiples canales en vivo.

        Navega por los canales usando dpad y captura cada uno.

        Args:
            navigator: Instancia de Navigator.
            num_channels: Cantidad de canales a recorrer.
            wait: Espera entre canales.

        Returns:
            Lista de dicts con info de cada canal.
        """
        channels = []

        for i in range(num_channels):
            # Capturar estado actual
            result = self.capture(label=f"channel_{i+1:02d}")

            channel_info = {
                "index": i + 1,
                "name": result.get("channel", "Desconocido"),
                "capture": result,
            }
            channels.append(channel_info)

            logger.info(f"Canal {i+1}: {channel_info['name']}")

            # Siguiente canal
            navigator.change_channel_down(wait=wait)

        return channels

    # ─── Exportar resultados ──────────────────────────────────────────

    def save_log(self):
        """
        Guarda el log completo de la sesion en JSON.

        Returns:
            Ruta al archivo JSON generado.
        """
        log_path = self.base_dir / "dumps" / self.session_name / "session_log.json"

        log_data = {
            "session": self.session_name,
            "started": self.captures_log[0]["timestamp"] if self.captures_log else None,
            "total_captures": len(self.captures_log),
            "captures": self.captures_log,
        }

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Log de sesion guardado: {log_path}")
        return str(log_path)

    def export_texts(self):
        """
        Exporta todos los textos encontrados en un archivo de resumen.

        Returns:
            Ruta al archivo de resumen.
        """
        report_path = (
            self.base_dir / "dumps" / self.session_name / "texts_report.txt"
        )

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"REPORTE DE TEXTOS - {self.session_name}\n")
            f.write(f"{'='*60}\n\n")

            for cap in self.captures_log:
                f.write(f"--- {cap['label']} ---\n")
                f.write(f"    Timestamp: {cap['timestamp']}\n")
                if cap.get("channel"):
                    f.write(f"    Canal: {cap['channel']}\n")
                if cap.get("texts"):
                    f.write(f"    Textos ({len(cap['texts'])}):\n")
                    for text in cap["texts"]:
                        f.write(f"      - {text}\n")
                f.write("\n")

        logger.info(f"Reporte de textos: {report_path}")
        return str(report_path)

    # ─── Utilidades ───────────────────────────────────────────────────

    def get_latest_parser(self):
        """Retorna el parser con el ultimo dump cargado."""
        return self.parser

    def get_summary(self):
        """Retorna un resumen de la sesion."""
        return {
            "session": self.session_name,
            "total_captures": len(self.captures_log),
            "screenshots_dir": str(self.screenshots_dir),
            "dumps_dir": str(self.dumps_dir),
            "labels": [c["label"] for c in self.captures_log],
        }

    def __repr__(self):
        return (
            f"CaptureSession('{self.session_name}', "
            f"captures={len(self.captures_log)})"
        )
