import os
import yaml
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("AgentEagle.PrinterManager")


class PrinterManager:
    """
    Gestiona grupos de impresoras y sus configuraciones.
    """

    _instance: Optional['PrinterManager'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        if self._initialized:
            return

        self.groups = {}
        self.default_group = "general"
        self.print_mode = "windows"
        self._load_config(config_path)
        self._initialized = True
        logger.info(f"PrinterManager inicializado con {len(self.groups)} grupos")

    def _load_config(self, config_path: Optional[str] = None) -> None:
        """Carga la configuración de impresoras."""
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "printers.yaml")

        if not os.path.exists(config_path):
            logger.warning(f"Config de impresoras no encontrada: {config_path}")
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}

            self.groups = config.get('printers', {})
            self.default_group = config.get('default_group', 'general')
            self.print_mode = config.get('print_mode', 'windows')
            logger.info(f"Configuración de impresoras cargada")
        except Exception as e:
            logger.error(f"Error cargando config de impresoras: {e}")

    def get_printer_for_group(self, group_name: str) -> Optional[str]:
        """Obtiene la impresora por defecto de un grupo."""
        group = self.groups.get(group_name, {})
        printer = group.get('default_printer')

        if not printer:
            # Fallback al grupo por defecto
            default = self.groups.get(self.default_group, {})
            printer = default.get('default_printer')

        return printer

    def get_group_settings(self, group_name: str) -> Dict[str, Any]:
        """Obtiene la configuración de un grupo."""
        group = self.groups.get(group_name, {})
        return group.get('settings', {})

    def get_all_groups(self) -> List[str]:
        """Lista todos los grupos disponibles."""
        return list(self.groups.keys())

    def get_print_mode(self) -> str:
        """Obtiene el modo de impresión actual."""
        return self.print_mode

    def group_exists(self, group_name: str) -> bool:
        """Verifica si un grupo existe."""
        return group_name in self.groups

    @classmethod
    def reset_instance(cls) -> None:
        """Reinicia el singleton."""
        cls._instance = None