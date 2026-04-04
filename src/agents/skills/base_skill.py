# src/agents/skills/base_skill.py
"""AgentEagle++ - Clase base para todas las skills."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging
import json
import time

logger = logging.getLogger(__name__)


class SkillExecutionError(Exception):
    """Error durante la ejecución de un skill."""
    pass


class BaseSkill(ABC):
    """
    Clase base para skills en AgentEagle++.

    Diseño para entorno local con seguridad:
    • Sandboxing por whitelist de comandos/operaciones
    • Timeouts configurables
    • Logging detallado de ejecución
    • Input/output JSON para integración con LLM
    """

    # === Metadata del skill (para discovery y documentación) ===
    name: str = "base_skill"
    description: str = "Descripción base del skill"
    version: str = "1.0.0"
    category: str = "general"  # aws, security, file, network, etc.

    # === Parámetros esperados (para validación de input) ===
    parameters: Dict[str, Dict[str, Any]] = {}

    # === Permisos requeridos (para sandboxing) ===
    required_permissions: List[str] = []

    # === Configuración por defecto ===
    default_timeout: int = 30  # segundos
    default_enabled: bool = True

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.timeout = self.config.get("timeout", self.default_timeout)
        self.enabled = self.config.get("enabled", self.default_enabled)
        self._initialized = False
        logger.info(f"🔧 Skill '{self.name}' v{self.version} inicializada")

    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Valida que el input cumple con los parámetros esperados."""
        for param_name, param_spec in self.parameters.items():
            required = param_spec.get("required", False)
            param_type = param_spec.get("type", str)

            # Verificar parámetros requeridos
            if required and param_name not in input_data:
                logger.warning(f"❌ Skill '{self.name}': parámetro requerido '{param_name}' faltante")
                return False

            # Verificar tipo de dato
            if param_name in input_data:
                value = input_data[param_name]
                if param_type and not isinstance(value, param_type):
                    logger.warning(f"❌ Skill '{self.name}': tipo incorrecto para '{param_name}'")
                    return False

            # Verificar enum si está definido
            if param_name in input_data and "enum" in param_spec:
                if value not in param_spec["enum"]:
                    logger.warning(f"❌ Skill '{self.name}': valor '{value}' no está en {param_spec['enum']}")
                    return False

        return True

    def validate_permissions(self, user_permissions: List[str]) -> bool:
        """Verifica que el usuario tiene los permisos necesarios."""
        for perm in self.required_permissions:
            if perm not in user_permissions:
                logger.warning(f"⚠️ Skill '{self.name}': usuario no tiene permiso '{perm}'")
                return False
        return True

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta el skill con los datos de entrada.

        Args:
            input_data: Diccionario con parámetros del skill

        Returns:
            Dict con resultado de la ejecución:
            {
                "success": bool,
                "output": Any,  # Resultado del skill
                "error": Optional[str],  # Mensaje de error si falló
                "metadata": {  # Info adicional
                    "execution_time_ms": int,
                    "skill_name": str,
                    "skill_version": str,
                }
            }
        """
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Retorna el esquema del skill para que el LLM sepa cómo usarlo."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category,
            "parameters": {
                name: {
                    "type": spec.get("type", str).__name__,
                    "description": spec.get("description", ""),
                    "required": spec.get("required", False),
                    "enum": spec.get("enum", None),
                    "default": spec.get("default", None)
                }
                for name, spec in self.parameters.items()
            },
            "returns": {
                "type": "object",
                "description": "Resultado de la ejecución del skill"
            },
            "permissions": self.required_permissions,
            "timeout": self.timeout
        }

    def format_for_llm(self) -> str:
        """Formato legible para inyectar en el prompt del LLM."""
        schema = self.get_schema()
        params_str = ", ".join([
            f"{name}{'*' if spec['required'] else ''}: {spec['type']}"
            for name, spec in schema["parameters"].items()
        ])
        return f"{self.name}({params_str}) → {self.description}"

    def format_for_llm_detailed(self) -> str:
        """Formato detallado para documentación del skill."""
        schema = self.get_schema()
        lines = [
            f"🔧 **{self.name}** v{self.version}",
            f"📝 {self.description}",
            f"📂 Categoría: {self.category}",
            f"⏱️ Timeout: {self.timeout}s",
            "",
            "📋 **Parámetros**:"
        ]

        for name, spec in schema["parameters"].items():
            required = "*" if spec["required"] else ""
            param_type = spec["type"]
            desc = spec.get("description", "")
            default = spec.get("default")
            enum = spec.get("enum")

            line = f"• `{name}{required}` ({param_type}): {desc}"
            if default is not None:
                line += f" [default: {default}]"
            if enum:
                line += f" [opciones: {', '.join(enum)}]"
            lines.append(line)

        if self.required_permissions:
            lines.append("")
            lines.append(f"🔐 **Permisos requeridos**: {', '.join(self.required_permissions)}")

        return "\n".join(lines)