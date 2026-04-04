# src/agents/seguridad_agent.py
"""AgentEagle++ Cloud Security Specialist - Con sistema de Skills integrado."""
from .base_agent import BaseAgent
from typing import Dict, Any, Optional
import logging
import re
import json
from datetime import datetime

# ✅ PRIMERO: Inicializar logger
logger = logging.getLogger(__name__)


# ✅ FUNCIÓN GLOBAL DEFINIDA ANTES DE LA CLASE
def _get_fecha_espanol() -> str:
    """Obtiene fecha en español sin depender de locale del sistema."""
    now = datetime.now()
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre"]
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return f"{dias[now.weekday()]}, {now.day} de {meses[now.month - 1]} de {now.year}, {now.strftime('%H:%M')}"


# ✅ Imports de servicios AWS
try:
    from src.core.aws_services import AWS_SERVICES, ALL_AWS_SERVICE_NAMES, is_aws_service_query

    AWS_SERVICES_AVAILABLE = True
except ImportError:
    AWS_SERVICES_AVAILABLE = False
    logger.warning("⚠️ aws_services.py no disponible")

# ✅ Imports de búsqueda web
try:
    from tools.security_search import SecuritySearch

    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False
    logger.warning("⚠️ SecuritySearch no disponible")

# ✅ Imports de Skills
try:
    from .skills.skill_registry import SkillRegistry
    from .skills.base_skill import SkillExecutionError

    SKILLS_AVAILABLE = True
except ImportError:
    SKILLS_AVAILABLE = False
    logger.warning("⚠️ Skills no disponibles")


