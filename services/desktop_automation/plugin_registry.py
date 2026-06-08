from typing import Dict, Type
from .base_plugin import BaseAutomationPlugin

class PluginRegistry:
    _plugins: Dict[str, Type[BaseAutomationPlugin]] = {}

    @classmethod
    def register(cls, plugin_class: Type[BaseAutomationPlugin]):
        instance = plugin_class()
        cls._plugins[instance.action_type] = plugin_class
        return plugin_class

    @classmethod
    def get_plugin(cls, action_type: str) -> BaseAutomationPlugin:
        if action_type not in cls._plugins:
            raise ValueError(f"Plugin no registrado para: {action_type}")
        return cls._plugins[action_type]()
