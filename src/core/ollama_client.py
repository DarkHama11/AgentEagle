# src/core/ollama_client.py
"""AgentEagle++ - Cliente HTTP para interactuar con Ollama."""
import logging
from typing import Optional, Dict, Any, List
import requests

logger = logging.getLogger(__name__)


class OllamaClient:
    """Cliente para conectarse a Ollama vía API REST."""

    def __init__(self, model: str = "llama3.2:3b", base_url: str = "http://localhost:11434", timeout: int = 60):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/generate"
        self.tags_url = f"{self.base_url}/api/tags"
        self.timeout = timeout
        logger.info(f"🔄 OllamaClient: {model} @ {base_url}")

    def _build_payload(self, prompt: str, model: Optional[str] = None, max_tokens: Optional[int] = None,
                       temperature: Optional[float] = None, options: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[
        str, Any]:
        target_model = model or self.model
        final_options = {"num_predict": 384, "temperature": 0.3, "num_ctx": 1536}
        if options and isinstance(options, dict):
            final_options.update(options)
        if temperature is not None:
            final_options["temperature"] = temperature
        if max_tokens is not None:
            final_options["num_predict"] = max_tokens
        for key in ["top_p", "top_k", "repeat_penalty", "stop", "seed"]:
            if key in kwargs:
                final_options[key] = kwargs[key]

        return {"model": target_model, "prompt": prompt, "stream": False, "options": final_options, "keep_alive": "3m"}

    def generate(self, prompt: str, max_tokens: Optional[int] = None, temperature: Optional[float] = None,
                 model: Optional[str] = None, options: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        payload = self._build_payload(prompt=prompt, model=model, max_tokens=max_tokens, temperature=temperature,
                                      options=options, **kwargs)
        logger.debug(f"📤 Ollama: model={payload['model']}, tokens={payload['options'].get('num_predict')}")

        try:
            response = requests.post(self.api_url, json=payload, timeout=self.timeout,
                                     headers={"Content-Type": "application/json"})
            response.raise_for_status()
            result = response.json()
            generated = result.get("response", "")
            if not generated:
                logger.warning("⚠️ Ollama respondió sin contenido")
                return ""
            logger.debug(f"📥 Respuesta: {len(generated)} chars")
            return generated.strip()
        except requests.exceptions.ConnectionError:
            logger.error("❌ No se pudo conectar con Ollama. ¿Está 'ollama serve' corriendo?")
            return ""
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout después de {self.timeout}s")
            return ""
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP {e.response.status_code}: {e.response.text[:200]}")
            return ""
        except Exception as e:
            logger.error(f"❌ Error en generate(): {type(e).__name__} - {e}", exc_info=True)
            return ""

    def list_models(self) -> List[str]:
        try:
            response = requests.get(self.tags_url, timeout=5)
            response.raise_for_status()
            models_data = response.json().get("models", [])
            return [m.get("name", "") for m in models_data if m.get("name")]
        except Exception as e:
            logger.error(f"❌ Error listando modelos: {e}")
            return []

    def health_check(self) -> Dict[str, Any]:
        result = {"client": "OllamaClient", "base_url": self.base_url, "model": self.model, "connected": False}
        try:
            response = requests.get(f"{self.base_url}/api/version", timeout=3)
            if response.status_code == 200:
                result["connected"] = True
                result["version"] = response.json().get("version", "unknown")
                result["models_available"] = self.list_models()
        except Exception as e:
            result["error"] = str(e)
        return result