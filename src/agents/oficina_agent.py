# src/agents/oficina_agent.py
"""AgentEagle++ - Agente especializado en Microsoft Office."""
from .base_agent import BaseAgent
from typing import Dict, Any, Optional
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class OficinaAgent(BaseAgent):
    """📊 AgentEagle Office Specialist - Excel • Word • PowerPoint"""

    MODEL_CONFIGS = {
        "3b": {"name": "llama3.2:3b", "temp": 0.2, "max_tokens": 384},
        "7b": {"name": "deepseek-r1:7b", "temp": 0.15, "max_tokens": 384},
    }

    CONVERSATIONAL_RESPONSES = {
        "greeting": ["👋 ¡Hola! ¿Excel, Word o PowerPoint? 📊 ¿En qué ayudo hoy?"],
        "goodbye": ["👋 ¡Hasta pronto! Productividad máxima ⚡"],
        "thanks": ["😊 ¡Me alegra ayudar! ¿Más dudas de Office?"],
        "date": lambda: f"📅 Hoy es {_get_fecha_espanol()}. ¿Qué necesitas en Office?",
    }

    def __init__(self, model_key: str = "3b"):
        super().__init__("oficina", model_key)
        self.config = self.MODEL_CONFIGS.get(model_key, self.MODEL_CONFIGS["3b"])
        self.system_prompt = self._build_system_prompt()
        logger.info(f"📊 OficinaAgent inicializado (model: {self.config['name']})")

    def _build_system_prompt(self) -> str:
        fecha = _get_fecha_espanol()
        return f"""📅 Hoy es {fecha}. Eres un asistente experto en Microsoft Office.

INSTRUCCIONES:
• Responde en español, claro y práctico
• Usa emojis: 📊📝🎨⚡
• Pasos numerados + atajos de teclado
• Fórmulas exactas para Excel: =SUMA(A1:A10)

EJEMPLOS:

Usuario: "hola"
Asistente: "👋 ¡Hola! ¿Excel, Word o PowerPoint? 📊"

Usuario: "¿Suma en Excel?"
Asistente: "📌 **Sumar en Excel**:
1. Selecciona celda de resultado
2. Escribe `=SUMA(A1:A10)`
3. Presiona Enter
⚡ F4 fija referencias ($A$1)"

Ahora responde:

Usuario: """

    def _format_prompt(self, user_input: str, context: Optional[Dict] = None) -> str:
        history = context.get("history", []) if context else []
        recent = history[-3:] if len(history) > 3 else history
        history_text = "\n".join(f"{'Usuario' if m.get('role')=='user' else 'Asistente'}: {m.get('content','')}" for m in recent)
        parts = [self.system_prompt, history_text, f"{user_input}", "Asistente:"]
        return "\n".join(p for p in parts if p)

    def _clean_response(self, text: str) -> str:
        if not text: return ""
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'^(Asistente|Respuesta):\s*', '', text.strip(), flags=re.I)
        return text.strip()

    def _get_conversational_response(self, intent: str) -> str:
        import random
        if intent == "date" and callable(self.CONVERSATIONAL_RESPONSES.get("date")):
            return self.CONVERSATIONAL_RESPONSES["date"]()
        if intent in self.CONVERSATIONAL_RESPONSES and not callable(self.CONVERSATIONAL_RESPONSES[intent]):
            return random.choice(self.CONVERSATIONAL_RESPONSES[intent])
        return f"📊 Hoy es {_get_fecha_espanol()}. ¿Excel, Word o PowerPoint?"

    def _get_fallback_response(self, user_input: str) -> str:
        return "🔧 Disculpa, tuve un problema. Intenta reformular: ¿Excel, Word o PowerPoint? ¿Qué tarea?"

    def _error_response(self, message: str) -> Dict[str, Any]:
        return {"agent": self.name, "response": f"⚠️ {message}", "model": self.config["name"], "model_key": self.model_key, "success": False, "error": True}

    async def process(self, user_input: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        intent = self._detect_intent(user_input)
        logger.info(f"📝 [INTENT: {intent}] '{user_input[:80]}...'")
        if intent in ["greeting", "goodbye", "thanks", "date"]:
            respuesta = self._get_conversational_response(intent)
            return self._build_response(respuesta, success=True, model=self.config["name"], intent_detected=intent, tokens_used=len(respuesta.split()), fast_response=True)
        full_prompt = self._format_prompt(user_input, context)
        try:
            options = {"temperature": self.config["temp"], "num_predict": self.config["max_tokens"], "num_ctx": self.config.get("context_length", 1536), "stop": ["Usuario:", "###"]}
            respuesta_cruda = self.model.generate(prompt=full_prompt, model=self.config["name"], options=options)
            respuesta_limpia = self._clean_response(respuesta_cruda)
            if self._should_use_fallback(respuesta_limpia, user_input, intent):
                logger.warning("⚠️ Fallback activado")
                respuesta_limpia = self._get_fallback_response(user_input)
            return self._build_response(respuesta_limpia, success=True, model=self.config["name"], tokens_used=len(respuesta_limpia.split()) if respuesta_limpia else 0, intent_detected="question")
        except ConnectionError: return self._error_response("No se pudo conectar con Ollama.")
        except TimeoutError: return self._error_response("Timeout.")
        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)
            return self._error_response(f"Error: {str(e)[:100]}")


def _get_fecha_espanol() -> str:
    now = datetime.now()
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return f"{dias[now.weekday()]}, {now.day} de {meses[now.month - 1]} de {now.year}, {now.strftime('%H:%M')}"