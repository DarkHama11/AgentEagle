import requests
import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class LLMService:
    """Servicio centralizado para interactuar con Ollama"""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2:3b"):
        self.base_url = base_url
        self.model = model
        self._warm = False
        logger.info(f"🧠 LLMService inicializado: {model} @ {base_url}")

    def is_available(self) -> bool:
        """Verifica si Ollama está disponible"""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, temperature: float = 0.1, max_tokens: int = 200) -> str:
        """Genera una respuesta del modelo"""
        try:
            inicio = time.time()
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                },
                timeout=60
            )

            if response.status_code == 200:
                resultado = response.json().get("response", "")
                tiempo = time.time() - inicio
                logger.debug(f"🧠 LLM respondió en {tiempo:.2f}s")
                return resultado.strip()
            else:
                logger.error(f"❌ Error HTTP {response.status_code} de Ollama")
                return ""
        except Exception as e:
            logger.error(f"❌ Error consultando Ollama: {e}")
            return ""

    def clasificar_intencion(self, mensaje: str) -> str:
        """Clasifica la intención del usuario en una categoría"""
        prompt = f"""Eres un clasificador de intenciones para un asistente de documentos.
Clasifica el mensaje del usuario en EXACTAMENTE UNA de estas categorías:

- pdf2word: convertir PDF a Word
- word2pdf: convertir Word a PDF  
- print: imprimir un documento
- ocr: extraer texto de imagen o PDF escaneado
- analyze: analizar el contenido de un documento
- smart_convert: reconstruir inteligentemente un PDF
- help: pedir ayuda o información
- status: consultar el estado del sistema
- unknown: no se puede clasificar

Responde SOLO con el nombre de la categoría, nada más.

Mensaje del usuario: "{mensaje}"

Categoría:"""

        resultado = self.generate(prompt, temperature=0.0, max_tokens=20)

        # Limpiar la respuesta
        categorias_validas = [
            "pdf2word", "word2pdf", "print", "ocr",
            "analyze", "smart_convert", "help", "status"
        ]

        resultado_limpio = resultado.lower().strip()
        for cat in categorias_validas:
            if cat in resultado_limpio:
                return cat

        return "unknown"

    def analizar_documento(self, texto: str) -> Dict[str, Any]:
        """Analiza el contenido de un documento"""
        prompt = f"""Analiza este documento y devuelve un JSON con esta estructura exacta:
{{
    "tipo": "tipo de documento (CV, factura, contrato, carta, informe, otro)",
    "resumen": "resumen en 2-3 líneas",
    "datos_clave": ["lista de datos importantes encontrados"]
}}

Documento:
{texto[:2000]}

JSON:"""

        resultado = self.generate(prompt, temperature=0.2, max_tokens=500)

        # Intentar parsear como JSON
        try:
            import json
            # Buscar el JSON en la respuesta
            inicio = resultado.find('{')
            fin = resultado.rfind('}') + 1
            if inicio >= 0 and fin > inicio:
                return json.loads(resultado[inicio:fin])
        except Exception as e:
            logger.warning(f"⚠️ No se pudo parsear JSON: {e}")

        return {
            "tipo": "desconocido",
            "resumen": resultado,
            "datos_clave": []
        }

    def generar_respuesta(self, contexto: str, pregunta: str) -> str:
        """Genera una respuesta basada en contexto"""
        prompt = f"""Basándote en este contexto, responde la pregunta de forma clara y concisa.

Contexto:
{contexto}

Pregunta: {pregunta}

Respuesta:"""

        return self.generate(prompt, temperature=0.3, max_tokens=300)