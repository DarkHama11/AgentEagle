# -*- coding: utf-8 -*-
# src/agents/seguridad_agent.py
"""AgentEagle Cloud Security Specialist - Con sistema de Skills integrado."""
# -*- coding: utf-8 -*-
# src/agents/seguridad_agent.py
"""AgentEagle Cloud Security Specialist - Con sistema de Skills integrado."""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from .base_agent import BaseAgent, AgentResponse
from .skills.skill_registry import SkillRegistry
from src.core.config import Config
from tools.security_search import SecuritySearch, SearchCategory  # ✅ FIX: Import absoluto

logger = logging.getLogger(__name__)
# ... resto del archivo igual ...


class SeguridadAgent(BaseAgent):
    """🦅 AgentEagle Cloud Security Specialist - Con sistema de Skills integrado"""

    def __init__(self, model_key: str = "seguridad_experto", enable_web_search: bool = True,
                 enable_skills: bool = True):
        super().__init__(model_key=model_key)
        self.enable_web_search = enable_web_search
        self.enable_skills = enable_skills
        self.name = "seguridad"
        self.description = "Especialista en seguridad cloud: AWS, Azure, GCP, CVE, MITRE, compliance"
        self.trigger_keywords = [
            "aws", "azure", "gcp", "cloud", "security", "cve", "vulnerability",
            "mitre", "att&ck", "compliance", "cis", "nist", "iam", "s3", "ec2",
            "lambda", "cloudtrail", "guardduty", "kms", "vpc", "eks", "ecs"
        ]

        # Inicializar sistema de skills
        self.skill_registry = SkillRegistry() if enable_skills else None
        if self.skill_registry:
            self.skill_registry.register_all()
            logger.info(f"🔧 Skills inicializadas: {list(self.skill_registry.list_skills().keys())}")

        # Inicializar buscador de seguridad
        self.searcher = SecuritySearch(timeout=Config.SEARCH_TIMEOUT,
                                       cache_ttl_hours=Config.SEARCH_CACHE_TTL_HOURS) if enable_web_search else None

        logger.info(
            f"🦅 AgentEagle Cloud Security Specialist inicializado (web: {enable_web_search}, skills: {enable_skills})")

    def get_system_prompt(self) -> str:
        """Retorna el prompt de sistema para el agente de seguridad."""
        fecha = datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
        return f"""Eres AgentEagle 🦅, especialista en seguridad cloud.

📅 Hoy es {fecha}.

Tu expertise:
- ☁️ Plataformas cloud: AWS, Azure, GCP
- 🔐 Servicios de seguridad: IAM, KMS, CloudTrail, GuardDuty, Defender for Cloud, Security Command Center
- 🐛 Vulnerabilidades: CVE lookup, zero-days, exploit analysis
- 🎯 MITRE ATT&CK: Tecnicas, tacticas, mapeo a controles cloud
- 📋 Compliance: CIS Benchmarks, NIST 800-53, ISO 27001, PCI DSS

Reglas importantes:
1. Para CVEs: citar fuentes oficiales (NVD, MITRE, CISA) con ID completo
2. Para configuraciones cloud: recomendar principio de minimo privilegio
3. Para compliance: referenciar controles especificos del framework
4. Para zero-days: indicar nivel de confianza y fuentes verificadas
5. Si no hay informacion actualizada, ser honesto y sugerir donde buscar

Formato de respuesta:
- Usar emojis relevantes para mejorar legibilidad
- Incluir enlaces a documentacion oficial cuando sea posible
- Estructurar respuestas tecnicas con bullets claros
- Indicar fecha de la informacion si es relevante

Si la consulta requiere busqueda web actualizada, usar el sistema de SecuritySearch integrado.
Si requiere ejecucion de comandos o verificacion de configuraciones, usar las skills disponibles.
"""

    def _detect_intent(self, user_input: str) -> str:
        """Detecta la intencion de la consulta de seguridad."""
        t = user_input.lower()

        # CVE lookup
        if re.search(r'cve-\d{4}-\d+', t, re.I):
            return "cve_lookup"

        # MITRE ATT&CK
        if re.search(r'[tT]\d{4}(\.\d{3})?', t) or "mitre" in t or "att&ck" in t:
            return "mitre_mapping"

        # Cloud provider specific
        if any(kw in t for kw in ["aws", "amazon web services"]):
            if any(kw in t for kw in ["s3", "ec2", "iam", "lambda", "cloudtrail", "guardduty"]):
                return "aws_service"
            return "aws_general"
        elif any(kw in t for kw in ["azure", "microsoft azure", "entra"]):
            return "azure_general"
        elif any(kw in t for kw in ["gcp", "google cloud"]):
            return "gcp_general"

        # Compliance
        if any(kw in t for kw in ["cis", "nist", "iso", "pci", "hipaa", "gdpr", "compliance"]):
            return "compliance"

        # Vulnerability general
        if any(kw in t for kw in ["vulnerability", "exploit", "zero-day", "0-day", "patch"]):
            return "vulnerability"

        # Security best practices
        if any(kw in t for kw in ["best practice", "mejor practica", "recomendacion", "hardening"]):
            return "best_practices"

        return "security_question"

    async def process(self, user_input: str, conversation_history: Optional[List[Dict]] = None, options: Optional[Dict[str, Any]] = None, context: Optional[Dict] = None) -> AgentResponse:
        """Procesa la consulta de seguridad y retorna respuesta."""
        intent = self._detect_intent(user_input)
        logger.info(f"🦅 [INTENT: {intent}] '{user_input[:50]}...'")

        # Extraer entidades relevantes
        entities = self.extract_entities(user_input)

        # Intentar usar skill si esta disponible y es relevante
        if self.enable_skills and self.skill_registry:
            skill_response = await self._try_skill_execution(user_input, intent, entities)
            if skill_response:
                return skill_response

        # Buscar contexto web si es relevante y esta habilitado
        web_context = None
        if self.enable_web_search and self.searcher:
            should_search, search_query, category = self.searcher.should_trigger_security_search(user_input)
            if should_search:
                logger.debug(f"🔍 Triggering security search: {search_query} [{category}]")
                try:
                    search_result = self.searcher.search(query=search_query, num_results=3, category=category)
                    if search_result.results:
                        web_context = self.searcher.format_for_llm(search_result, max_results=2)
                        logger.debug(f"📦 Web context retrieved: {len(search_result.results)} results")
                except Exception as e:
                    logger.warning(f"⚠️ Search error: {e}")

        # Construir prompt para LLM
        system_prompt = self.get_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]

        # Agregar contexto web si existe
        if web_context:
            messages.append({"role": "system", "content": f"🔍 Informacion web actualizada:\n{web_context}"})

        # Agregar historial de conversacion
        if conversation_history:
            messages.extend(conversation_history[-10:])

        # Agregar consulta del usuario con entidades extraidas
        user_msg = user_input
        if entities:
            entity_str = ", ".join(f"{k}: {v}" for k, v in entities.items() if v)
            user_msg += f"\n\n[Entidades detectadas: {entity_str}]"

        messages.append({"role": "user", "content": user_msg})
        full_prompt = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in messages)

        try:
            # Generar respuesta del modelo
            respuesta_cruda = self.model.generate(prompt=full_prompt, options=options)

            # Procesar respuesta
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
                metadata={
                    "model": self.config["ollama_model"],
                    "intent_confidence": 0.9,
                    "entities": entities,
                    "web_search_used": web_context is not None,
                    "skills_used": self.skill_registry is not None
                })

        except Exception as e:
            logger.error(f"❌ Error en SeguridadAgent: {e}")
            return AgentResponse(
                agent=self.name, intent=intent,
                response=self._get_fallback_response(user_input, intent, str(e)),
                tokens_used=0, execution_time_ms=0,
                metadata={"error": str(e)[:100], "fallback": True})

    async def _try_skill_execution(self, user_input: str, intent: str, entities: Dict) -> Optional[AgentResponse]:
        """Intenta ejecutar una skill relevante para la consulta."""
        if not self.skill_registry:
            return None

        # Mapear intent a skill
        skill_map = {
            "cve_lookup": "cve_lookup",
            "mitre_mapping": "mitre_mapping",
            "aws_service": "aws_cli",
            "aws_general": "aws_cli",
            "compliance": "compliance_check",
        }

        skill_name = skill_map.get(intent)
        if not skill_name or not self.skill_registry.has_skill(skill_name):
            return None

        try:
            skill = self.skill_registry.get_skill(skill_name)
            result = await skill.execute(user_input, context={"entities": entities})

            if result.get("success"):
                return AgentResponse(
                    agent=self.name, intent=f"{intent}_via_skill",
                    response=result.get("output", "✅ Operacion completada"),
                    tokens_used=0, execution_time_ms=result.get("execution_time_ms", 0),
                    metadata={"skill": skill_name, "skill_result": result})
        except Exception as e:
            logger.warning(f"⚠️ Skill {skill_name} error: {e}")

        return None

    def _get_fallback_response(self, user_input: str, intent: str, error: Optional[str] = None) -> str:
        """Respuestas de fallback para agente de seguridad."""
        fallbacks = {
            "cve_lookup": f"🐛 No pude encontrar informacion actualizada para ese CVE. Te recomiendo verificar directamente en: https://nvd.nist.gov o https://cve.mitre.org",
            "mitre_mapping": f"🎯 Para tecnicas MITRE ATT&CK, consulta: https://attack.mitre.org - ¿Hay alguna tecnica especifica en la que pueda ayudarte?",
            "aws_service": f"☁️ Para documentacion oficial de AWS, visita: https://docs.aws.amazon.com - ¿Que servicio especifico te interesa?",
            "compliance": f"📋 Para frameworks de compliance, revisa: CIS (https://cisecurity.org) o NIST (https://csrc.nist.gov) - ¿Que framework necesitas?",
        }

        base = fallbacks.get(intent,
                             f"🦅 Estoy procesando tu consulta de seguridad. Mientras tanto, ¿hay algo mas en lo que pueda ayudarte?")

        if error:
            return f"{base}\n\n⚠️ Nota: Ocurrio un error tecnico: {error[:150]}..."

        return base

    def get_available_skills(self) -> List[str]:
        """Retorna lista de skills disponibles."""
        if not self.skill_registry:
            return []
        return list(self.skill_registry.list_skills().keys())