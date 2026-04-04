# src/agents/general_agent.py
"""AgentEagle++ - Agente generalista con búsqueda web para deportes y actualidad."""
from .base_agent import BaseAgent
from typing import Dict, Any, Optional
import logging
import re
import hashlib
from datetime import datetime

# ✅ PRIMERO: Inicializar logger
logger = logging.getLogger(__name__)

# ✅ Imports opcionales para búsqueda web
try:
    from tools.security_search import SecuritySearch

    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False
    logger.warning("⚠️ SecuritySearch no disponible (búsqueda web desactivada)")


class GeneralAgent(BaseAgent):
    """🦞 AgentEagle General Assistant - Con búsqueda web para deportes y actualidad"""

    MODEL_CONFIGS = {
        "3b": {"name": "llama3.2:3b", "temp": 0.3, "max_tokens": 512},
        "7b": {"name": "deepseek-r1:7b", "temp": 0.25, "max_tokens": 512},
    }

    CONVERSATIONAL_RESPONSES = {
        "greeting": [
            "👋 ¡Hola! Soy AgentEagle 🦅, tu asistente para preguntas de todo tipo. ¿En qué puedo ayudarte hoy?",
            "🦞 ¡Hola! Curiosidad es mi especialidad. ¿Qué quieres saber?",
            "👋 ¡Bienvenido! Soy AgentEagle 🦅. Pregúntame lo que quieras: historia, ciencia, tecnología, cultura... ¡Estoy aquí para ayudar! ✨",
        ],
        "goodbye": [
            "👋 ¡Hasta pronto! Vuelve cuando tengas más preguntas 🦞",
            "🦞 ¡Nos vemos! La curiosidad nunca descansa ✨",
        ],
        "thanks": [
            "😊 ¡Me alegra ayudar! ¿Algo más en lo que pueda asistirte? 🦞",
            "🙌 ¡De nada! Preguntar es la mejor forma de aprender ✨",
        ],
        "date": lambda: f"📅 Hoy es {_get_fecha_espanol()}. ¿Qué te gustaría saber?",
    }

    def __init__(self, model_key: str = "3b", enable_web_search: bool = True):
        super().__init__("general", model_key)
        self.config = self.MODEL_CONFIGS.get(model_key, self.MODEL_CONFIGS["3b"])
        self.system_prompt = self._build_system_prompt()
        self.enable_web_search = enable_web_search and SEARCH_AVAILABLE
        self.searcher = SecuritySearch(timeout=10) if self.enable_web_search else None
        logger.info(f"🦞 GeneralAgent inicializado (model: {self.config['name']}, web: {self.enable_web_search})")

    def _build_system_prompt(self) -> str:
        fecha = _get_fecha_espanol()

        return f"""📅 Hoy es {fecha}. Eres AgentEagle 🦅, un asistente amigable y curioso.

🎯 TU PERSONALIDAD:
• Amigable, cercano, con emojis 🦞✨
• Claro y práctico: adapta tu explicación al nivel del usuario
• Honesto: si no sabes algo, dilo y sugiere dónde buscar

📚 TEMAS QUE PUEDES ABORDAR:
• Tecnología, ciencia, historia, cultura, vida diaria
• Deportes: equipos, jugadores, historia (pero para horarios en vivo, sugiere fuentes oficiales)
• Actualidad: noticias generales (con búsqueda web si está disponible)

📋 FORMATO DE RESPUESTAS:
• 👋 Para saludos: cálido + oferta de ayuda
• 🔍 Para preguntas: explica claro, usa ejemplos, estructura con viñetas si es largo
• ⚽ Para deportes: da contexto histórico, pero para horarios/resultados en vivo → redirige a fuentes oficiales
• 📚 Para referencias: menciona fuentes confiables si es relevante

🚫 EVITA:
• Inventar horarios de partidos o resultados en tiempo real
• Dar consejos médicos, legales o financieros profesionales
• Opiniones personales controvertidas

💬 EJEMPLOS:

Usuario: "¿Qué es Microsoft Word?"
Asistente: "📝 **Microsoft Word** es un procesador de textos parte de Microsoft Office 🦞
• Propósito: crear, editar y dar formato a documentos
• Características: estilos, tablas, imágenes, revisión ortográfica
• Alternativas: Google Docs, LibreOffice Writer, Apple Pages
💡 Tip: Usa Ctrl+S para guardar frecuentemente. ¿Necesitas ayuda con alguna función?"

Usuario: "¿Cuándo juega el Barcelona?"
Asistente: "⚽ **FC Barcelona** 🦞
Para información en tiempo real sobre partidos del Barça:
• 🌐 Sitio oficial: fcbarcelona.com
• 📱 Apps: ESPN, OneFootball, la app oficial del club
• 📺 Transmisiones: Dependen de tu región y derechos de TV
💡 Tip: Los horarios pueden cambiar por razones de TV o seguridad. ¡Verifica siempre fuentes oficiales!
¿Necesitas ayuda con algo más relacionado con deportes o tecnología?"

Usuario: "¿Quién ganó la Champions 2024?"
Asistente: "🏆 **UEFA Champions League** 🦞
Para resultados oficiales y actualizados de la Champions:
• 🌐 UEFA.com: uefa.com/championsleague
• 📱 Apps: OneFootball, ESPN, la app oficial de UEFA
• 📰 Noticias: Marca, AS, BBC Sport
💡 Los resultados y estadísticas se actualizan en tiempo real en estas fuentes.
¿Te interesa saber más sobre fútbol europeo o historia de la Champions?"

Ahora responde como AgentEagle 🦅:

Usuario: """

    def _format_prompt(self, user_input: str, context: Optional[Dict] = None, web_context: Optional[str] = None) -> str:
        history = context.get("history", []) if context else []
        recent = history[-3:] if len(history) > 3 else history
        history_text = "\n".join(
            f"{'Usuario' if m.get('role') == 'user' else 'Asistente'}: {m.get('content', '')}" for m in recent)

        web_section = ""
        if web_context:
            web_section = f"\n\n🌐 **Información actualizada**:\n{web_context}\n\nUsa esta información para responder con datos recientes."

        parts = [self.system_prompt, history_text, web_section, f"{user_input}", "Asistente:"]
        return "\n".join(p for p in parts if p)

    def _clean_response(self, text: str) -> str:
        if not text: return ""
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'^(Asistente|Respuesta|AgentEagle):\s*', '', text.strip(), flags=re.I)
        return text.strip()

    def _detect_topic_emoji(self, user_input: str) -> str:
        """Detecta el tema para emoji contextual."""
        t = user_input.lower()

        if any(k in t for k in
               ["fútbol", "futbol", "barça", "barcelona", "real madrid", "partido", "liga", "gol", "equipo",
                "champions", "uefa"]):
            return "⚽"
        elif any(k in t for k in ["baloncesto", "basket", "nba", "canasta"]):
            return "🏀"
        elif any(k in t for k in ["tenis", "wimbledon", "rafa", "federer"]):
            return "🎾"
        elif any(k in t for k in ["cocina", "receta", "comida", "cocinar"]):
            return "🍳"
        elif any(k in t for k in ["viaje", "turismo", "vacaciones", "destino"]):
            return "✈️"
        elif any(k in t for k in ["salud", "medicina", "síntoma", "enfermedad"]):
            return "🏥"
        elif any(k in t for k in ["dinero", "finanzas", "inversión", "banco"]):
            return "💰"
        elif any(k in t for k in ["historia", "independencia", "guerra", "revolución"]):
            return "📜"
        elif any(k in t for k in ["ciencia", "física", "química", "biología"]):
            return "🔬"
        elif any(k in t for k in ["tecnología", "software", "app", "programa"]):
            return "💻"

        return "🦞"

    def _is_sports_live_question(self, user_input: str) -> bool:
        """Detecta si la pregunta es sobre deportes en tiempo real (horarios, resultados)."""
        t = user_input.lower()
        live_keywords = ["próximo partido", "cuándo juega", "horario", "fecha partido", "resultado", "quién ganó",
                         "marcador", "en vivo", "live"]
        sports_keywords = ["fútbol", "futbol", "barça", "barcelona", "real madrid", "champions", "liga", "nba", "tenis"]

        return any(sk in t for sk in sports_keywords) and any(lk in t for lk in live_keywords)

    def _get_conversational_response(self, intent: str, user_input: str = "") -> str:
        import random
        topic_emoji = self._detect_topic_emoji(user_input)

        # Respuestas temáticas específicas
        if intent not in ["greeting", "goodbye", "thanks", "date"]:
            t = user_input.lower()
            if self._is_sports_live_question(user_input):
                return f"{topic_emoji} ¡Hola! Soy AgentEagle 🦅. Para horarios y resultados en vivo, te recomiendo: ESPN, OneFootball, o el sitio oficial del equipo. ¿En qué más puedo ayudarte?"
            elif any(k in t for k in ["cocina", "receta", "comida"]):
                return f"{topic_emoji} ¡Hola! Soy AgentEagle 🦅. Para recetas actualizadas, te recomiendo AllRecipes o sitios de cocina. ¿Necesitas ayuda con algo más?"
            elif any(k in t for k in ["salud", "medicina", "síntoma"]):
                return f"{topic_emoji} ¡Hola! Soy AgentEagle 🦅. Para temas de salud, consulta siempre a un profesional médico. ¿En qué más puedo asistirte?"

        if intent == "date" and callable(self.CONVERSATIONAL_RESPONSES.get("date")):
            return self.CONVERSATIONAL_RESPONSES["date"]()
        if intent in self.CONVERSATIONAL_RESPONSES and not callable(self.CONVERSATIONAL_RESPONSES[intent]):
            return random.choice(self.CONVERSATIONAL_RESPONSES[intent])

        return f"{topic_emoji} Hoy es {_get_fecha_espanol()}. ¿Qué te gustaría saber? 🦞"

    def _get_general_web_context(self, user_input: str) -> Optional[str]:
        """Búsqueda web para preguntas de actualidad, especialmente deportes."""
        if not self.enable_web_search or not self.searcher:
            return None

        # === BÚSQUEDA PARA DEPORTES EN TIEMPO REAL ===
        if self._is_sports_live_question(user_input):
            try:
                # Construir query optimizado para deportes
                t = user_input.lower()
                if "barcelona" in t or "barça" in t:
                    query = "FC Barcelona próximo partido horario site:fcbarcelona.com OR site:espndeportes.com"
                elif "real madrid" in t:
                    query = "Real Madrid próximo partido horario site:realmadrid.com OR site:espndeportes.com"
                elif "champions" in t or "uefa" in t:
                    query = "UEFA Champions League resultados horarios site:uefa.com"
                elif "liga" in t or "laliga" in t:
                    query = "LaLiga próximos partidos horarios site:laliga.com"
                else:
                    query = f"{user_input} site:espndeportes.com OR site:marca.com OR site:onefootball.com"

                logger.info(f"🦞 Búsqueda deportes activada: '{query[:60]}...'")
                results = self.searcher.search(query, num_results=3)

                if results and 'error' not in results[0]:
                    # Formatear resultados específicos para deportes
                    lines = ["⚽ **Información deportiva actualizada**:\n"]
                    for r in results[:2]:
                        title = r.get('title', 'Sin título')[:80]
                        snippet = r.get('snippet', '')[:150]
                        url = r.get('url', '')[:70]
                        domain = r.get('domain', '')
                        lines.append(f"• **{title}**")
                        if domain: lines.append(f"  🌐 {domain}")
                        if snippet: lines.append(f"  📝 {snippet}...")
                        if url: lines.append(f"  🔗 {url}")
                        lines.append("")
                    return "\n".join(lines).strip()

            except Exception as e:
                logger.warning(f"⚠️ Búsqueda deportes falló: {e}")

        # === BÚSQUEDA GENERAL PARA ACTUALIDAD ===
        current_keywords = ["último", "reciente", "hoy", "ahora", "próximo", "noticia", "actualidad", "precio actual"]
        static_keywords = ["quién inventó", "qué es", "definición", "historia de"]

        if any(k in user_input.lower() for k in current_keywords) and not any(
                k in user_input.lower() for k in static_keywords):
            try:
                results = self.searcher.search(user_input, num_results=3)
                if results and 'error' not in results[0]:
                    return self.searcher.format_results_for_llm(results[:2])
            except Exception as e:
                logger.warning(f"⚠️ Búsqueda web general falló: {e}")

        return None

    def _get_fallback_response(self, user_input: str) -> str:
        topic_emoji = self._detect_topic_emoji(user_input)
        return (
            f"{topic_emoji} Disculpa, tuve un pequeño problema técnico 🛠️ "
            f"Intenta reformular tu pregunta. Ejemplos:\n"
            f"• '¿Qué es [concepto] y para qué sirve?'\n"
            f"• '¿Quién inventó [cosa] y cuándo?'\n"
            f"• '¿Cómo funciona [tecnología] en términos simples?'\n\n"
            f"🦞 ¡Estoy aquí para ayudarte con preguntas de todo tipo! ✨"
        )

    def _error_response(self, message: str) -> Dict[str, Any]:
        return {
            "agent": self.name,
            "response": f"🦞 ⚠️ {message}",
            "model": self.config["name"],
            "model_key": self.model_key,
            "success": False,
            "error": True
        }

    async def process(self, user_input: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        intent = self._detect_intent(user_input)
        topic_emoji = self._detect_topic_emoji(user_input)
        logger.info(f"🦞 [GENERAL] [INTENT: {intent}] '{user_input[:80]}...'")

        if intent in ["greeting", "goodbye", "thanks", "date"]:
            respuesta = self._get_conversational_response(intent, user_input)
            return self._build_response(respuesta, success=True, model=self.config["name"], intent_detected=intent,
                                        tokens_used=len(respuesta.split()), fast_response=True, web_search_used=False)

        # === Búsqueda web opcional ===
        web_context = None
        web_search_used = False

        if self.enable_web_search:
            web_context = self._get_general_web_context(user_input)
            if web_context:
                web_search_used = True
                logger.info(f"✅ Web context general: resultados obtenidos")

        full_prompt = self._format_prompt(user_input, context, web_context)

        try:
            options = {
                "temperature": self.config["temp"],
                "num_predict": self.config["max_tokens"],
                "num_ctx": self.config.get("context_length", 2048),
                "stop": ["Usuario:", "###"]
            }

            logger.debug(f"🧠 Enviando a {self.config['name']}")

            respuesta_cruda = self.model.generate(prompt=full_prompt, model=self.config["name"], options=options)
            respuesta_limpia = self._clean_response(respuesta_cruda)

            if self._should_use_fallback(respuesta_limpia, user_input, intent):
                logger.warning("⚠️ Fallback activado en GeneralAgent")
                respuesta_limpia = self._get_fallback_response(user_input)
            else:
                logger.info(f"✅ Respuesta generada ({len(respuesta_limpia)} chars)")

            return self._build_response(
                respuesta_limpia,
                success=True,
                model=self.config["name"],
                tokens_used=len(respuesta_limpia.split()) if respuesta_limpia else 0,
                intent_detected="question",
                web_search_used=web_search_used,
                web_results_count=2 if web_search_used else 0,
                web_search_category="deportes" if self._is_sports_live_question(user_input) else "general"
            )

        except ConnectionError:
            return self._error_response("No se pudo conectar con Ollama.")
        except TimeoutError:
            return self._error_response("Timeout.")
        except Exception as e:
            logger.error(f"❌ Error en GeneralAgent: {e}", exc_info=True)
            return self._error_response(f"Error: {str(e)[:100]}")


def _get_fecha_espanol() -> str:
    now = datetime.now()
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre"]
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return f"{dias[now.weekday()]}, {now.day} de {meses[now.month - 1]} de {now.year}, {now.strftime('%H:%M')}"