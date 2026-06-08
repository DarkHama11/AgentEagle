import importlib
import pkgutil
import logging
from typing import Dict, Type, List, Any
from agents.base_agent import BaseAgent

logger = logging.getLogger("AgentEagle.Registry")


class AgentRegistry:
    """
    Sistema de registro y descubrimiento automático de agentes.
    Permite sobrescribir instancias para inyección de dependencias.
    """

    def __init__(self, package_names: List[str]):
        self.package_names = package_names
        self._agent_classes: Dict[str, Type[BaseAgent]] = {}
        self._agent_instances: Dict[str, BaseAgent] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def discover_agents(self) -> None:
        """Escanea paquetes y registra clases de agentes automáticamente."""
        logger.info(f"Iniciando descubrimiento de agentes en: {self.package_names}")

        for package_name in self.package_names:
            try:
                package = importlib.import_module(package_name)
            except ImportError as e:
                logger.warning(f"No se pudo importar el paquete '{package_name}': {e}")
                continue

            for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
                full_module_name = f"{package_name}.{module_name}"
                try:
                    module = importlib.import_module(full_module_name)

                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)

                        if (isinstance(attr, type) and
                                issubclass(attr, BaseAgent) and
                                attr is not BaseAgent):
                            self._register_class(attr)

                except Exception as e:
                    logger.error(f"Error al procesar el módulo '{full_module_name}': {e}")

        logger.info(f"Descubrimiento completado. Total de agentes registrados: {len(self._agent_classes)}")

    def _register_class(self, agent_class: Type[BaseAgent]) -> None:
        """Registra una clase de agente. Permite sobrescribir si ya existe."""
        agent_name = agent_class.name

        if agent_name in self._agent_classes:
            logger.warning(f"Agente '{agent_name}' ya registrado. Sobrescribiendo con {agent_class.__name__}")

        self._agent_classes[agent_name] = agent_class
        self._metadata[agent_name] = {
            "name": agent_class.name,
            "description": agent_class.description,
            "capabilities": agent_class.capabilities,
            "class_name": agent_class.__name__
        }
        logger.debug(f"Agente registrado: '{agent_name}' ({agent_class.__name__})")

    def register_agent(self, agent_class: Type[BaseAgent]) -> None:
        """Método público para registrar manualmente un agente."""
        self._register_class(agent_class)

    def get_agent(self, agent_name: str) -> BaseAgent:
        """
        Obtiene una instancia del agente.
        Si existe una instancia configurada, la retorna.
        Si no, crea una nueva instancia.
        """
        if agent_name not in self._agent_classes:
            raise KeyError(f"Agente '{agent_name}' no encontrado. Disponibles: {list(self._agent_classes.keys())}")

        # Si ya hay una instancia configurada (inyectada), retornarla
        if agent_name in self._agent_instances:
            logger.debug(f"Retornando instancia configurada de '{agent_name}'")
            return self._agent_instances[agent_name]

        # Si no, crear una nueva instancia
        logger.debug(f"Creando nueva instancia de '{agent_name}'")
        self._agent_instances[agent_name] = self._agent_classes[agent_name]()
        return self._agent_instances[agent_name]

    def set_agent_instance(self, agent_name: str, instance: BaseAgent) -> None:
        """
        Permite establecer una instancia configurada manualmente.
        Útil para inyección de dependencias.
        """
        if agent_name not in self._agent_classes:
            raise KeyError(f"Agente '{agent_name}' no está registrado. Regístralo primero.")

        self._agent_instances[agent_name] = instance
        logger.info(f"Instancia configurada para '{agent_name}'")

    def list_agents(self) -> List[Dict[str, Any]]:
        """Retorna metadatos de todos los agentes registrados."""
        return list(self._metadata.values())