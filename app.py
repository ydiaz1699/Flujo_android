"""
app.py - Gestion de la aplicacion MGAndroid.

Abstrae abrir, cerrar, verificar estado y esperar
a que la app este lista para interactuar.
"""

import time
import logging

from device import Device

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Error de gestion de la app."""
    pass


class App:
    """
    Gestor de la aplicacion MGAndroid.

    Maneja el ciclo de vida: abrir, cerrar, reiniciar,
    verificar que este lista.
    """

    PACKAGE = "com.android.mgandroid"

    # IDs que indican que estamos en la pantalla principal
    HOME_INDICATORS = [
        "com.android.mgandroid:id/iv_logo",
        "com.android.mgandroid:id/vod_category_name",
        "com.android.mgandroid:id/ll_video",
    ]

    def __init__(self, device: Device):
        """
        Args:
            device: Instancia de Device.
        """
        self.device = device

    def open(self, wait=5.0):
        """
        Abre la aplicacion MGAndroid.

        Args:
            wait: Segundos a esperar para que cargue.
        """
        logger.info(f"Abriendo {self.PACKAGE}...")
        self.device.start_app(self.PACKAGE)
        time.sleep(wait)
        logger.info("App abierta.")

    def close(self):
        """Cierra la aplicacion."""
        logger.info(f"Cerrando {self.PACKAGE}...")
        self.device.stop_app(self.PACKAGE)
        time.sleep(1)

    def restart(self, wait=5.0):
        """Cierra y vuelve a abrir la app."""
        self.close()
        time.sleep(1)
        self.open(wait=wait)

    def is_running(self):
        """Verifica si la app esta en primer plano."""
        return self.device.is_app_foreground(self.PACKAGE)


    def is_on_home(self, refresh=True):
        """
        Verifica si estamos en la pantalla principal.

        Busca indicadores conocidos (logo, categorias, video).
        """
        if refresh:
            self.device.refresh()

        for indicator_id in self.HOME_INDICATORS:
            node = self.device.tree.find_id(indicator_id).first()
            if node:
                return True
        return False

    def wait_ready(self, timeout=20, interval=2):
        """
        Espera hasta que la app este cargada y lista.

        Verifica que los elementos principales sean visibles.

        Args:
            timeout: Segundos maximos de espera.
            interval: Intervalo entre verificaciones.

        Returns:
            True si la app cargo correctamente.

        Raises:
            AppError: Si la app no carga en el tiempo limite.
        """
        logger.info("Esperando a que la app este lista...")
        start = time.time()

        while time.time() - start < timeout:
            self.device.refresh()

            # Verificar que hay categorias visibles
            categories = self.device.tree.get_categories()
            if categories:
                logger.info(
                    f"App lista. Categorias: {list(categories.keys())}"
                )
                return True

            time.sleep(interval)

        raise AppError(f"La app no cargo en {timeout}s")

    def ensure_home(self):
        """
        Asegura que estamos en la pantalla principal.

        Si no estamos en home, intenta volver (back repetido o reabrir).
        """
        if self.is_on_home():
            return

        # Intentar back (hasta 5 veces)
        for _ in range(5):
            self.device.back()
            time.sleep(1)
            if self.is_on_home():
                return

        # Si no funciona, reabrir
        logger.warning("No se pudo volver a home. Reiniciando app...")
        self.restart()
        self.wait_ready()

    def get_version(self):
        """Obtiene la version de la app."""
        self.device.refresh()
        return self.device.tree.get_version()

    def get_current_channel(self):
        """Obtiene el canal en vivo actual."""
        self.device.refresh()
        return self.device.tree.get_live_channel()

    def __repr__(self):
        return f"App({self.PACKAGE})"
