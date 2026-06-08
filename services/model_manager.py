import os
import yaml
import logging
import threading
from typing import Dict, Optional, List, Any
from datetime import datetime, timezone

logger = logging.getLogger("AgentEagle.ModelManager")


class ModelManager:
    """
    Gestor centralizado de modelos LLM (Patrón Singleton).
    """

    _instance: Optional['ModelManager'] = None
    _lock = threading.Lock()

    REQUIRED_KEYS = [
        "classification_model",
        "extraction_model",
        "summary_model",
        "routing_model",
        "chat_model",
        "reasoning_model",
        "print_decision_model",  # 🆕 Fase 7.1
        "default_model"
    ]

    def __new__(cls, config_path: Optional[str] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        if self._initialized:
            return

        self._setup_logging()

        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "models.yaml")

        self.config_path = config_path
        self._config: Dict[str, str] = {}
        self._config_lock = threading.RLock()

        self.load_config()

        self._initialized = True
        logger.info(f"ModelManager inicializado correctamente con: {self.config_path}")

    def _setup_logging(self) -> None:
        if logger.handlers:
            return

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logs_dir = os.path.join(base_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        log_file = os.path.join(logs_dir, "model_manager.log")

        file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
        file_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

    def load_config(self) -> None:
        with self._config_lock:
            if not os.path.exists(self.config_path):
                error_msg = f"Archivo de configuración no encontrado: {self.config_path}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = yaml.safe_load(f)
                    self._config = loaded_config if loaded_config else {}

                logger.debug(f"Configuración cargada: {self._config}")
                self._validate_config()
                logger.info(f"Configuración cargada exitosamente desde: {self.config_path}")

            except yaml.YAMLError as e:
                error_msg = f"Error parseando YAML: {e}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            except Exception as e:
                error_msg = f"Error inesperado cargando configuración: {e}"
                logger.error(error_msg)
                raise

    def _validate_config(self) -> None:
        missing_keys = []

        for key in self.REQUIRED_KEYS:
            if key not in self._config:
                missing_keys.append(key)
            elif not isinstance(self._config[key], str) or not self._config[key].strip():
                logger.warning(f"La clave '{key}' tiene un valor vacío o inválido")
                missing_keys.append(key)

        if missing_keys:
            error_msg = f"Configuración inválida. Faltan o son inválidas las claves: {', '.join(missing_keys)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("Validación de configuración exitosa")

    def reload(self) -> None:
        logger.info("Solicitando recarga de configuración de modelos...")
        try:
            self.load_config()
            logger.info("Configuración recargada exitosamente")
        except Exception as e:
            logger.error(f"Error crítico recargando configuración: {e}")
            raise

    def get_model(self, task_type: str) -> str:
        with self._config_lock:
            key = f"{task_type}_model"

            if key in self._config and self._config[key]:
                model = self._config[key]
                logger.debug(f"Modelo resuelto para tarea '{task_type}': {model}")
                return model

            default_model = self._config.get("default_model")
            if default_model:
                logger.warning(f"Tarea '{task_type}' no configurada explícitamente. Usando default: {default_model}")
                return default_model

            error_msg = f"No hay modelo configurado para '{task_type}' y falta 'default_model'"
            logger.error(error_msg)
            raise KeyError(error_msg)

    def get_all_models(self) -> Dict[str, str]:
        with self._config_lock:
            return self._config.copy()

    def validate_models(self) -> Dict[str, bool]:
        try:
            from services.llm_service import LLMService
            llm_service = LLMService()
        except ImportError:
            logger.error("No se pudo importar LLMService para validación de modelos")
            return {}

        availability = {}
        unique_models = set(self._config.values())

        logger.info(f"Validando disponibilidad de {len(unique_models)} modelos únicos en Ollama...")

        for model in unique_models:
            try:
                is_available = llm_service.is_model_available(model)
                availability[model] = is_available

                if is_available:
                    logger.info(f"✅ Modelo disponible: {model}")
                else:
                    logger.warning(f"❌ Modelo NO disponible en Ollama: {model}")
            except Exception as e:
                logger.error(f"Error verificando modelo {model}: {e}")
                availability[model] = False

        return availability

    def is_model_available(self, model_name: str) -> bool:
        try:
            from services.llm_service import LLMService
            llm_service = LLMService()
            return llm_service.is_model_available(model_name)
        except ImportError:
            logger.error("No se pudo importar LLMService")
            return False
        except Exception as e:
            logger.error(f"Error verificando disponibilidad de {model_name}: {e}")
            return False

    def update_model(self, task_type: str, model_name: str, save_to_file: bool = False) -> None:
        with self._config_lock:
            key = f"{task_type}_model"
            old_model = self._config.get(key, "N/A")
            self._config[key] = model_name

            logger.info(f"Modelo actualizado en memoria: {task_type} -> '{model_name}' (anterior: '{old_model}')")

            if save_to_file:
                self._save_config()

    def _save_config(self) -> None:
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            logger.info(f"Configuración persistida exitosamente en: {self.config_path}")
        except Exception as e:
            logger.error(f"Error guardando configuración en disco: {e}")
            raise

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance = None
                logger.info("Instancia de ModelManager reiniciada (Testing)")