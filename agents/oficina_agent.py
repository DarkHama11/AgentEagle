# -*- coding: utf-8 -*-
# src/agents/oficina_agent.py
"""AgentEagle - Agente especializado en Microsoft Office."""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

from .base_agent import BaseAgent, AgentResponse
from src.core.config import Config

logger = logging.getLogger(__name__)


class OficinaAgent(BaseAgent):
    """📊 AgentEagle Office Specialist - Excel • Word • PowerPoint"""

    def __init__(self, model_key: str = "general"):
        super().__init__(model_key=model_key)
        self.name = "oficina"
        self.description = "Especialista en Microsoft Office: Excel, Word, PowerPoint, Outlook"
        self.trigger_keywords = [
            "excel", "word", "powerpoint", "outlook", "office", "microsoft office",
            "formula", "macro", "vba", "pivot", "tabla dinamica", "grafico",
            "documento", "presentacion", "correo", "plantilla", "formato"
        ]
        logger.info(f"📊 OficinaAgent inicializado (model: {self.config['ollama_model']})")

    def get_system_prompt(self) -> str:
        """Retorna el prompt de sistema para el agente de Office."""
        fecha = datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
        return f"""Eres AgentEagle 🦅, especialista en Microsoft Office.

📅 Hoy es {fecha}.

Tu expertise:
- 📊 Excel: Formulas, tablas dinamicas, macros VBA, graficos, Power Query
- 📝 Word: Formato avanzado, estilos, referencias, combinacion de correspondencia
- 📽️ PowerPoint: Diseño de presentaciones, animaciones, transiciones, master slides
- 📧 Outlook: Reglas, firmas, calendarios, integracion con Office 365
- 🔧 Office 365: SharePoint, Teams, OneDrive, automatizacion con Power Automate

Reglas importantes:
1. Para formulas de Excel: explicar sintaxis completa y dar ejemplos practicos
2. Para macros VBA: incluir codigo comentado y advertencias de seguridad
3. Para problemas de formato: dar pasos claros y verificables
4. Para integracion entre apps: explicar flujo de trabajo completo
5. Si la version de Office es relevante, preguntar o asumir version reciente

Formato de respuesta:
- Usar emojis relevantes para mejorar legibilidad
- Incluir ejemplos de codigo en bloques formateados para VBA/formulas
- Estructurar pasos numerados para procedimientos
- Indicar atajos de teclado cuando aplique (Ctrl+Shift+...)

Si no estas seguro de una funcion especifica, ser honesto y sugerir documentacion oficial de Microsoft.
"""

    def _detect_intent(self, user_input: str) -> str:
        """Detecta la intencion de la consulta de Office."""
        t = user_input.lower()

        # Excel specific
        if any(kw in t for kw in ["excel", "formula", "vba", "macro", "pivot", "tabla dinamica"]):
            if any(kw in t for kw in ["formula", "funcion", "calcular"]):
                return "excel_formula"
            elif any(kw in t for kw in ["macro", "vba", "automatizar"]):
                return "excel_vba"
            elif any(kw in t for kw in ["pivot", "tabla dinamica", "resumen"]):
                return "excel_pivot"
            return "excel_general"

        # Word specific
        if any(kw in t for kw in ["word", "documento", "formato", "estilo", "referencia"]):
            return "word_general"

        # PowerPoint specific
        if any(kw in t for kw in ["powerpoint", "presentacion", "diapositiva", "slide"]):
            return "powerpoint_general"

        # Outlook specific
        if any(kw in t for kw in ["outlook", "correo", "email", "calendario", "reunion"]):
            return "outlook_general"

        # Office 365 / Integration
        if any(kw in t for kw in ["office 365", "sharepoint", "teams", "onedrive", "power automate"]):
            return "office365_integration"

        return "office_question"

    async def process(self, user_input: str, conversation_history: Optional[List[Dict]] = None, options: Optional[Dict[str, Any]] = None, context: Optional[Dict] = None) -> AgentResponse:
        """Procesa la consulta de Office y retorna respuesta."""
        intent = self._detect_intent(user_input)
        logger.info(f"📊 [OFICINA] [INTENT: {intent}] '{user_input[:50]}...'")

        # Respuestas rapidas para intents comunes
        if intent == "excel_formula":
            # Detectar si pide una formula especifica
            if "vlookup" in user_input.lower() or "buscarv" in user_input.lower():
                return AgentResponse(
                    agent=self.name, intent=intent,
                    response=self._get_excel_vlookup_help(),
                    tokens_used=0, execution_time_ms=0, metadata={"fast_response": True})
            elif "if" in user_input.lower() or "si(" in user_input.lower():
                return AgentResponse(
                    agent=self.name, intent=intent,
                    response=self._get_excel_if_help(),
                    tokens_used=0, execution_time_ms=0, metadata={"fast_response": True})

        # Construir prompt para LLM
        system_prompt = self.get_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history[-10:])

        messages.append({"role": "user", "content": user_input})
        full_prompt = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in messages)

        try:
            # Generar respuesta del modelo
            respuesta_cruda = self.model.generate(prompt=full_prompt, options=options)

            if isinstance(respuesta_cruda, dict):
                texto = respuesta_cruda.get("response", str(respuesta_cruda))
            else:
                texto = str(respuesta_cruda)

            # Limpiar prefijos del modelo
            texto = re.sub(r'^(Asistente|Respuesta|AgentEagle|Assistant):\s*', '', texto.strip(), flags=re.I)

            return AgentResponse(
                agent=self.name, intent=intent, response=texto,
                tokens_used=len(texto) // 4,
                execution_time_ms=0,
                metadata={"model": self.config["ollama_model"], "intent_confidence": 0.9})

        except Exception as e:
            logger.error(f"❌ Error en OficinaAgent: {e}")
            return AgentResponse(
                agent=self.name, intent=intent,
                response=self._get_fallback_response(user_input, intent, str(e)),
                tokens_used=0, execution_time_ms=0,
                metadata={"error": str(e)[:100], "fallback": True})

    def _get_excel_vlookup_help(self) -> str:
        """Ayuda rapida para VLOOKUP/BUSCARV."""
        return """📊 **Fórmula VLOOKUP / BUSCARV en Excel**"""
