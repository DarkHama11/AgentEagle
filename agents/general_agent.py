# -*- coding: utf-8 -*-
# src/agents/general_agent.py
"""AgentEagle - Agente generalista con busqueda web para deportes y actualidad."""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

from .base_agent import BaseAgent, AgentResponse
from src.core.config import Config

logger = logging.getLogger(__name__)


class GeneralAgent(BaseAgent):
    """🦅 AgentEagle General Assistant - Con busqueda web para deportes y actualidad"""

    def __init__(self, model_key: str = "general", enable_web_search: bool = True):
        super().__init__(model_key=model_key)
        self.enable_web_search = enable_web_search
        self.name = "general"
        self.description = "Asistente para preguntas de cultura general, deportes, actualidad"
        self.trigger_keywords = ["hola", "buenos", "buenas", "que dia", "que hora",
                                 "deporte", "futbol", "baloncesto", "tenis", "noticia",
                                 "actualidad", "cultura", "historia", "ciencia"]
        logger.info(f"🦅 GeneralAgent inicializado (model: {self.config['ollama_model']}, web: {enable_web_search})")

    def get_system_prompt(self) -> str:
        """Retorna el prompt de sistema para el agente general."""
        fecha = datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
        return f"""Eres AgentEagle 🦅, un asistente amigable y curioso.

📅 Hoy es {fecha}.

Tu proposito:
- Responder preguntas de cultura general, historia, ciencia, tecnologia
- Ayudar con deportes: horarios, resultados, noticias (recomendar fuentes oficiales)
- Proporcionar informacion de actualidad verificable
- Ser util, preciso y entretenido

Reglas importantes:
1. Para deportes en vivo: recomendar ESPN, OneFootball, sitios oficiales
2. Para noticias: citar fuentes confiables, no inventar informacion
3. Para salud: recomendar consultar profesionales medicos
4. Para recetas: sugerir AllRecipes o sitios especializados
5. Mantener tono amigable pero profesional

Si no sabes algo, se honesto y sugiere donde buscar informacion confiable.
"""

    def _detect_intent(self, user_input: str) -> str:
        """Detecta la intencion de la consulta del usuario."""
        t = user_input.lower()
        if any(k in t for k in ["hola", "buenos", "buenas", "hey", "hi"]):
            return "greeting"
        elif any(k in t for k in ["que dia", "fecha", "hoy es"]):
            return "date"
        elif any(k in t for k in ["que hora", "hora actual"]):
            return "time"
        elif any(k in t for k in ["futbol", "barcelona", "real madrid", "liga", "champions"]):
            return "sports_soccer"
        elif any(k in t for k in ["baloncesto", "nba", "basquet"]):
            return "sports_basketball"
        elif any(k in t for k in ["receta", "cocina", "comida", "preparar"]):
            return "cooking"
        elif any(k in t for k in ["salud", "medicina", "sintoma", "enfermedad"]):
            return "health"
        elif any(k in t for k in ["noticia", "actualidad", "ultimo", "reciente"]):
            return "news"
        return "question"

    async def process(self, user_input: str, conversation_history: Optional[List[Dict]] = None,
                      options: Optional[Dict[str, Any]] = None, context: Optional[Dict] = None) -> AgentResponse:
        """Procesa la consulta del usuario y retorna respuesta.

        Args:
            user_input: Consulta del usuario
            conversation_history: Historial opcional de mensajes
            options: Opciones adicionales para el modelo
            context: Contexto adicional (no usado en GeneralAgent, pero aceptado por compatibilidad)
        """
        intent = self._detect_intent(user_input)
        logger.info(f"🦅 [GENERAL] [INTENT: {intent}] '{user_input[:50]}...'")

        # Respuestas rapidas para intents especificos
        if intent == "greeting":
            return AgentResponse(
                agent=self.name, intent=intent, response=self._get_greeting(),
                tokens_used=0, execution_time_ms=0, metadata={"fast_response": True})

        elif intent == "date":
            fecha = datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
            return AgentResponse(
                agent=self.name, intent=intent,
                response=f"📅 Hoy es {fecha}. ¿Que te gustaria saber?",
                tokens_used=0, execution_time_ms=0, metadata={"fast_response": True})

        elif intent == "time":
            hora = datetime.now().strftime("%H:%M:%S")
            return AgentResponse(
                agent=self.name, intent=intent,
                response=f"🕐 Son las {hora}. ¿En que puedo ayudarte?",
                tokens_used=0, execution_time_ms=0, metadata={"fast_response": True})

        # Construir prompt para LLM
        system_prompt = self.get_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history[-10:])

        messages.append({"role": "user", "content": user_input})
        full_prompt = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in messages)

        try:
            # ✅ FIX: Sin parametro 'model' - ya configurado en ModelWrapper.__init__
            respuesta_cruda = self.model.generate(prompt=full_prompt, options=options)

            if isinstance(respuesta_cruda, dict):
                texto = respuesta_cruda.get("response", str(respuesta_cruda))
            else:
                texto = str(respuesta_cruda)

            texto = re.sub(r'^(Asistente|Respuesta|AgentEagle|Assistant):\s*', '', texto.strip(), flags=re.I)

            return AgentResponse(
                agent=self.name, intent=intent, response=texto,
                tokens_used=len(texto) // 4,
                execution_time_ms=0,
                metadata={"model": self.config["ollama_model"], "intent_confidence": 0.9})

        except Exception as e:
            logger.error(f"❌ Error en GeneralAgent: {e}")
            return AgentResponse(
                agent=self.name, intent=intent,
                response=self._get_fallback_response(user_input, intent),
                tokens_used=0, execution_time_ms=0,
                metadata={"error": str(e)[:100], "fallback": True})

    def _get_greeting(self) -> str:
        """Retorna saludo aleatorio."""
        import random
        greetings = [
            "👋 ¡Hola! Soy AgentEagle 🦅, tu asistente para preguntas de todo tipo. ¿En que puedo ayudarte hoy?",
            "🦅 ¡Hola! Curiosidad es mi especialidad. ¿Que quieres saber?",
            "👋 ¡Bienvenido! Soy AgentEagle 🦅. Preguntame lo que quieras: historia, ciencia, tecnologia, cultura... ¡Estoy aqui para ayudar! ✨",
        ]
        return random.choice(greetings)

    def _get_fallback_response(self, user_input: str, intent: str) -> str:
        """Respuestas de fallback cuando el modelo falla."""
        fallbacks = {
            "sports_soccer": f"⚽ Para horarios y resultados en vivo de futbol, te recomiendo: ESPN, OneFootball, o el sitio oficial del equipo. ¿En que mas puedo ayudarte?",
            "cooking": f"🍳 Para recetas actualizadas, te recomiendo AllRecipes o sitios de cocina especializados. ¿Necesitas ayuda con algo mas?",
            "health": f"🏥 Para temas de salud, consulta siempre a un profesional medico. ¿En que mas puedo asistirte?",
            "news": f"📰 Para noticias verificadas, te recomiendo medios confiables como BBC, Reuters, o agencias oficiales. ¿Hay algo especifico que busques?",
        }
        return fallbacks.get(intent,
                             f"🦅 Gracias por tu pregunta. Estoy procesando la informacion. Mientras tanto, ¿hay algo mas en lo que pueda ayudarte?")