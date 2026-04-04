# src/core/model_wrapper.py
"""AgentEagle++ - Wrapper para usar modelos a través de Ollama."""
import logging
from typing import Optional, Dict, Any
from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class ModelWrapper:
    """Wrapper con soporte para múltiples modelos."""

    def __init__(self, model_key: str = "3b"):
        from .config import Config
        self.model_key = model_key
        self.config = Config.MODELS.get(model_key, Config.MODELS["3b"])
        self.cliente: Optional[OllamaClient] = None
        self.model_name = self.config.get("ollama_model", "llama3.2:3b")
        self.default_options = {
            "temperature": self.config.get("temperature", 0.2),
            "num_predict": self.config.get("max_tokens", 384),
            "num_ctx": self.config.get("context_length", 2048),
        }
        logger.info(f"📦 ModelWrapper: '{self.model_name}' (key: {model_key})")

    def load(self) -> "ModelWrapper":
        self.cliente = OllamaClient(model=self.model_name)
        models = self.cliente.list_models()
        if self.model_name in models:
            logger.info(f"✅ Modelo '{self.model_name}' disponible")
        else:
            logger.warning(f"⚠️ Modelo '{self.model_name}' no encontrado. Disponibles: {models}")
        return self

    def generate(self, prompt: str, max_tokens: Optional[int] = None, temperature: Optional[float] = None,
                 model: Optional[str] = None, options: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        if self.cliente is None:
            raise RuntimeError("ModelWrapper no inicializado. Llama a .load() primero.")

        final_options = self.default_options.copy()
        if options:
            final_options.update(options)
        if temperature is not None:
            final_options["temperature"] = temperature
        if max_tokens is not None:
            final_options["num_predict"] = max_tokens
        for key in ["top_p", "stop"]:
            if key in kwargs:
                final_options[key] = kwargs[key]

        target_model = model or self.model_name
        logger.debug(
            f"🔄 Generate: '{target_model}' | temp={final_options.get('temperature')}, tokens={final_options.get('num_predict')}")

        try:
            return self.cliente.generate(prompt=prompt, model=target_model, options=final_options).strip()
        except TypeError as e:
            if "unexpected keyword argument" in str(e):
                logger.debug("⚡ Fallback a formato legacy")
                return self.cliente.generate(prompt, final_options.get("num_predict", 384),
                                             final_options.get("temperature", 0.2)).strip()
            raise
        except Exception as e:
            logger.error(f"❌ Error en generate: {e}")
            return ""

    def get_model_info(self) -> Dict[str, Any]:
        return {"model_key": self.model_key, "model_name": self.model_name, "default_options": self.default_options,
                "client_connected": self.cliente is not None}