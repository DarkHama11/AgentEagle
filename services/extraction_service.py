import json
import re
import logging
from typing import Dict, Any, List
from services.llm_service import LLMService
from services.model_manager import ModelManager

logger = logging.getLogger("AgentEagle.ExtractionService")


class ExtractionService:
    """
    Servicio de extracción de campos estructurados de documentos.
    Usa LLM para extraer información específica según el tipo de documento.
    """

    def __init__(self, llm_service: LLMService, model_manager: ModelManager):
        self.llm_service = llm_service
        self.model_manager = model_manager

        self._field_definitions = {
            "invoice": ["invoice_number", "supplier", "date", "amount", "reference", "customer", "due_date"],
            "receipt": ["transaction_status", "store", "date", "amount", "cus", "nequi_reference", "taxes",
                        "commerce_invoice", "reference_1", "reference_2", "reference_3", "description"],
            "contract": ["contract_number", "parties", "start_date", "end_date", "value", "subject"],
            "report": ["title", "author", "date", "summary", "conclusions"]
        }

        logger.info("ExtractionService inicializado")

    def extract(self, document_type: str, text: str) -> Dict[str, Any]:
        """
        Extrae campos estructurados de un documento.
        """
        if not text or len(text.strip()) < 50:
            logger.warning("Texto demasiado corto para extracción")
            return {"fields": {}, "error": "Texto insuficiente"}

        # ✅ USO DEL MODEL MANAGER: Nunca hardcodear "llama3.2:3b" aquí
        model = self.model_manager.get_model("extraction")
        fields_to_extract = self._field_definitions.get(document_type, [])

        if not fields_to_extract:
            logger.warning(f"No hay definición de campos para tipo: {document_type}")
            return {"fields": {}, "error": f"Tipo de documento no soportado: {document_type}"}

        system_prompt = f"""Eres un experto en extracción de información de documentos.
Tu tarea es extraer campos específicos de un documento de tipo '{document_type}'.

Campos a extraer:
{', '.join(fields_to_extract)}

Instrucciones importantes:
- Extrae TODA la información que esté presente en el texto, incluso si dice "Sin información"
- Si un campo dice "Sin información", extrae ese valor literal
- Para montos, incluye el símbolo de moneda si está presente
- Para fechas, extrae el formato exacto como aparece
- Responde SOLO con un JSON válido

Formato de respuesta:
{{
  "fields": {{
    "campo1": "valor1",
    "campo2": "valor2"
  }}
}}"""

        user_prompt = f"""Extrae TODOS los campos del siguiente documento de tipo '{document_type}':

---
{text[:4000]}
---

Recuerda: Extrae TODOS los campos, incluso si dicen "Sin información".
Responde con el JSON de extracción:"""

        try:
            logger.info(f"Extrayendo campos de documento tipo '{document_type}' con modelo: {model}")

            response = self.llm_service.generate(
                model=model,
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.1,
                max_tokens=800
            )

            result = self._parse_extraction_response(response, fields_to_extract)

            logger.info(f"Campos extraídos: {len(result.get('fields', {}))} campos")
            return result

        except Exception as e:
            logger.error(f"Error en extracción: {e}", exc_info=True)
            return {"fields": {}, "error": str(e)}

    def _parse_extraction_response(self, response: str, expected_fields: List[str]) -> Dict[str, Any]:
        """Parsea la respuesta del LLM para extraer el JSON de campos."""
        try:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{[^{}]*"fields"[^{}]*\{[^{}]*\}[^{}]*\}', response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)

            if json_match:
                json_str = json_match.group(1) if '```' in json_match.group(0) else json_match.group(0)
                data = json.loads(json_str)

                fields = data.get("fields", data)

                cleaned_fields = {}
                for field in expected_fields:
                    if field in fields:
                        value = fields[field]
                        if value is not None:
                            cleaned_fields[field] = str(value).strip()

                return {
                    "fields": cleaned_fields,
                    "extracted_count": len(cleaned_fields)
                }
            else:
                logger.warning("No se encontró JSON en la respuesta de extracción")
                return {"fields": {}, "error": "No se pudo parsear la respuesta del LLM"}
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parseando respuesta de extracción: {e}", exc_info=True)
            return {"fields": {}, "error": f"Error de parsing: {str(e)}"}