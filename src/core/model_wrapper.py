# -*- coding: utf-8 -*-
"""AgentEagle - Wrapper para usar modelos a traves de Ollama."""

import logging
from typing import Optional, Dict, Any
from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class ModelWrapper:
    """Wrapper con soporte para multiples modelos."""

    def __init__(self, model_key: str = "seguridad_experto"):
        from .config import Config
        self.model_key = model_key
        self.config = Config.MODELS.get(model_key, Config.MODELS["general"])
        self.cliente: Optional[OllamaClient] = None
        self.model_name = self.config.get("ollama_model", "llama3.2:1b")
        self.default_options = {
            "temperature": self.config.get("temperature", 0.2),
            "num_predict": self.config.get("max_tokens", 384),
            "num_ctx": self.config.get("context_length", 2048),
        }
        logger.info(f"📦 ModelWrapper: '{self.model_name}' (key: {model_key})")

    def load(self) -> "ModelWrapper":
        """Inicializar cliente Ollama."""
        from .config import Config
        self.cliente = OllamaClient(base_url=Config.OLLAMA_BASE_URL)
        logger.info(f"✅ Cliente Ollama conectado: {Config.OLLAMA_BASE_URL}")
        return self

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Any:
        """Generar respuesta del modelo."""
        if not self.cliente:
            self.load()
        merged_options = {**self.default_options, **(options or {})}
        return self.cliente.generate(
            model=self.model_name,
            prompt=prompt,
            system=system,
            options=merged_options,
            stream=stream
        )

    def chat(
        self,
        messages: list,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Any:
        """Enviar conversacion al modelo."""
        if not self.cliente:
            self.load()
        merged_options = {**self.default_options, **(options or {})}
        return self.cliente.chat(
            model=self.model_name,
            messages=messages,
            options=merged_options,
            stream=stream
        )

    def get_model_info(self) -> Dict[str, Any]:
        """Retornar informacion del modelo configurado."""
        return {
            "key": self.model_key,
            "name": self.model_name,
            "config": self.config,
            "default_options": self.default_options,
        }