class SeguridadAgent(BaseAgent):
    """🦞 AgentEagle Cloud Security Specialist - Con sistema de Skills integrado"""

    MODEL_CONFIGS = {
        "3b": {"name": "llama3.2:3b", "temp": 0.2, "max_tokens": 384},
        "7b": {"name": "deepseek-r1:7b", "temp": 0.15, "max_tokens": 384},
    }

    CONVERSATIONAL_RESPONSES = {
        "greeting": [
            "👋 ¡Hola! Soy tu especialista en seguridad cloud 🦞 ¿IAM, S3, EC2, Lambda o cualquier servicio AWS? ¡Estoy listo para ayudar! 🛡️",
            "🦞 ¡Hola! Seguridad cloud es mi especialidad: 200+ servicios de AWS, Azure, GCP. ¿Qué necesitas?",
            "👋 ¡Bienvenido! ¿IAM, S3, EC2, Lambda, CloudTrail, GuardDuty, KMS? ¡Cualquier servicio AWS! Estoy listo para ayudar 🛡️",
        ],
        "goodbye": [
            "👋 ¡Hasta pronto! Recuerda: seguridad primero 🔐 Vuelve cuando necesites ayuda con AWS, Azure o GCP.",
            "🦞 ¡Nos vemos! Mantén tus clouds seguros 🛡️ Aquí estaré si necesitas algo.",
        ],
        "thanks": [
            "😊 ¡Me alegra ayudar con seguridad cloud! ¿Algo más? 🦞",
            "🙌 ¡De nada! La seguridad cloud es mi pasión 🛡️ ¿Más dudas? ¡Pregunta sin miedo!",
        ],
        "date": lambda: f"📅 Hoy es {_get_fecha_espanol()}. ¿Qué necesitas en seguridad cloud? 🦞",
        "out_of_scope": [
            "🦞 ¡Hola! Me especializo en seguridad de servicios cloud (AWS/Azure/GCP) 🛡️ Para otros temas, te recomiendo otro asistente. Pero si es sobre IAM, S3, EC2, Lambda, CloudTrail... ¡ahí sí soy tu experto! ¿En qué puedo ayudarte?",
        ],
    }

    def __init__(self, model_key: str = "3b", enable_web_search: bool = True, enable_skills: bool = True):
        super().__init__("seguridad", model_key)
        self.config = self.MODEL_CONFIGS.get(model_key, self.MODEL_CONFIGS["3b"])

        # === PRIMERO: Definir todas las variables que usa _build_system_prompt() ===
        self.enable_web_search = enable_web_search and SEARCH_AVAILABLE
        self.enable_skills = enable_skills and SKILLS_AVAILABLE
        self.searcher = SecuritySearch(timeout=10) if self.enable_web_search else None

        # === Inicializar registro de skills ===
        if self.enable_skills:
            self.skill_registry = SkillRegistry(config={
                "aws_cli": {"enabled": True, "default_region": "us-east-1", "timeout": 30},
                "cve_lookup": {"enabled": True, "timeout": 15},
                "compliance_check": {"enabled": True, "timeout": 15},
            })
            logger.info(f"🔧 Skills inicializadas: {list(self.skill_registry._skill_classes.keys())}")
        else:
            self.skill_registry = None
            logger.info("⚠️ Skills deshabilitadas")

        # === AHORA sí construir el system prompt (ya tiene todas las variables) ===
        self.system_prompt = self._build_system_prompt()

        logger.info(
            f"🦞 AgentEagle Cloud Security Specialist inicializado (web: {self.enable_web_search}, skills: {self.enable_skills})")

    def _build_system_prompt(self) -> str:
        """Construye el system prompt con fecha actual y ejemplos de skills."""
        fecha = _get_fecha_espanol()

        # === Variable para ejemplo JSON (evita problemas con f-strings) ===
        skills_json_example = '{"skill": "nombre_skill", "params": {"param1": "value1"}}'

        # === Lista de skills disponibles para incluir en el prompt ===
        skills_section = ""
        if self.enable_skills and self.skill_registry:
            skills_prompt = self.skill_registry.get_llm_tools_prompt()
            skills_section = "\n\n" + skills_prompt + "\n"

        # ✅ CONSTRUIR EL PROMPT EN PARTES (más seguro que un f-string gigante)
        prompt_parts = []

        # Parte 1: Fecha y personalidad
        prompt_parts.append("📅 Hoy es " + fecha + ". Eres AgentEagle 🦅, experto en seguridad cloud.")
        prompt_parts.append("")
        prompt_parts.append("🎯 TU PERSONALIDAD:")
        prompt_parts.append("• Amigable, claro, con emojis 🦞🛡️☁️")
        prompt_parts.append("• Práctico: da pasos accionables, no solo teoría")
        prompt_parts.append("• Preciso: cita fuentes oficiales cuando sea relevante")
        prompt_parts.append("")

        # Parte 2: Expertise
        prompt_parts.append("☁️ TU EXPERTISE:")
        prompt_parts.append("• AWS: IAM, S3, EC2, Lambda, CloudTrail, GuardDuty, KMS, VPC, EKS, ECS, ECR")
        prompt_parts.append("• Azure: Entra ID, Key Vault, Defender for Cloud, Sentinel")
        prompt_parts.append("• GCP: IAM, Cloud KMS, Security Command Center")
        prompt_parts.append("• Cross-cloud: Encriptación, compliance, identidad, monitoreo")
        prompt_parts.append("")

        # Parte 3: Enfoque de seguridad
        prompt_parts.append("🔐 ENFOQUE DE SEGURIDAD:")
        prompt_parts.append("• IAM: mínimo privilegio, MFA, roles temporales")
        prompt_parts.append("• Encriptación: at-rest (KMS), in-transit (TLS)")
        prompt_parts.append("• Logging: CloudTrail, CloudWatch, GuardDuty")
        prompt_parts.append("• Compliance: CIS Benchmarks, NIST, ISO 27001")
        prompt_parts.append("• Network: Security Groups, NACLs, WAF, Shield")
        prompt_parts.append("")

        # Parte 4: Formato para CVEs
        prompt_parts.append("📋 FORMATO PARA CVEs:")
        prompt_parts.append("• Título: 🔐 **CVE-XXXX-NNNNN** - [breve descripción]")
        prompt_parts.append("• CVSS: • 📊 CVSS: X.X ([Severidad])")
        prompt_parts.append("• Afecta: • 🎯 Servicios afectados: [lista]")
        prompt_parts.append("• Mitigación: • 🔧 Mitigación: [pasos concretos]")
        prompt_parts.append("• Fuentes: • 📚 Fuentes: cve.mitre.org, nvd.nist.gov, aws.amazon.com/security")
        prompt_parts.append("")

        # Parte 5: Skills disponibles
        prompt_parts.append("🔧 SKILLS DISPONIBLES:")
        prompt_parts.append(
            "Puedes ejecutar acciones reales usando skills. Para usar una skill, responde con formato JSON:")
        prompt_parts.append("```json")
        prompt_parts.append(skills_json_example)
        prompt_parts.append("```")
        prompt_parts.append("")
        prompt_parts.append(skills_section)
        prompt_parts.append("")

        # Parte 6: Lo que nunca sugerir
        prompt_parts.append("🚫 NUNCA SUGIERAS:")
        prompt_parts.append("• Hardcode de credentials o access keys")
        prompt_parts.append("• Políticas IAM con wildcard (*) sin justificación")
        prompt_parts.append("• Security groups con 0.0.0.0/0 en producción")
        prompt_parts.append("")

        # Parte 7: Ejemplos precisos
        prompt_parts.append("💬 EJEMPLOS PRECISOS:")
        prompt_parts.append("")
        prompt_parts.append('Usuario: "¿Cuáles son los últimos CVE de AWS?"')
        prompt_parts.append('Asistente: "🔐 **CVEs Recientes Relacionados con AWS** 🦞')
        prompt_parts.append(
            "• CVE-2026-XXXX: Vulnerabilidad en [servicio] - 📊 CVSS: 7.5 (Alto) - 🎯 Afecta: EC2, Lambda - 🔧 Mitigación: Actualizar agente de SSM, revisar políticas IAM")
        prompt_parts.append(
            "• CVE-2026-YYYY: [otra vulnerabilidad] - 📊 CVSS: 5.3 (Medio) - 🎯 Afecta: S3 - 🔧 Mitigación: Habilitar Bucket Policy de encriptación")
        prompt_parts.append("📚 Para información en tiempo real:")
        prompt_parts.append("• https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=aws")
        prompt_parts.append("• https://aws.amazon.com/security/security-bulletins/")
        prompt_parts.append("• https://nvd.nist.gov/vuln/search/results?keyword=aws")
        prompt_parts.append('💡 ¿Necesitas ayuda para evaluar o mitigar un CVE específico en tu entorno?"')
        prompt_parts.append("")
        prompt_parts.append('Usuario: "¿Cómo proteger un bucket S3?"')
        prompt_parts.append('Asistente: "🔐 **Protección de S3 en AWS** 🦞:')
        prompt_parts.append("1. ✅ Block Public Access: a nivel de bucket Y cuenta")
        prompt_parts.append("2. 🔐 Encriptación: SSE-S3 (default) o SSE-KMS (control de claves)")
        prompt_parts.append('3. 📋 Bucket Policy: mínimo privilegio, evita Principal:"*"')
        prompt_parts.append("4. 📊 Logging: CloudTrail + S3 Access Logs habilitados")
        prompt_parts.append("5. 🔄 Versioning + MFA Delete: para recuperación ante ransomware")
        prompt_parts.append("6. 🔍 Macie: para detectar datos sensibles almacenados")
        prompt_parts.append("⚠️ Evita: ACLs heredadas, wildcard en policies, acceso público accidental")
        prompt_parts.append(
            "📚 Docs oficiales: https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html")
        prompt_parts.append('💡 ¿Necesitas ayuda con un caso específico de S3?"')
        prompt_parts.append("")
        prompt_parts.append('Usuario: "¿Puedes listar mis buckets S3?"')
        prompt_parts.append('Asistente: "🔧 Ejecutando skill aws_cli...')
        prompt_parts.append("```json")
        prompt_parts.append(skills_json_example)
        prompt_parts.append("```")
        prompt_parts.append("✅ **Tus buckets S3**:")
        prompt_parts.append("• mi-bucket-prod (us-east-1)")
        prompt_parts.append("• backups-diarios (us-west-2)")
        prompt_parts.append("🔐 Tips: Verifica que 'Block Public Access' esté habilitado en cada bucket.\"")
        prompt_parts.append("")
        prompt_parts.append('Usuario: "¿Qué es la técnica T1059 de MITRE?"')
        prompt_parts.append('Asistente: "🎯 **T1059: Command and Scripting Interpreter** 🦞')
        prompt_parts.append("• 📝 Descripción: Ejecución de comandos via PowerShell, Bash, Python, etc.")
        prompt_parts.append("• 🎯 Táctica asociada: Execution (TA0002)")
        prompt_parts.append("• 🔍 Detección:")
        prompt_parts.append("  - Logging de comandos (CloudTrail, OS logs)")
        prompt_parts.append("  - EDR/XDR para detectar scripts sospechosos")
        prompt_parts.append("  - Anomalías en patrones de ejecución")
        prompt_parts.append("• 🛡️ Mitigación:")
        prompt_parts.append("  - Restrict execution policies (AppLocker, WDAC)")
        prompt_parts.append("  - Application whitelisting")
        prompt_parts.append("  - Logging centralizado y monitoreo")
        prompt_parts.append("• 📚 Fuente oficial: https://attack.mitre.org/techniques/T1059/")
        prompt_parts.append('💡 ¿Necesitas ayuda para detectar o mitigar T1059 en tu entorno cloud?"')
        prompt_parts.append("")
        prompt_parts.append("Ahora responde como AgentEagle 🦅, con precisión y utilidad:")
        prompt_parts.append("")
        prompt_parts.append("Usuario: ")

        # ✅ Unir todas las partes con saltos de línea
        return "\n".join(prompt_parts)

    def _format_prompt(self, user_input: str, context: Optional[Dict] = None, web_context: Optional[str] = None) -> str:
        """Construye el prompt final con historial limitado y web context opcional."""
        history = context.get("history", []) if context else []

        # === Limitar historial a últimas 2 interacciones ===
        recent = history[-2:] if len(history) > 2 else history

        history_text = ""
        if recent:
            history_lines = []
            for m in recent:
                role = "Usuario" if m.get("role") == "user" else "Asistente"
                content = m.get("content", "")
                # Truncar mensajes muy largos
                if len(content) > 200:
                    content = content[:197] + "..."
                history_lines.append(role + ": " + content)
            history_text = "\n".join(history_lines) + "\n\n"

        web_section = ""
        if web_context:
            web_section = "\n🌐 **Información actualizada**:\n" + web_context + "\n"

        parts = [self.system_prompt, history_text, web_section, "Usuario: " + user_input + "\nAsistente:"]
        return "\n".join(p for p in parts if p)

    def _clean_response(self, text: str) -> str:
        """Limpia la respuesta del modelo manteniendo formato legible."""
        if not text:
            return ""
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'^(Asistente|Respuesta|AgentEagle|Assistant):\s*', '', text.strip(), flags=re.I)
        return text.strip()

    def _get_conversational_response(self, intent: str, user_input: str = "") -> str:
        """Respuestas conversacionales con personalidad AgentEagle."""
        import random
        out_of_scope_keywords = ["fútbol", "barcelona", "real madrid", "cocina", "receta", "música", "película"]
        if any(k in user_input.lower() for k in out_of_scope_keywords) and intent not in ["greeting", "goodbye",
                                                                                          "thanks", "date"]:
            return random.choice(self.CONVERSATIONAL_RESPONSES["out_of_scope"])
        if intent == "date" and callable(self.CONVERSATIONAL_RESPONSES.get("date")):
            return self.CONVERSATIONAL_RESPONSES["date"]()
        if intent in self.CONVERSATIONAL_RESPONSES and not callable(self.CONVERSATIONAL_RESPONSES[intent]):
            return random.choice(self.CONVERSATIONAL_RESPONSES[intent])
        return "🦞 Hoy es " + _get_fecha_espanol() + ". ¿Qué necesitas en seguridad cloud? 🛡️"

    def _is_cloud_security_question(self, user_input: str) -> bool:
        """Detecta si la pregunta es sobre cloud security incluyendo todos los servicios AWS."""
        t = user_input.lower()

        # === Primero verificar si menciona un servicio AWS ===
        if AWS_SERVICES_AVAILABLE:
            is_aws, service_name, category = is_aws_service_query(user_input)
            if is_aws:
                return True

        # === Keywords de cloud providers ===
        cloud_keywords = ["aws", "azure", "gcp", "google cloud", "amazon web services", "cloud", "nube"]

        # === Keywords de seguridad cloud EXPANDIDO ===
        security_keywords = [
            "iam", "s3", "ec2", "lambda", "bucket", "encript", "kms", "cloudtrail", "guardduty",
            "sentinel", "defender", "vpc", "security group", "rbac", "mfa", "compliance", "cis",
            "nist", "cve", "vulnerabilidad", "mitre", "att&ck", "policy", "role", "permission",
            "cloudwatch", "config", "waf", "shield", "secrets", "inspector", "security hub",
            "eks", "ecs", "ecr", "kubernetes", "k8s", "container", "fargate"
        ]

        has_cloud = any(k in t for k in cloud_keywords)
        has_security = any(k in t for k in security_keywords)

        return (has_cloud and has_security) or has_security

    def _detect_and_execute_skill(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        Detecta si el usuario quiere usar un skill y lo ejecuta.

        Returns:
            Dict con resultado del skill, o None si no se detectó skill.
        """
        if not self.enable_skills or not self.skill_registry:
            return None

        # === Patrón para detectar llamadas a skills ===
        json_match = re.search(r'\{[^{}]*"skill"[^{}]*\}', user_input, re.DOTALL)
        if not json_match:
            return None

        try:
            skill_call = json.loads(json_match.group())
            skill_name = skill_call.get("skill")
            params = skill_call.get("params", {})

            if not skill_name:
                return None

            logger.info("🔧 Skill detectado: " + skill_name + " con params: " + str(params))

            # Obtener y ejecutar skill
            skill = self.skill_registry.get_skill(skill_name)
            if not skill:
                return {
                    "success": False,
                    "error": "Skill '" + skill_name + "' no encontrado. Disponibles: " + str(
                        list(self.skill_registry._skill_classes.keys())),
                    "skill_execution": True,
                }

            # Ejecutar skill (async)
            import asyncio
            result = asyncio.run(skill.execute(params))
            result["skill_execution"] = True
            result["skill_name"] = skill_name
            return result

        except json.JSONDecodeError:
            logger.warning("⚠️ JSON mal formado en input de skill: " + user_input[:100])
            return None
        except SkillExecutionError as e:
            logger.error("❌ Error ejecutando skill: " + str(e))
            return {"success": False, "error": str(e), "skill_execution": True}
        except Exception as e:
            logger.error("❌ Error inesperado en skill execution: " + str(e))
            return {"success": False, "error": "Error ejecutando skill: " + str(e)[:200], "skill_execution": True}

    def _get_security_web_context(self, user_input: str) -> tuple:
        """Ejecuta búsqueda web especializada para cloud security con queries optimizados."""
        if not self.enable_web_search or not self.searcher:
            return None, 0, None

        should_search, search_query, category = self.searcher.should_trigger_security_search(user_input)

        if should_search:
            logger.info("🦞 Búsqueda cloud security activada [" + category + "]: '" + search_query[:60] + "...'")
            try:
                if category == "cve" and re.search(r'CVE-\d{4}-\d+', search_query, re.I):
                    cve_match = re.search(r'CVE-\d{4}-\d+', search_query, re.I)
                    results = self.searcher.buscar_cve(cve_match.group()) if cve_match else []
                elif category == "cve_recent":
                    severity = "critical" if any(s in search_query for s in ["critical", "critica", "high"]) else ""
                    results = self.searcher.buscar_cve_recientes(limit=5, severity=severity)
                elif category == "mitre":
                    technique_match = re.search(r'[Tt]\d{4}(\.\d{3})?', search_query)
                    results = self.searcher.buscar_mitre_technique(technique_match.group()) if technique_match else []
                elif category in ["aws", "azure", "gcp"]:
                    if AWS_SERVICES_AVAILABLE:
                        is_aws, service_name, svc_category = is_aws_service_query(user_input)
                        if is_aws and category == "aws":
                            t = user_input.lower()
                            if any(k in t for k in ["que es", "qué es", "what is"]):
                                search_query = "AWS " + service_name + " service documentation overview"
                            elif any(k in t for k in ["seguridad", "proteger", "asegurar", "best practices"]):
                                search_query = "AWS " + service_name + " security best practices"
                            else:
                                search_query = "AWS " + service_name + " documentation"
                            logger.info("🦞 Query optimizado para " + service_name + ": '" + search_query + "'")
                            results = self.searcher.buscar_aws_security(service_name)
                        else:
                            results = self.searcher.search_safe(search_query, num_results=4)
                    else:
                        results = self.searcher.search_safe(search_query, num_results=4)
                elif category and category.startswith("compliance_"):
                    framework = category.replace("compliance_", "")
                    results = self.searcher.buscar_compliance_framework(framework)
                elif category == "zero_day":
                    results = self.searcher.buscar_zero_day()
                else:
                    results = self.searcher.search_safe(search_query, num_results=4)

                if results and 'error' not in results[0]:
                    web_context = self.searcher.format_results_for_llm(results[:4])
                    return web_context, len(results), category
                return None, 0, category
            except Exception as e:
                logger.warning("⚠️ Búsqueda cloud security falló: " + str(e))
                return None, 0, category

        # === Fallback: Si es pregunta sobre servicio AWS pero no activó búsqueda especializada ===
        if AWS_SERVICES_AVAILABLE:
            is_aws, service_name, svc_category = is_aws_service_query(user_input)
            if is_aws:
                t = user_input.lower()
                if any(k in t for k in ["que es", "qué es", "what is"]):
                    search_query = "AWS " + service_name + " service documentation overview"
                elif any(k in t for k in ["seguridad", "proteger", "asegurar", "best practices"]):
                    search_query = "AWS " + service_name + " security best practices"
                else:
                    search_query = "AWS " + service_name + " documentation"

                logger.info("🦞 Búsqueda AWS service activada: " + service_name + " → '" + search_query + "'")
                try:
                    results = self.searcher.buscar_aws_security(service_name)
                    if results and 'error' not in results[0]:
                        web_context = self.searcher.format_results_for_llm(results[:4])
                        return web_context, len(results), "aws"
                except Exception as e:
                    logger.warning("⚠️ Búsqueda de servicio AWS falló: " + str(e))

        return None, 0, None

    def _get_fallback_response(self, user_input: str) -> str:
        """Fallback con personalidad AgentEagle para cuando el modelo falla."""
        return (
            "🦞 Disculpa, tuve un pequeño problema técnico 🛠️ "
            "Intenta reformular tu pregunta sobre seguridad cloud. Ejemplos:\n"
            "• '¿Cómo proteger un bucket S3 en AWS?'\n"
            "• '¿Qué es un CVE y cómo lo mitigo?'\n"
            "• '¿Cómo configurar MFA en IAM?'\n"
            "• '¿Qué dice el benchmark CIS de AWS sobre encriptación?'\n\n"
            "🔧 También puedes usar skills directamente:\n"
            "• {\"skill\": \"aws_cli\", \"params\": {\"command\": \"s3 ls\"}}\n"
            "• {\"skill\": \"cve_lookup\", \"params\": {\"cve_id\": \"CVE-2024-6387\"}}\n\n"
            "🦞 ¡Estoy aquí para ayudarte con seguridad en AWS, Azure o Google Cloud! 🛡️"
        )

    def _error_response(self, message: str) -> Dict[str, Any]:
        """Respuesta de error con personalidad AgentEagle."""
        return {
            "agent": self.name,
            "response": "🦞 ⚠️ " + message,
            "model": self.config["name"],
            "model_key": self.model_key,
            "success": False,
            "error": True
        }

    async def process(self, user_input: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Procesa consultas con sistema de Skills integrado + búsqueda web opcional.
        """
        intent = self._detect_intent(user_input)
        logger.info("🦞 [INTENT: " + intent + "] '" + user_input[:80] + "...'")

        # === 1. Conversacional simple → respuesta inmediata ===
        if intent in ["greeting", "goodbye", "thanks", "date"]:
            respuesta = self._get_conversational_response(intent, user_input)
            return self._build_response(
                respuesta, success=True, model=self.config["name"],
                intent_detected=intent, tokens_used=len(respuesta.split()),
                fast_response=True, web_search_used=False, skill_used=False
            )

        # === 2. Fuera de scope → redirección amable ===
        if not self._is_cloud_security_question(user_input):
            respuesta = self._get_conversational_response("out_of_scope", user_input)
            return self._build_response(
                respuesta, success=True, model=self.config["name"],
                intent_detected="out_of_scope", tokens_used=len(respuesta.split()),
                fast_response=True, web_search_used=False, skill_used=False
            )

        # === 3. Detectar y ejecutar skill si aplica (ANTES del modelo) ===
        skill_result = None
        if self.enable_skills:
            skill_result = self._detect_and_execute_skill(user_input)

        if skill_result and skill_result.get("skill_execution"):
            # Skill ejecutada exitosamente
            if skill_result.get("success"):
                output = skill_result.get("output")
                if isinstance(output, (dict, list)):
                    output = json.dumps(output, indent=2, ensure_ascii=False)

                respuesta = "✅ **Skill '" + str(
                    skill_result.get('skill_name')) + "' ejecutada exitosamente**\n\n🔧 **Resultado**:\n```\n" + str(
                    output) + "\n```"

                return self._build_response(
                    respuesta,
                    success=True,
                    model=self.config["name"],
                    tokens_used=len(respuesta.split()),
                    intent_detected="skill_execution",
                    web_search_used=False,
                    skill_used=True,
                    skill_name=skill_result.get("skill_name"),
                    skill_metadata=skill_result.get("metadata", {})
                )
            else:
                # Skill falló, incluir error en contexto para que el modelo explique
                logger.warning("⚠️ Skill falló: " + str(skill_result.get('error')))

        # === 4. Búsqueda web para información actualizada ===
        web_context = None
        num_results = 0
        web_search_used = False
        search_category = None

        if self.enable_web_search:
            web_context, num_results, search_category = self._get_security_web_context(user_input)
            if web_context:
                web_search_used = True
                logger.info("✅ Web context [" + str(search_category) + "]: " + str(num_results) + " resultados")

        # === 5. Generar prompt con contexto web si está disponible ===
        full_prompt = self._format_prompt(user_input, context, web_context)

        try:
            options = {
                "temperature": self.config["temp"],
                "num_predict": self.config["max_tokens"],
                "num_ctx": self.config.get("context_length", 2048),
                "stop": ["Usuario:", "###"]
            }

            logger.debug("🧠 Enviando a " + self.config["name"] + " (temp=" + str(options["temperature"]) + ")")

            # Generar respuesta con el modelo
            respuesta_cruda = self.model.generate(prompt=full_prompt, model=self.config["name"], options=options)
            respuesta_limpia = self._clean_response(respuesta_cruda)

            # Fallback solo si respuesta verdaderamente inválida
            if self._should_use_fallback(respuesta_limpia, user_input, intent):
                logger.warning("⚠️ Fallback activado")
                respuesta_limpia = self._get_fallback_response(user_input)
            else:
                logger.info("✅ Respuesta generada (" + str(len(respuesta_limpia)) + " chars)")

            return self._build_response(
                respuesta_limpia,
                success=True,
                model=self.config["name"],
                tokens_used=len(respuesta_limpia.split()) if respuesta_limpia else 0,
                intent_detected="question",
                web_search_used=web_search_used,
                web_results_count=num_results,
                web_search_category=search_category,
                skill_used=False
            )

        except ConnectionError:
            return self._error_response("No se pudo conectar con Ollama. Verifica 'ollama serve'.")
        except TimeoutError:
            return self._error_response("Timeout. Intenta con pregunta más específica.")
        except Exception as e:
            logger.error("❌ Error: " + str(type(e).__name__) + " - " + str(e), exc_info=True)
            return self._error_response("Error: " + str(e)[:100])

