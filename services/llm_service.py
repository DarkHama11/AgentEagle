import logging
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger("AgentEagle.LLMService")


class LLMService:
    """
    Servicio wrapper para interacción con Ollama.
    Proporciona una interfaz unificada para generación de texto.
    """

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        logger.info(f"LLMService inicializado con URL: {base_url}")

    def generate(
            self,
            model: str,
            prompt: str,
            system: Optional[str] = None,
            temperature: float = 0.7,
            max_tokens: int = 2048
    ) -> str:
        """
        Genera texto usando un modelo LLM.

        :param model: Nombre del modelo (ej: "llama3.2:3b")
        :param prompt: Prompt del usuario
        :param system: Prompt de sistema (opcional)
        :param temperature: Temperatura de generación
        :param max_tokens: Máximo de tokens a generar
        :return: Texto generado
        """
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        if system:
            payload["system"] = system

        try:
            logger.debug(f"Enviando solicitud a Ollama: modelo={model}, prompt_length={len(prompt)}")
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()

            result = response.json()
            generated_text = result.get("response", "")

            logger.debug(f"Respuesta generada: {len(generated_text)} caracteres")
            return generated_text

        except requests.exceptions.RequestException as e:
            logger.error(f"Error al comunicarse con Ollama: {e}")
            raise RuntimeError(f"Fallo en la generación LLM: {e}")
        except Exception as e:
            logger.error(f"Error inesperado en LLMService: {e}")
            raise

    def chat(
            self,
            model: str,
            messages: list,
            temperature: float = 0.7,
            max_tokens: int = 2048
    ) -> str:
        """
        Genera texto usando el formato de chat (más estructurado).

        :param model: Nombre del modelo
        :param messages: Lista de mensajes [{"role": "user", "content": "..."}]
        :param temperature: Temperatura de generación
        :param max_tokens: Máximo de tokens
        :return: Texto generado
        """
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        try:
            logger.debug(f"Enviando solicitud de chat a Ollama: modelo={model}")
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()

            result = response.json()
            message = result.get("message", {})
            generated_text = message.get("content", "")

            logger.debug(f"Respuesta de chat generada: {len(generated_text)} caracteres")
            return generated_text

        except requests.exceptions.RequestException as e:
            logger.error(f"Error al comunicarse con Ollama (chat): {e}")
            raise RuntimeError(f"Fallo en la generación LLM (chat): {e}")
        except Exception as e:
            logger.error(f"Error inesperado en LLMService (chat): {e}")
            raise

    def health_check(self) -> bool:
        """Verifica si Ollama está disponible."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False