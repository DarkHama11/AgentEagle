# src/agents/skills/skill_registry.py
"""AgentEagle++ - Registry para descubrir y cargar skills."""
from typing import Dict, Type, Optional, List, Any
import logging
import importlib
import pkgutil
from pathlib import Path

from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Registry centralizado para skills de AgentEagle++.

    • Auto-discovery de skills en el paquete skills/
    • Carga dinámica con validación
    • Schema export para LLM prompting
    • Gestión de configuración por skill
    """

    def __init__(self, skills_module: str = "src.agents.skills", config: Optional[Dict[str, Any]] = None):
        self.skills_module = skills_module
        self.config = config or {}
        self._skills: Dict[str, BaseSkill] = {}
        self._skill_classes: Dict[str, Type[BaseSkill]] = {}
        self._load_available_skills()

    def _load_available_skills(self):
        """Auto-discover skills en el módulo configurado."""
        try:
            module = importlib.import_module(self.skills_module)
            module_path = Path(module.__file__).parent

            for finder, name, is_pkg in pkgutil.iter_modules([str(module_path)]):
                # Ignorar módulos privados y base
                if name.startswith("_") or name in ["base_skill", "skill_registry"]:
                    continue

                try:
                    skill_module = importlib.import_module(f"{self.skills_module}.{name}")

                    # Buscar clases que hereden de BaseSkill
                    for attr_name in dir(skill_module):
                        attr = getattr(skill_module, attr_name)
                        if (
                                isinstance(attr, type)
                                and issubclass(attr, BaseSkill)
                                and attr != BaseSkill
                                and hasattr(attr, "name")
                        ):
                            self._skill_classes[attr.name] = attr
                            logger.info(f"✅ Skill registrada: {attr.name} ({attr.__name__})")

                except ImportError as e:
                    logger.warning(f"⚠️ No se pudo cargar skill module '{name}': {e}")

        except Exception as e:
            logger.error(f"❌ Error cargando skills: {e}")

    def register_skill(self, skill_class: Type[BaseSkill], config: Optional[Dict] = None) -> BaseSkill:
        """Registra manualmente una skill con configuración opcional."""
        if not hasattr(skill_class, "name"):
            raise ValueError("Skill class must have 'name' attribute")

        skill_config = self.config.get(skill_class.name, {})
        if config:
            skill_config.update(config)

        skill_instance = skill_class(config=skill_config)

        # Verificar si está habilitada
        if not skill_instance.enabled:
            logger.info(f"⚠️ Skill '{skill_instance.name}' está deshabilitada por configuración")
            return skill_instance

        self._skills[skill_instance.name] = skill_instance
        self._skill_classes[skill_instance.name] = skill_class
        logger.info(f"✅ Skill registrada manualmente: {skill_instance.name}")
        return skill_instance

    def get_skill(self, name: str, config: Optional[Dict] = None) -> Optional[BaseSkill]:
        """Obtiene una instancia de skill por nombre, cargándola si es necesario."""
        # Verificar caché primero
        if name in self._skills:
            skill = self._skills[name]
            if skill.enabled:
                return skill
            else:
                logger.warning(f"⚠️ Skill '{name}' está deshabilitada")
                return None

        if name not in self._skill_classes:
            logger.warning(f"⚠️ Skill '{name}' no encontrada en registry")
            return None

        # Instanciar skill con configuración
        skill_config = self.config.get(name, {})
        if config:
            skill_config.update(config)

        skill_class = self._skill_classes[name]
        skill_instance = skill_class(config=skill_config)

        if not skill_instance.enabled:
            logger.info(f"⚠️ Skill '{name}' está deshabilitada por configuración")
            return None

        self._skills[name] = skill_instance
        return skill_instance

    def list_skills(self) -> List[Dict[str, Any]]:
        """Lista todas las skills disponibles con sus schemas."""
        return [
            {
                "name": name,
                "description": skill_class.description,
                "version": skill_class.version,
                "category": skill_class.category,
                "schema": skill_class().get_schema(),
                "llm_format": skill_class().format_for_llm(),
                "enabled": self.config.get(name, {}).get("enabled", True)
            }
            for name, skill_class in self._skill_classes.items()
        ]

    def get_llm_tools_prompt(self) -> str:
        """Genera prompt para que el LLM sepa qué skills puede usar."""
        enabled_skills = [
            skill_class for name, skill_class in self._skill_classes.items()
            if self.config.get(name, {}).get("enabled", True)
        ]

        if not enabled_skills:
            return "🔧 No hay skills disponibles en este momento."

        lines = ["🔧 **SKILLS DISPONIBLES** (puedes usar estos comandos):", ""]
        for skill_class in enabled_skills:
            lines.append(f"• {skill_class().format_for_llm()}")

        lines.append("")
        lines.append("**Para usar un skill, responde con formato JSON:**")
        lines.append("```json")
        lines.append('{"skill": "nombre_skill", "params": {"param1": "value1", ...}}')
        lines.append("```")

        return "\n".join(lines)

    def get_skills_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Obtiene skills filtradas por categoría."""
        return [
            skill for skill in self.list_skills()
            if skill.get("category") == category and skill.get("enabled")
        ]