# -*- coding: utf-8 -*-
"""AgentEagle Cloud Security Specialist - Configuracion centralizada."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any


class Config:
    """Configuracion centralizada para AgentEagle."""

    # === Rutas del proyecto ===
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    DATA_DIR = PROJECT_ROOT / "data"
    MODELS_DIR = PROJECT_ROOT / "models"
    LOGS_DIR = PROJECT_ROOT / "logs"

    # === Configuracion de Ollama ===
    OLLAMA_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL = "llama3.2"
    MODELS_DISPONIBLES = ["llama3.2", "mistral", "codellama", "phi3", "qwen2.5"]

    # === Configuracion de modelos ===
    DEFAULT_MODEL_KEY = "seguridad_experto"
    MODELS = {
        "seguridad_experto": {
            "ollama_model": "llama3.2:3b",
            "description": "Modelo especializado en seguridad cloud",
            "context_window": 4096,
            "temperature": 0.1,
        },
        "general": {
            "ollama_model": "llama3.2:1b",
            "description": "Modelo ligero para preguntas generales",
            "context_window": 2048,
            "temperature": 0.3,
        },
        "code": {
            "ollama_model": "codellama:7b",
            "description": "Modelo especializado en codigo",
            "context_window": 4096,
            "temperature": 0.1,
        },
    }

    # === Configuracion de agentes ===
    AGENTES_DISPONIBLES = ["seguridad", "oficina", "general"]
    DEFAULT_AGENT = "seguridad"

    # === Configuracion de busqueda web ===
    SEARCH_TIMEOUT = 10
    SEARCH_CACHE_TTL_HOURS = 24
    MAX_SEARCH_RESULTS = 5

    # === Configuracion de API FastAPI ===
    API_HOST = "0.0.0.0"
    API_PORT = 8000
    API_DEBUG = False
    API_TITLE = "AgentEagle API"
    API_VERSION = "2.1.0"

    # === CORS Configuration ===
    CORS_ORIGINS = [
        "http://localhost:8000",
        "http://localhost:8501",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8501",
        "*",
    ]
    CORS_CREDENTIALS = True
    CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_HEADERS = ["*"]

    # === Configuracion de logging ===
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"

    # === Configuracion de seguridad ===
    ENABLE_WEB_SEARCH = True
    ENABLE_SKILLS = True
    SANDBOX_MODE = True

    # === Configuracion de fine-tuning ===
    QLORA_R = 8
    QLORA_ALPHA = 16
    QLORA_DROPOUT = 0.05
    TRAINING_BATCH_SIZE = 1
    TRAINING_EPOCHS = 3
    TRAINING_LR = 2e-4

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Obtener valor de configuracion."""
        return getattr(cls, key, default)

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Establecer valor de configuracion."""
        setattr(cls, key, value)

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Exportar configuracion como diccionario."""
        return {
            key: value for key, value in cls.__dict__.items()
            if not key.startswith("_") and not callable(value)
        }

    @classmethod
    def validate(cls) -> List[str]:
        """Validar configuracion y retornar lista de errores."""
        errors = []
        if not cls.OLLAMA_BASE_URL.startswith("http"):
            errors.append("OLLAMA_BASE_URL debe ser una URL valida")
        if cls.API_PORT < 1 or cls.API_PORT > 65535:
            errors.append("API_PORT debe estar entre 1 y 65535")
        return errors