# src/server/router.py
"""AgentEagle++ - Router inteligente para enrutamiento de preguntas a agentes."""
import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class AgentRouter:
    """
    Enruta preguntas al agente especializado más adecuado.

    Reglas de enrutamiento:
    • Seguridad cloud (AWS/Azure/GCP, CVEs, IAM, etc.) → seguridad_agent
    • Office (Excel, Word, PowerPoint) → oficina_agent
    • Preguntas generales → general_agent
    • Fuera de scope para todos → general_agent (fallback)
    """

    # Keywords por agente
    SECURITY_KEYWORDS = [
        "aws", "azure", "gcp", "cloud", "nube", "iam", "s3", "ec2", "lambda", "rds", "dynamodb",
        "cloudtrail", "guardduty", "kms", "vpc", "security", "seguridad", "cve", "vulnerabilidad",
        "mitre", "att&ck", "compliance", "cis", "nist", "encript", "cifrar", "policy", "role",
        "eks", "ecs", "ecr", "kubernetes", "k8s", "container", "fargate", "cloudwatch", "config"
    ]

    OFFICE_KEYWORDS = [
        "excel", "word", "powerpoint", "ppt", "office", "microsoft office", "hoja de cálculo",
        "tabla dinámica", "fórmula", "macro", "presentación", "diapositiva", "celda", "rango",
        "atajo", "shortcut", "formato condicional", "gráfico", "chart"
    ]

    # Keywords que indican pregunta general (no especializada)
    GENERAL_INDICATORS = [
        "qué es", "que es", "what is", "quién", "quien", "who", "cuándo", "cuando", "when",
        "dónde", "donde", "where", "por qué", "porque", "why", "cómo", "como", "how",
        "historia", "history", "origen", "origin", "inventor", "inventó", "created",
        "capital", "país", "country", "ciudad", "city", "persona", "person", "evento", "event"
    ]

    def __init__(self, default_agent: str = "general"):
        self.default_agent = default_agent
        logger.info(f"🧭 AgentRouter inicializado (default: {default_agent})")

    def route(self, user_input: str) -> str:
        """
        Decide a qué agente enviar la pregunta.

        Returns:
            str: Nombre del agente ("seguridad", "oficina", "general")
        """
        t = user_input.lower().strip()

        # === 1. ¿Es pregunta de seguridad cloud? ===
        if any(kw in t for kw in self.SECURITY_KEYWORDS):
            # Verificar que no sea solo mención casual
            # Ej: "¿Word tiene seguridad?" → debería ir a oficina, no seguridad
            if any(sec_kw in t for sec_kw in ["aws", "azure", "gcp", "iam", "s3", "ec2", "cve", "eks", "ecs"]):
                logger.debug(f"🧭 Enrutando a 'seguridad': '{user_input[:50]}...'")
                return "seguridad"

        # === 2. ¿Es pregunta de Office? ===
        if any(kw in t for kw in self.OFFICE_KEYWORDS):
            logger.debug(f"🧭 Enrutando a 'oficina': '{user_input[:50]}...'")
            return "oficina"

        # === 3. ¿Es pregunta general/curiosidad? ===
        # Si tiene indicador de pregunta general Y no tiene keywords de seguridad/oficina
        has_general_indicator = any(ind in t for ind in self.GENERAL_INDICATORS)
        has_specialized_keyword = any(kw in t for kw in self.SECURITY_KEYWORDS + self.OFFICE_KEYWORDS)

        if has_general_indicator and not has_specialized_keyword:
            logger.debug(f"🧭 Enrutando a 'general': '{user_input[:50]}...'")
            return "general"

        # === 4. Fallback: si no está claro, usar agente general ===
        logger.debug(f"🧭 Fallback a 'general': '{user_input[:50]}...'")
        return self.default_agent

    def get_available_agents(self) -> list:
        """Lista de agentes disponibles para el frontend."""
        return ["seguridad", "oficina", "general"]