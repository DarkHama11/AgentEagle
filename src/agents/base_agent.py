# src/agents/base_agent.py
"""AgentEagle++ - Clase base para agentes con fallback conservador."""
from abc import ABC, abstractmethod
import logging
import re
from typing import Dict, Any, Optional, TypeVar, Generic
from datetime import datetime

logger = logging.getLogger(__name__)
ModelType = TypeVar("ModelType")


class BaseAgent(ABC, Generic[ModelType]):
    """Clase base abstracta para agentes especializados AgentEagle++."""

    GREETINGS = ["hola", "hi", "hello", "hey", "buenos días", "buenas tardes", "buenas noches", "saludos", "qué tal",
                 "cómo estás"]
    GOODBYES = ["adiós", "chau", "bye", "hasta luego", "nos vemos", "hasta pronto"]
    THANKS = ["gracias", "thank", "muy bien", "excelente", "perfecto", "genial"]

    def __init__(self, name: str, model_key: str = "3b"):
        self.name: str = name
        self.model_key: str = model_key
        self._model: Optional[ModelType] = None
        self._is_ready: bool = False
        logger.info(f"🤖 Agente '{name}' inicializado (model_key: {model_key})")

    @property
    def model(self) -> ModelType:
        if self._model is None:
            raise RuntimeError(f"Modelo no asignado en agente '{self.name}'. Usa set_model() primero.")
        return self._model

    @model.setter
    def model(self, value: ModelType):
        self._model = value
        self._is_ready = value is not None

    @abstractmethod
    async def process(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    def set_model(self, model_instance: ModelType) -> "BaseAgent":
        self.model = model_instance
        return self

    def is_ready(self) -> bool:
        return self._is_ready and self._model is not None

    def _detect_intent(self, user_input: str) -> str:
        """Detecta la intención del usuario."""
        text = user_input.lower().strip()
        text_clean = re.sub(r'[^\w\sáéíóúñü]', ' ', text)

        if any(k in text_clean for k in ["fecha", "día", "dia", "hora", "qué día", "today", "date"]):
            return "date"
        if any(g in text_clean for g in self.GREETINGS):
            return "greeting"
        if any(g in text_clean for g in self.GOODBYES):
            return "goodbye"
        if any(k in text_clean for k in self.THANKS):
            return "thanks"
        return "question"

    def _should_use_fallback(self, response: str, user_input: str, intent: str) -> bool:
        """Fallback SOLO si respuesta verdaderamente inválida."""
        if not response or not response.strip():
            logger.warning(f"⚠️ Fallback: respuesta vacía")
            return True

        if len(response.strip()) < 10:
            logger.warning(f"⚠️ Fallback: respuesta muy corta ({len(response.strip())} chars)")
            return True

        logger.debug(f"✅ Usando respuesta del modelo ({len(response.strip())} chars)")
        return False

    def _build_response(self, response_text: str, success: bool = True, **metadata) -> Dict[str, Any]:
        base = {
            "agent": self.name,
            "model_key": self.model_key,
            "response": response_text.strip() if response_text else "",
            "success": success,
            "timestamp": datetime.now().isoformat()
        }
        base.update(metadata)
        return base

    async def health_check(self) -> Dict[str, Any]:
        health = {"agent": self.name, "model_key": self.model_key, "is_ready": self.is_ready(),
                  "model_connected": False}
        if self._model and hasattr(self._model, "get_model_info"):
            try:
                info = self._model.get_model_info()
                health["model_connected"] = info.get("client_connected", False)
            except Exception:
                pass
        return health