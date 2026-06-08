import json
import re
import logging
from typing import Dict, Any
from services.llm_service import LLMService
from services.model_manager import ModelManager

logger = logging.getLogger("AgentEagle.ClassificationService")


class ClassificationService:
    """
    Servicio de clasificación de documentos usando LLM.
    Determina el tipo de documento (factura, recibo, contrato, etc.)
    """

    def __init__(self, llm_service: LLMService, model_manager: ModelManager):
        self.llm_service = llm_service
        self.model_manager = model_manager
        logger.info("ClassificationService inicializado")

    def classify(self, text: str) -> Dict[str, Any]:
        """
        Clasifica un documento basado en su contenido textual.
        """
        if not text or len(text.strip()) < 50:
            logger.warning("Texto demasiado corto para clasificación confiable")
            return {
                "document_type": "other",
                "confidence": 0.5
            }

        # ✅ USO DEL MODEL MANAGER: Nunca hardcodear "llama3.2:3b" aquí
        model = self.model_manager.get_model("classification")

        system_prompt = """Eres un experto en clasificación de documentos. 
Tu tarea es analizar el texto de un documento y determinar su tipo.

Tipos posibles:
- invoice: Factura comercial
- receipt: Recibo o ticket
- contract: Contrato o acuerdo legal
- manual: Manual de usuario o técnico
- report: Informe o reporte
- other: Otro tipo de documento

Responde SOLO con un JSON válido en este formato exacto:
{
  "document_type": "tipo_documento",
  "confidence": 0.95
}

Donde confidence es un número entre 0.0 y 1.0 que indica tu nivel de certeza."""

        user_prompt = f"""Analiza el siguiente texto y clasifícalo:

---
{text[:3000]}
---

Responde con el JSON de clasificación:"""

        try:
            logger.info(f"Clasificando documento con modelo: {model}")

            response = self.llm_service.generate(
                model=model,
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.3,
                max_tokens=200
            )

            result = self._parse_classification_response(response)

            logger.info(f"Documento clasificado como: {result['document_type']} (confianza: {result['confidence']})")
            return result

        except Exception as e:
            logger.error(f"Error en clasificación: {e}")
            return {
                "document_type": "other",
                "confidence": 0.0,
                "error": str(e)
            }

    def _parse_classification_response(self, response: str) -> Dict[str, Any]:
        """Parsea la respuesta del LLM para extraer el JSON de clasificación."""
        try:
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)

                document_type = data.get("document_type", "other")
                confidence = float(data.get("confidence", 0.5))

                valid_types = ["invoice", "receipt", "contract", "manual", "report", "other"]
                if document_type not in valid_types:
                    document_type = "other"

                confidence = max(0.0, min(1.0, confidence))

                return {
                    "document_type": document_type,
                    "confidence": confidence
                }
            else:
                logger.warning("No se encontró JSON en la respuesta del LLM")
                return {"document_type": "other", "confidence": 0.0}
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parseando respuesta de clasificación: {e}")
            return {"document_type": "other", "confidence": 0.0, "parse_error": str(e)}