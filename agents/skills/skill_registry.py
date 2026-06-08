# -*- coding: utf-8 -*-
# src/agents/skills/skill_registry.py
"""AgentEagle - Registry para descubrir y cargar skills."""

import logging
import importlib
import pkgutil
from typing import Dict, Type, Optional, List, Any
from pathlib import Path

from .base_skill import BaseSkill, SkillExecutionError

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Registry centralizado para skills de AgentEagle.

    Descubre, registra y gestiona skills de forma dinamica.
    """

    _instance: Optional["SkillRegistry"] = None
    _skills: Dict[str, Type[BaseSkill]] = {}

    def __new__(cls):
        """Singleton pattern para registry global."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Inicializar registry (solo una vez por singleton)."""
        if self._initialized:
            return
        self._initialized = True
        self._skills = {}
        logger.info("🔧 SkillRegistry inicializado")

    @classmethod
    def reset(cls):
        """Resetear registry (util para testing)."""
        cls._instance = None

    def register_skill(self, skill_class: Type[BaseSkill], name: Optional[str] = None) -> str:
        """
        Registrar una skill en el registry.

        Args:
            skill_class: Clase de la skill que hereda de BaseSkill
            name: Nombre opcional (por defecto usa skill_class.name)

        Returns:
            str: Nombre registrado de la skill
        """
        if not issubclass(skill_class, BaseSkill):
            raise TypeError(f"{skill_class.__name__} debe heredar de BaseSkill")

        skill_name = name or getattr(skill_class, "name", skill_class.__name__.lower())

        if skill_name in self._skills:
            logger.warning(f"⚠️ Skill '{skill_name}' ya registrada, sobrescribiendo")

        self._skills[skill_name] = skill_class
        logger.info(f"✅ Skill registrada: {skill_name} ({skill_class.__name__})")

        return skill_name

    def register_all(self, package_path: Optional[str] = None) -> List[str]:
        """
        Descubrir y registrar automaticamente todas las skills en un package.

        Args:
            package_path: Ruta del package a escanear (por defecto: skills/)

        Returns:
            List[str]: Lista de nombres de skills registradas
        """
        if package_path is None:
            package_path = "src.agents.skills"

        registered = []

        try:
            package = importlib.import_module(package_path)
            package_dir = Path(package.__file__).parent

            # Escanear archivos .py en el directorio de skills
            for item in package_dir.iterdir():
                if item.name.startswith("_") or not item.name.endswith(".py"):
                    continue

                module_name = item.stem
                if module_name in ("base_skill", "skill_registry", "__init__"):
                    continue

                try:
                    # Importar modulo dinamicamente
                    module = importlib.import_module(f"{package_path}.{module_name}")

                    # Buscar clases que hereden de BaseSkill
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                                isinstance(attr, type)
                                and issubclass(attr, BaseSkill)
                                and attr != BaseSkill
                                and hasattr(attr, "name")
                        ):
                            self.register_skill(attr)
                            registered.append(attr.name)

                except ImportError as e:
                    logger.warning(f"⚠️ No se pudo importar {module_name}: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ Error procesando {module_name}: {e}")

        except ImportError as e:
            logger.error(f"❌ No se pudo importar package {package_path}: {e}")

        logger.info(f"🔧 Skills registradas automaticamente: {registered}")
        return registered

    def has_skill(self, name: str) -> bool:
        """Verificar si una skill esta registrada."""
        return name in self._skills

    def get_skill(self, name: str, **kwargs) -> BaseSkill:
        """
        Obtener instancia de una skill registrada.

        Args:
            name: Nombre de la skill
            **kwargs: Argumentos para el constructor de la skill

        Returns:
            BaseSkill: Instancia de la skill inicializada
        """
        if name not in self._skills:
            available = list(self._skills.keys())
            raise ValueError(f"Skill '{name}' no registrada. Disponibles: {available}")

        skill_class = self._skills[name]
        return skill_class(**kwargs)

    def list_skills(self) -> Dict[str, Dict[str, Any]]:
        """
        Listar todas las skills registradas con metadata.

        Returns:
            Dict[str, Dict]: Metadata de cada skill
        """
        result = {}
        for name, skill_class in self._skills.items():
            result[name] = {
                "class": skill_class.__name__,
                "version": getattr(skill_class, "version", "1.0.0"),
                "description": getattr(skill_class, "description", ""),
                "required_permissions": getattr(skill_class, "required_permissions", []),
            }
        return result

    def execute_skill(self, name: str, user_input: str, context: Optional[Dict] = None) -> Any:
        """
        Ejecutar una skill por nombre.

        Args:
            name: Nombre de la skill
            user_input: Input del usuario
            context: Contexto adicional para la ejecucion

        Returns:
            Any: Resultado de la ejecucion de la skill
        """
        if not self.has_skill(name):
            raise ValueError(f"Skill '{name}' no registrada")

        skill = self.get_skill(name)
        return skill.execute(user_input, context=context)

    def unregister_skill(self, name: str) -> bool:
        """
        Eliminar una skill del registry.

        Args:
            name: Nombre de la skill a eliminar

        Returns:
            bool: True si se elimino, False si no existia
        """
        if name in self._skills:
            del self._skills[name]
            logger.info(f"🗑️ Skill '{name}' eliminada del registry")
            return True
        return False

    def clear(self):
        """Eliminar todas las skills del registry."""
        count = len(self._skills)
        self._skills.clear()
        logger.info(f"🗑️ Registry limpiado: {count} skills eliminadas")

    @property
    def skills(self) -> Dict[str, Type[BaseSkill]]:
        """Acceso de solo lectura a las skills registradas."""
        return dict(self._skills)