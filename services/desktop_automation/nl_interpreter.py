import json
import logging
import re
from typing import Dict, Any, Optional, List

from services.llm_service import LLMService
from dto.desktop_automation.action_dto import AutomationAction, ActionType

logger = logging.getLogger("AgentEagle.DesktopAutomation.NLInterpreter")


class NLInterpreter:
    """
    Interpreta instrucciones en lenguaje natural y las convierte
    en acciones de automatización estructuradas usando Ollama.
    """

    SYSTEM_PROMPT = """
Eres un intérprete de instrucciones de automatización de escritorio.
Tu tarea es convertir instrucciones en lenguaje natural en acciones JSON estructuradas.

Acciones disponibles:
- convert_pdf_to_word: Convierte PDF a Word usando PDFgear
- convert_pdf_to_excel: Convierte PDF a Excel usando PDFgear
- convert_pdf_to_ppt: Convierte PDF a PowerPoint usando PDFgear
- open_app: Abre una aplicación
- close_app: Cierra una aplicación

Responde SOLO con un JSON válido en este formato:
{
  "action_type": "nombre_de_la_accion",
  "plugin_name": "pdfgear",
  "parameters": {
    "pdf_path": "/ruta/al/archivo.pdf"
  },
  "requires_approval": false,
  "max_retries": 3
}

Si la instrucción es ambigua o no puedes interpretarla, responde:
{"error": "No se pudo interpretar la instrucción", "suggestions": ["..."]}
"""

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService()

    async def interpret(self, instruction: str, context: Dict[str, Any] = None) -> Optional[AutomationAction]:
        """
        Interpreta una instrucción en lenguaje natural.
        Ejemplo: "Convierte el archivo factura.pdf a Word"
        """
        context = context or {}

        # Construir prompt con contexto
        user_prompt = f"""
Instrucción del usuario: "{instruction}"

Contexto adicional:
{json.dumps(context, indent=2, ensure_ascii=False)}

Responde con el JSON de la acción a ejecutar:
"""

        try:
            response = await self.llm_service.generate_async(
                model="llama3.2:3b",
                prompt=user_prompt,
                system=self.SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=500
            )

            # Extraer JSON de la respuesta
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if not json_match:
                logger.error(f"No se encontró JSON en respuesta: {response}")
                return None

            action_data = json.loads(json_match.group(0))

            if "error" in action_data:
                logger.warning(f"Error en interpretación: {action_data['error']}")
                return None

            # Crear DTO de acción
            import uuid
            action = AutomationAction(
                action_id=f"AUTO-{uuid.uuid4().hex[:8].upper()}",
                action_type=ActionType(action_data["action_type"]),
                plugin_name=action_data.get("plugin_name", "pdfgear"),
                parameters=action_data.get("parameters", {}),
                requires_approval=action_data.get("requires_approval", False),
                max_retries=action_data.get("max_retries", 3)
            )

            logger.info(f"Instrucción interpretada: {instruction} → {action.action_type.value}")
            return action

        except Exception as e:
            logger.error(f"Error interpretando instrucción: {e}", exc_info=True)
            return None