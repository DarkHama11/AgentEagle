import logging
import time
from pywinauto import Application
from ..retry_strategy import retry_action

logger = logging.getLogger(__name__)


class PywinautoBackend:
    def __init__(self):
        self.app = None

    def start(self, exe_path: str):
        logger.info(f"[Backend] Iniciando: {exe_path}")
        self.app = Application(backend="uia").start(exe_path)
        return self.app

    @retry_action(max_retries=3, delay=2.0)
    def click_button(self, window_title_pattern: str, button_name_or_id: str):
        logger.info(f"[Backend] Buscando elemento: '{button_name_or_id}' en ventana '{window_title_pattern}'")

        window = self.app.window(title_re=window_title_pattern)
        window.wait('ready', timeout=15)

        # INTENTO 1: Por auto_id y tipo Button
        try:
            logger.info(f"[Backend] Intento 1: auto_id='{button_name_or_id}', control_type='Button'")
            ctrl = window.child_window(auto_id=button_name_or_id, control_type="Button")
            ctrl.wait('ready', timeout=5)
            ctrl.click_input()
            logger.info("[Backend] ✅ Éxito (Intento 1)")
            return
        except Exception as e:
            logger.info(f"[Backend] ⚠️ Falló Intento 1 ({type(e).__name__}). Pasando al siguiente...")

        # INTENTO 2: Por title (texto visible) y tipo Button
        try:
            logger.info(f"[Backend] Intento 2: title='{button_name_or_id}', control_type='Button'")
            ctrl = window.child_window(title=button_name_or_id, control_type="Button")
            ctrl.wait('ready', timeout=5)
            ctrl.click_input()
            logger.info("[Backend] ✅ Éxito (Intento 2)")
            return
        except Exception as e:
            logger.info(f"[Backend] ⚠️ Falló Intento 2 ({type(e).__name__}). Pasando al siguiente...")

        # INTENTO 3: Por title y CUALQUIER tipo de control (a veces el texto es un 'Text' hijo de un 'Button')
        try:
            logger.info(f"[Backend] Intento 3: title='{button_name_or_id}' (cualquier control)")
            ctrl = window.child_window(title=button_name_or_id)
            ctrl.wait('ready', timeout=5)
            ctrl.click_input()
            logger.info("[Backend] ✅ Éxito (Intento 3)")
            return
        except Exception as e:
            logger.info(f"[Backend] ⚠️ Falló Intento 3 ({type(e).__name__}).")

        # Si llegamos aquí, nada funcionó
        raise Exception(f"No se pudo encontrar o interactuar con '{button_name_or_id}' con ningún método.")

    @retry_action(max_retries=3, delay=2.0)
    def type_text(self, window_title_pattern: str, edit_name_or_id: str, text: str):
        logger.info(f"[Backend] Escribiendo '{text}' en: '{edit_name_or_id}'")
        window = self.app.window(title_re=window_title_pattern)
        window.wait('ready', timeout=15)

        try:
            ctrl = window.child_window(auto_id=edit_name_or_id, control_type="Edit")
            ctrl.wait('ready', timeout=5)
            ctrl.set_text(text)
        except Exception:
            logger.info(f"[Backend] ⚠️ No encontrado por auto_id. Intentando por title...")
            ctrl = window.child_window(title=edit_name_or_id, control_type="Edit")
            ctrl.wait('ready', timeout=5)
            ctrl.set_text(text)

    def kill(self):
        if self.app and self.app.process:
            logger.info(f"[Backend] Terminando proceso: {self.app.process}")
            self.app.kill()