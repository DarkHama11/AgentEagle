import logging
from typing import Dict, Any
from core.agent import BaseAgent

logger = logging.getLogger(__name__)


class RouterAgent(BaseAgent):
    """
    RouterAgent: Usa Ollama para clasificar mensajes en lenguaje natural
    y redirigirlos al agente correspondiente.
    """

    def __init__(self, event_bus, llm_service=None):
        super().__init__("RouterAgent", event_bus)

        # Inicializar LLMService
        if llm_service is None:
            from services.llm_service import LLMService
            self.llm = LLMService()
        else:
            self.llm = llm_service

        # Suscribirse a eventos de texto del usuario
        self.subscribe("message.text_received", self._handle_text_message)

        logger.info(f"🧠 RouterAgent inicializado. Ollama disponible: {self.llm.is_available()}")

    def _handle_text_message(self, event: Dict[str, Any]):
        """Maneja mensajes de texto del usuario"""
        payload = event.get("payload", {})
        mensaje = payload.get("text", "").strip()
        chat_id = payload.get("chat_id")
        message_id = payload.get("message_id")

        if not mensaje or not chat_id:
            return

        if len(mensaje) < 3:
            return

        logger.info(f"🧠 [Router] Procesando mensaje: '{mensaje[:50]}...'")

        if not self.llm.is_available():
            logger.warning("🧠 [Router] Ollama no disponible, ignorando mensaje")
            return

        try:
            # Clasificar intención con Ollama
            intencion = self.llm.clasificar_intencion(mensaje)
            logger.info(f"🧠 [Router] Intención detectada: {intencion}")

            # Mapeo de intenciones a eventos
            eventos_map = {
                "pdf2word": "conversion.pdf_to_word",
                "word2pdf": "conversion.word_to_pdf",
                "print": "document.received",
                "ocr": "conversion.ocr_pdf",  # Por defecto OCR de PDF
                "analyze": "document.analysis_requested",
                "smart_convert": "conversion.pdf_to_word_smart",
                "help": "bot.help_requested",
                "status": "bot.status_requested",
            }

            evento_destino = eventos_map.get(intencion)

            if evento_destino:
                payload_enriquecido = payload.copy()
                payload_enriquecido["detected_intent"] = intencion
                payload_enriquecido["original_message"] = mensaje

                self.publish(evento_destino, payload_enriquecido)
                logger.info(f"🧠 [Router] Evento publicado: {evento_destino}")
            else:
                logger.warning(f"🧠 [Router] Intención desconocida: {intencion}")

        except Exception as e:
            logger.error(f"🧠 [Router] Error procesando mensaje: {e}", exc_info=True)