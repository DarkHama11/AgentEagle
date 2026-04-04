# src/core/config.py
"""AgentEagle Cloud Security Specialist - Configuración centralizada."""
from pathlib import Path
from typing import Dict, List


class Config:
    """Configuración optimizada para RTX 3050 (4GB VRAM)."""

    BASE_DIR: Path = Path(__file__).resolve().parents[2]
    LOGS_DIR: Path = BASE_DIR / "logs"
    MODELS_DIR: Path = BASE_DIR / "models"
    DATA_DIR: Path = BASE_DIR / "data"

    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    CORS_ORIGINS: List[str] = ["*"]

    DEFAULT_MODEL_KEY: str = "3b"

    MODELS: Dict[str, dict] = {
        "3b": {
            "ollama_model": "llama3.2:3b",
            "temperature": 0.2,
            "max_tokens": 384,
            "context_length": 2048,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        },
        "7b": {
            "ollama_model": "deepseek-r1:7b",
            "temperature": 0.15,
            "max_tokens": 384,
            "context_length": 1536,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        },
        "phi": {
            "ollama_model": "phi:2",
            "temperature": 0.3,
            "max_tokens": 256,
            "context_length": 1024,
        },
    }

    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    ENABLE_WEB_SEARCH: bool = True
    MAX_CONCURRENT_REQUESTS: int = 2
    REQUEST_TIMEOUT_SECONDS: int = 60
