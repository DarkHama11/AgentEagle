import logging
from typing import Dict, Type
from services.desktop_automation.base_plugin import BaseAutomationPlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registro centralizado de plugins de automatización"""

    _plugins: Dict[str, Type[BaseAutomationPlugin]] = {}

    @classmethod
    def register(cls, plugin_class: Type[BaseAutomationPlugin]) -> Type[BaseAutomationPlugin]:
        """Registra un plugin usando el decorador @PluginRegistry.register"""
        action_type = plugin_class().action_type
        cls._plugins[action_type] = plugin_class
        logger.info(f"🔌 Plugin registrado: {action_type} → {plugin_class.__name__}")
        return plugin_class

    @classmethod
    def get_plugin(cls, action_type: str) -> BaseAutomationPlugin:
        """Obtiene una instancia del plugin para el action_type especificado"""
        if action_type not in cls._plugins:
            available = list(cls._plugins.keys())
            raise ValueError(f"No hay plugin registrado para '{action_type}'. Disponibles: {available}")

        plugin_class = cls._plugins[action_type]
        return plugin_class()

    @classmethod
    def list_plugins(cls) -> Dict[str, Type[BaseAutomationPlugin]]:
        """Lista todos los plugins registrados"""
        return cls._plugins.copy()