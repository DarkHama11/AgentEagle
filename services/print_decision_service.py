import json
import re
import logging
from typing import Dict, Any, Optional

from services.llm_service import LLMService
from services.model_manager import ModelManager
from services.print_rules_service import PrintRulesService

logger = logging.getLogger("AgentEagle.PrintDecisionService")


class PrintDecisionService:
    """
    Servicio que usa IA para decidir la estrategia de impresión.
    Combina reglas estáticas con análisis inteligente del documento.
    """

    def __init__(self, llm_service: LLMService, model_manager: ModelManager):
        self.llm_service = llm_service
        self.model_manager = model_manager
        self.rules_service = PrintRulesService()
        logger.info("PrintDecisionService inicializado")

    def decide(
            self,
            document_type: str,
            confidence: float,
            fields: Dict[str, Any],
            raw_text: str,
            file_name: str
    ) -> Dict[str, Any]:
        """
        Decide la estrategia de impresión para un documento.

        :return: Dict con should_print, copies, requires_approval,
                 printer_group, priority, reason
        """
        # Obtener regla base estática
        base_rule = self.rules_service.get_rule(document_type)

        # Si IA está deshabilitada, usar regla estática directamente
        if not self.rules_service.should_use_ai():
            logger.info(f"IA deshabilitada. Usando regla estática para: {document_type}")
            return self._build_decision(base_rule, document_type, fields)

        # Intentar decisión con IA
        try:
            ai_decision = self._ask_llm(document_type, confidence, fields, raw_text, file_name)

            # Validar y completar con regla base
            decision = self._merge_decisions(base_rule, ai_decision, document_type, fields)
            logger.info(f"Decisión IA para {document_type}: {decision}")
            return decision

        except Exception as e:
            logger.error(f"Error en decisión IA: {e}", exc_info=True)

            # Fallback a regla estática
            if self.rules_service.fallback_to_rules():
                logger.warning("Usando regla estática como fallback")
                return self._build_decision(base_rule, document_type, fields)

            # Si no hay fallback, retornar decisión conservadora
            return {
                "should_print": False,
                "copies": 0,
                "requires_approval": True,
                "printer_group": "general",
                "priority": "low",
                "reason": f"Error en IA: {str(e)}. Requiere revisión manual.",
                "decision_source": "error"
            }

    def _ask_llm(
            self,
            document_type: str,
            confidence: float,
            fields: Dict[str, Any],
            raw_text: str,
            file_name: str
    ) -> Dict[str, Any]:
        """Consulta al LLM para decidir estrategia de impresión."""

        # Obtener modelo desde ModelManager
        try:
            model = self.model_manager.get_model("print_decision")
        except KeyError:
            model = self.model_manager.get_model("default")

        ai_settings = self.rules_service.get_ai_settings()

        system_prompt = """Eres un asistente experto en gestión documental y estrategias de impresión.
Tu tarea es analizar documentos y decidir si deben imprimirse, cuántas copias, en qué impresora, y si requieren aprobación humana.

Responde SOLO con un JSON válido en este formato exacto:
{
  "should_print": true/false,
  "copies": número,
  "requires_approval": true/false,
  "printer_group": "finance" | "legal" | "general",
  "priority": "high" | "normal" | "low",
  "reason": "explicación breve"
}

Criterios:
- Facturas/recibos → finance, 1 copia, sin aprobación
- Contratos → legal, 2 copias, requiere aprobación
- Manuales → no imprimir (son digitales)
- Reportes → general, 1 copia
- Documentos confidenciales o de alto valor → requiere aprobación
- Documentos duplicados o irrelevantes → no imprimir"""

        user_prompt = f"""Analiza este documento y decide la estrategia de impresión:

📄 Archivo: {file_name}
🏷️ Tipo detectado: {document_type}
🎯 Confianza: {confidence:.2%}

📦 Campos extraídos:
{json.dumps(fields, indent=2, ensure_ascii=False)}

📝 Texto (primeros 1000 caracteres):
{raw_text[:1000]}

Responde con el JSON de decisión:"""

        try:
            response = self.llm_service.generate(
                model=model,
                prompt=user_prompt,
                system=system_prompt,
                temperature=ai_settings.get('temperature', 0.2),
                max_tokens=ai_settings.get('max_tokens', 300)
            )

            return self._parse_llm_response(response)

        except Exception as e:
            logger.error(f"Error consultando LLM: {e}")
            raise

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parsea la respuesta del LLM extrayendo el JSON."""
        try:
            # Buscar JSON en la respuesta
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if not json_match:
                raise ValueError("No se encontró JSON en la respuesta")

            data = json.loads(json_match.group(0))

            # Validar campos requeridos
            required = ['should_print', 'copies', 'requires_approval', 'printer_group', 'priority', 'reason']
            for field in required:
                if field not in data:
                    data[field] = None

            # Validar y corregir valores
            data['should_print'] = bool(data.get('should_print', False))
            data['copies'] = max(0, int(data.get('copies', 1)))
            data['requires_approval'] = bool(data.get('requires_approval', False))

            valid_groups = ['finance', 'legal', 'general']
            if data.get('printer_group') not in valid_groups:
                data['printer_group'] = 'general'

            valid_priorities = ['high', 'normal', 'low']
            if data.get('priority') not in valid_priorities:
                data['priority'] = 'normal'

            data['reason'] = str(data.get('reason', ''))[:200]
            data['decision_source'] = 'ai'

            return data

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parseando respuesta LLM: {e}")
            raise

    def _merge_decisions(
            self,
            base_rule: Dict[str, Any],
            ai_decision: Dict[str, Any],
            document_type: str,
            fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Combina la decisión de IA con la regla base."""
        merged = ai_decision.copy()

        # Si la IA no decidió algo, usar regla base
        if merged.get('copies') is None:
            merged['copies'] = base_rule.get('copies', 1)
        if merged.get('printer_group') is None:
            merged['printer_group'] = base_rule.get('printer_group', 'general')
        if merged.get('priority') is None:
            merged['priority'] = base_rule.get('priority', 'normal')

        # Enriquecer reason con template si aplica
        reason_template = base_rule.get('reason_template', '')
        if reason_template and merged.get('reason'):
            try:
                # Reemplazar placeholders con valores de fields
                enriched = reason_template.format(**fields)
                merged['reason'] = f"{enriched}. {merged['reason']}"
            except (KeyError, IndexError):
                pass

        return merged

    def _build_decision(
            self,
            base_rule: Dict[str, Any],
            document_type: str,
            fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Construye una decisión desde la regla estática."""
        decision = {
            "should_print": base_rule.get('should_print', True),
            "copies": base_rule.get('copies', 1),
            "requires_approval": base_rule.get('requires_approval', False),
            "printer_group": base_rule.get('printer_group', 'general'),
            "priority": base_rule.get('priority', 'normal'),
            "reason": base_rule.get('reason_template', f"Documento tipo {document_type}"),
            "decision_source": "rules"
        }

        # Enriquecer reason
        reason_template = base_rule.get('reason_template', '')
        if reason_template:
            try:
                decision['reason'] = reason_template.format(**fields)
            except (KeyError, IndexError):
                pass

        return decision