# -*- coding: utf-8 -*-
# src/server/router.py
"""AgentEagle - Router inteligente para enrutamiento de preguntas a agentes (v2.2 optimizado)."""

import logging
import re
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    """Resultado del enrutamiento de una consulta."""
    agent_name: str
    confidence: float
    matched_keywords: List[str]
    intent: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario para API/JSON."""
        return {
            "agent_name": self.agent_name,
            "confidence": self.confidence,
            "matched_keywords": self.matched_keywords,
            "intent": self.intent,
            "metadata": self.metadata,
        }


class AgentRouter:
    """
    Router inteligente para dirigir consultas al agente más adecuado.

    Soporta:
    - Enrutamiento por keywords explícitas (expandidas)
    - Enrutamiento por clasificación de intención con regex
    - Boost por patrones específicos (CVE, Excel, etc.)
    - Fallback a agente por defecto con threshold ajustado
    """

    # ✅ KEYWORDS EXPANDIDAS por agente (incluye español/inglés, sinónimos, variantes)
    KEYWORD_RULES: Dict[str, List[str]] = {
        "seguridad": [
            # CVE y vulnerabilidades
            "cve", "vulnerability", "vulnerabilidad", "exploit", "zero-day", "0-day",
            "patch", "parche", "security advisory", "bulletin", "nvd", "mitre",
            # Cloud providers
            "aws", "amazon web services", "azure", "microsoft azure", "gcp", "google cloud",
            "cloud security", "seguridad cloud", "cloud hardening",
            # Servicios AWS
            "iam", "s3", "ec2", "lambda", "cloudtrail", "guardduty", "kms", "vpc",
            "eks", "ecs", "rds", "secrets manager", "config", "security hub",
            # Servicios Azure
            "entra id", "azure ad", "defender for cloud", "key vault", "sentinel",
            # Servicios GCP
            "cloud iam", "security command center", "cloud kms", "chronicle",
            # Compliance y frameworks
            "compliance", "cis", "nist", "iso 27001", "pci dss", "hipaa", "gdpr",
            "benchmark", "hardening", "best practices", "mejores practicas",
            # MITRE ATT&CK
            "att&ck", "mitre", "t1059", "t1078", "t1190", "technique", "tactic",
            # Términos generales de seguridad
            "threat", "amenaza", "attack", "ataque", "breach", "incidente",
            "penetration", "pentest", "red team", "blue team", "soc", "siem"
        ],
        "oficina": [
            # Excel
            "excel", "hoja de calculo", "spreadsheet", "formula", "fórmula", "function",
            "vlookup", "buscarv", "hlookup", "buscarh", "index", "indice", "match",
            "pivot", "tabla dinamica", "pivot table", "grafico", "chart", "macro",
            "vba", "visual basic", "power query", "power pivot", "conditional formatting",
            "formato condicional", "data validation", "validacion de datos",
            # Word
            "word", "documento", "document", "formato", "format", "estilo", "style",
            "mail merge", "combinar correspondencia", "indice", "table of contents",
            "header", "footer", "encabezado", "pie de pagina", "page break",
            # PowerPoint
            "powerpoint", "presentacion", "presentation", "slide", "diapositiva",
            "animation", "animacion", "transition", "transicion", "master slide",
            "theme", "tema", "layout", "diseno", "design",
            # Outlook
            "outlook", "correo", "email", "calendario", "calendar", "reunion", "meeting",
            "signature", "firma", "rule", "regla", "folder", "carpeta", "attachment",
            # Office 365 / Integration
            "office 365", "microsoft 365", "sharepoint", "teams", "onedrive",
            "power automate", "flow", "power apps", "forms", "planner", "to do",
            # Términos generales
            "plantilla", "template", "formato condicional", "proteger hoja",
            "contrasena", "password", "compartir", "colaborar", "coauthoring"
        ],
        "general": [
            # Saludos y básicos
            "hola", "hello", "hi", "buenos dias", "buenas tardes", "buenas noches",
            "hey", "saludos", "que tal", "como estas", "how are you",
            # Fecha y hora
            "que dia", "que hora", "fecha", "hora", "hoy", "today", "now", "current time",
            # Deportes
            "deporte", "sport", "futbol", "soccer", "baloncesto", "basketball", "tenis",
            "liga", "champions", "nba", "mlb", "partido", "game", "match", "juega", "play",
            "resultado", "score", "tabla", "standings", "fixture", "calendario",
            # Cultura general
            "cultura", "culture", "historia", "history", "ciencia", "science",
            "tecnologia", "technology", "arte", "art", "musica", "music", "cine", "movie",
            "libro", "book", "autor", "author", "pais", "country", "ciudad", "city",
            # Noticias y actualidad
            "noticia", "news", "actualidad", "current events", "trending", "viral",
            "ultimo", "latest", "reciente", "recent", "nuevo", "new",
            # Preguntas generales
            "que es", "what is", "como", "how", "por que", "why", "cuando", "when",
            "donde", "where", "quien", "who", "cual", "which", "explicame", "explain",
            "ayuda", "help", "informacion", "information", "datos", "data",
            # Entretenimiento
            "serie", "series", "pelicula", "movie", "actor", "actress", "director",
            "juego", "game", "videojuego", "videogame", "streaming", "netflix", "youtube"
        ]
    }

    # ✅ REGEX PATTERNS EXPANDIDOS para detección precisa
    REGEX_RULES: Dict[str, List[Tuple[str, float]]] = {
        "seguridad": [
            # CVE IDs: CVE-2024-12345
            (r'cve-\d{4}-\d{4,7}', 0.5),
            # MITRE techniques: T1059, T1078.001
            (r'\b[tT]\d{4}(\.\d{3})?\b', 0.4),
            # Cloud services con contexto de seguridad
            (r'(aws|azure|gcp)\s+(security|iam|s3|ec2|lambda|cloudtrail|guardduty|kms)', 0.35),
            # Compliance frameworks
            (r'\b(cis|nist|iso\s*27001|pci\s*dss|hipaa|gdpr)\b', 0.3),
            # Vulnerability terms
            (r'(zero[-\s]?day|0[-\s]?day|exploit|vulnerabilit[yí]|amenaza)', 0.25),
        ],
        "oficina": [
            # Excel formulas: =VLOOKUP(, =SI(, =BUSCARV(
            (r'[=\(]?\s*(vlookup|hlookup|buscarv|buscarh|si|if|sumar\.si|countif)\s*\(', 0.4),
            # Excel features
            (r'(tabla\s*dinamica|pivot\s*table|formato\s*condicional|validacion\s*de\s*datos)', 0.35),
            # VBA/Macros
            (r'(macro|vba|visual\s*basic|sub\s+\w+|function\s+\w+)', 0.3),
            # PowerPoint terms
            (r'(diapositiva|slide|animacion|animation|transicion|transition)', 0.25),
            # Word formatting
            (r'(estilo|style|encabezado|header|pie\s*de\s*pagina|footer|indice)', 0.2),
        ],
        "general": [
            # Date/time questions
            (r'(que\s+(dia|hora|fecha)|what\s+(day|time)|hoy\s+es|today\s+is)', 0.3),
            # Sports questions
            (r'(cuando\s+.*\s*(juega|play)|partido\s+.*\s*(hoy|today)|liga\s+.*\s*(tabla|standings))', 0.3),
            # General knowledge questions
            (r'(que\s+es|what\s+is|quien\s+es|who\s+is|como\s+funciona|how\s+does.*work)', 0.2),
            # Entertainment
            (r'(pelicula|movie|serie|series|actor|actress|director|netflix|youtube)', 0.2),
        ]
    }

    # ✅ BOOST por patrones de alta prioridad (se suman al score base)
    PRIORITY_BOOSTS: Dict[str, List[Tuple[str, float]]] = {
        "seguridad": [
            (r'cve.*aws|aws.*cve', 0.3),
            (r'vulnerabilidad.*cloud|cloud.*vulnerabilidad', 0.25),
            (r'mitre.*aws|aws.*mitre', 0.2),
        ],
        "oficina": [
            (r'excel.*formula|formula.*excel', 0.3),
            (r'vlookup|buscarv', 0.25),
            (r'powerpoint.*animacion|animacion.*powerpoint', 0.2),
        ],
        "general": [
            (r'hola|hello|hi', 0.2),
            (r'que\s+dia|what\s+day', 0.2),
        ]
    }

    # ✅ Threshold ajustado: más permisivo pero con validación adicional
    CONFIDENCE_THRESHOLD = 0.10  # Reducido de 0.15 a 0.10

    def __init__(self, agents: Dict[str, Any], default_agent: str = "general"):
        """
        Inicializar router con agentes disponibles.

        Args:
            agents: Diccionario de agentes {name: agent_instance}
            default_agent: Nombre del agente por defecto para fallback
        """
        self.agents = agents
        self.default_agent = default_agent
        self._compiled_regexes = self._compile_regexes()
        logger.info(
            f"🧭 AgentRouter v2.2 inicializado (default: {default_agent}, threshold: {self.CONFIDENCE_THRESHOLD})")

    def _compile_regexes(self) -> Dict[str, List[Tuple[re.Pattern, float]]]:
        """Compilar patrones regex para mejor performance."""
        compiled = {}
        for agent_name, patterns in self.REGEX_RULES.items():
            compiled[agent_name] = [(re.compile(p, re.I), bonus) for p, bonus in patterns]
        return compiled

    def route(self, query: str, preferred_agent: Optional[str] = None) -> RouteResult:
        """
        Enrutar una consulta al agente más adecuado.

        Args:
            query: Consulta del usuario
            preferred_agent: Agente preferido por el usuario (opcional)

        Returns:
            RouteResult: Resultado del enrutamiento con confianza y metadata
        """
        query_lower = query.lower().strip()

        # Si el usuario especificó un agente y existe, usarlo directamente
        if preferred_agent and preferred_agent != "auto" and preferred_agent in self.agents:
            logger.debug(f"🎯 Agente forzado por usuario: '{preferred_agent}'")
            return RouteResult(
                agent_name=preferred_agent,
                confidence=1.0,
                matched_keywords=["user_preference"],
                intent="forced",
                metadata={"preferred_by_user": True}
            )

        # Calcular scores por agente
        scores: Dict[str, Tuple[float, List[str], float]] = {}  # (score, matched_keywords, regex_bonus)

        for agent_name, keywords in self.KEYWORD_RULES.items():
            if agent_name not in self.agents:
                continue

            # 1. Contar keywords matcheadas (con peso por longitud de keyword)
            matched = []
            keyword_score = 0
            for kw in keywords:
                if kw in query_lower:
                    matched.append(kw)
                    # Keywords más largas = más específicas = más peso
                    keyword_score += min(len(kw.split()) * 0.05, 0.15)

            # 2. Bonus por regex matches
            regex_bonus = 0
            regex_matches = []
            for pattern, bonus in self._compiled_regexes.get(agent_name, []):
                if pattern.search(query_lower):
                    regex_bonus += bonus
                    regex_matches.append(f"regex:{pattern.pattern[:30]}")

            # 3. Boost por patrones de prioridad
            priority_bonus = 0
            for pattern, boost in self.PRIORITY_BOOSTS.get(agent_name, []):
                if re.search(pattern, query_lower, re.I):
                    priority_bonus += boost

            # Score final con pesos
            final_score = keyword_score + regex_bonus + priority_bonus
            final_score = min(final_score, 1.0)  # Cap en 1.0

            if final_score > 0:
                all_matched = matched + regex_matches
                scores[agent_name] = (final_score, all_matched[:15], regex_bonus + priority_bonus)

        # Seleccionar agente con mayor score
        if scores:
            best_agent = max(scores.keys(), key=lambda k: scores[k][0])
            confidence, matched_keywords, bonus = scores[best_agent]

            # ✅ Threshold ajustado: más permisivo
            if confidence >= self.CONFIDENCE_THRESHOLD:
                logger.debug(f"🎯 Enrutado a '{best_agent}' (conf: {confidence:.2f}, keywords: {matched_keywords[:3]})")
                return RouteResult(
                    agent_name=best_agent,
                    confidence=round(confidence, 3),
                    matched_keywords=matched_keywords[:10],
                    intent=self._detect_intent(query_lower, best_agent),
                    metadata={
                        "scoring": {
                            "keyword_matches": len([k for k in matched_keywords if not k.startswith("regex:")]),
                            "regex_bonus": round(bonus, 3)
                        }
                    }
                )

        # Fallback a agente por defecto
        logger.debug(
            f"🔄 Fallback a agente por defecto: '{self.default_agent}' (max confidence: {max((s[0] for s in scores.values()), default=0):.2f})")
        return RouteResult(
            agent_name=self.default_agent,
            confidence=0.0,
            matched_keywords=[],
            intent="fallback",
            metadata={"fallback_reason": "no_confident_match",
                      "max_score": max((s[0] for s in scores.values()), default=0)}
        )

    def _detect_intent(self, query: str, agent_name: str) -> Optional[str]:
        """Detectar intención específica dentro de un agente."""
        intent_map = {
            "seguridad": {
                "cve_lookup": ["cve-", "vulnerability", "vulnerabilidad", "exploit", "zero-day", "0-day", "parche"],
                "mitre_mapping": ["mitre", "att&ck", "t1059", "t1078", "technique", "tactic"],
                "aws_service": ["aws", "amazon web services", "ec2", "s3", "iam", "lambda", "cloudtrail", "guardduty"],
                "azure_service": ["azure", "microsoft azure", "entra", "defender", "key vault"],
                "gcp_service": ["gcp", "google cloud", "cloud iam", "security command center"],
                "compliance": ["cis", "nist", "iso", "pci", "hipaa", "gdpr", "compliance", "benchmark"],
            },
            "oficina": {
                "excel_formula": ["formula", "fórmula", "funcion", "vlookup", "buscarv", "si(", "if(", "sumar",
                                  "count"],
                "excel_vba": ["macro", "vba", "visual basic", "automatizar", "script", "sub ", "function "],
                "excel_pivot": ["pivot", "tabla dinamica", "resumen", "agrupar", "drill"],
                "word_format": ["formato", "estilo", "pagina", "indice", "encabezado", "footer"],
                "powerpoint_design": ["diapositiva", "slide", "animacion", "transicion", "tema", "layout"],
                "outlook_email": ["correo", "email", "outlook", "firma", "regla", "calendario"],
            },
            "general": {
                "greeting": ["hola", "buenos", "buenas", "hey", "hi", "saludos"],
                "date_time": ["que dia", "que hora", "fecha", "hora actual", "hoy es", "what day"],
                "sports": ["futbol", "soccer", "barcelona", "liga", "partido", "juega", "nba", "champions"],
                "entertainment": ["pelicula", "movie", "serie", "series", "actor", "netflix", "youtube"],
                "knowledge": ["que es", "what is", "explicame", "explain", "como funciona"],
            }
        }

        agent_intents = intent_map.get(agent_name, {})
        for intent, keywords in agent_intents.items():
            if any(kw in query for kw in keywords):
                return intent

        return "general_question"

    def list_agents(self) -> List[str]:
        """Listar nombres de agentes disponibles."""
        return list(self.agents.keys())

    def get_agent_capabilities(self, agent_name: str) -> Dict[str, Any]:
        """Obtener capacidades declaradas de un agente."""
        agent = self.agents.get(agent_name)
        if not agent:
            return {}

        return {
            "name": getattr(agent, "name", agent_name),
            "description": getattr(agent, "description", ""),
            "trigger_keywords": getattr(agent, "trigger_keywords", []),
            "ready": getattr(agent, "is_ready", lambda: True)(),
        }