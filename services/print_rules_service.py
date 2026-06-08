import os
import yaml
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("AgentEagle.PrintRulesService")


class PrintRulesService:
    """
    Servicio que carga y evalúa reglas de impresión estáticas.
    Actúa como fallback cuando la IA no puede decidir.
    """

    _instance: Optional['PrintRulesService'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        if self._initialized:
            return

        self.rules = {}
        self._load_rules(config_path)
        self._initialized = True
        logger.info(f"PrintRulesService inicializado con {len(self.rules)} reglas")

    def _load_rules(self, config_path: Optional[str] = None) -> None:
        """Carga las reglas desde YAML."""
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "print_rules.yaml")

        if not os.path.exists(config_path):
            logger.warning(f"Archivo de reglas no encontrado: {config_path}")
            self.rules = {}
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            self.rules = config.get('rules', {})
            self.ai_settings = config.get('ai_settings', {})
            logger.info(f"Reglas cargadas desde: {config_path}")
        except Exception as e:
            logger.error(f"Error cargando reglas: {e}")
            self.rules = {}

    def get_rule(self, document_type: str) -> Dict[str, Any]:
        """Obtiene la regla para un tipo de documento."""
        rule = self.rules.get(document_type, self.rules.get('other', {}))
        return rule.copy()

    def get_ai_settings(self) -> Dict[str, Any]:
        """Obtiene la configuración de IA."""
        return self.ai_settings.copy()

    def should_use_ai(self) -> bool:
        """Determina si debe usarse IA para decisiones."""
        return self.ai_settings.get('enabled', True)

    def fallback_to_rules(self) -> bool:
        """Determina si debe usar reglas estáticas como fallback."""
        return self.ai_settings.get('fallback_to_rules', True)

    @classmethod
    def reset_instance(cls) -> None:
        """Reinicia el singleton (solo para testing)."""
        cls._instance = None