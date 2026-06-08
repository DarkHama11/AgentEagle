# src/agents/skills/cve_lookup_skill.py
"""AgentEagle++ - Skill para búsqueda de CVEs en fuentes oficiales."""
from .base_skill import BaseSkill, SkillExecutionError
from typing import Dict, Any, Optional, List
import logging
import time
import re

logger = logging.getLogger(__name__)

try:
    from tools.security_search import SecuritySearch

    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False
    logger.warning("⚠️ SecuritySearch no disponible para CveLookupSkill")


class CveLookupSkill(BaseSkill):
    """
    Skill para buscar información de CVEs en fuentes oficiales.

    ✅ Fuentes: cve.mitre.org, nvd.nist.gov, cisa.gov
    ✅ Ideal para: consultar vulnerabilidades específicas o recientes
    """

    name = "cve_lookup"
    description = "Busca información de vulnerabilidades CVE en fuentes oficiales (NVD, MITRE, CISA)"
    version = "1.0.0"
    category = "security"

    parameters = {
        "cve_id": {
            "type": str,
            "description": "ID del CVE a buscar (ej: CVE-2024-6387)",
            "required": False,
            "example": "CVE-2024-6387"
        },
        "search_query": {
            "type": str,
            "description": "Término de búsqueda para CVEs recientes (ej: 'aws', 'linux')",
            "required": False,
            "example": "aws"
        },
        "severity": {
            "type": str,
            "description": "Filtrar por severidad: critical, high, medium, low",
            "required": False,
            "enum": ["critical", "high", "medium", "low"],
            "default": "critical"
        },
        "limit": {
            "type": int,
            "description": "Número máximo de resultados a retornar",
            "required": False,
            "default": 5
        },
    }

    required_permissions = ["network"]
    default_timeout = 15

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.searcher = SecuritySearch(timeout=self.timeout) if SEARCH_AVAILABLE else None
        self._initialized = True
        logger.info(f"✅ CveLookupSkill inicializada")

    def _validate_cve_id(self, cve_id: str) -> bool:
        """Valida formato de CVE ID."""
        pattern = r'CVE-\d{4}-\d+'
        return bool(re.match(pattern, cve_id, re.I))

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta la búsqueda de CVEs."""
        start_time = time.time()

        if not self.searcher:
            return {
                "success": False,
                "error": "SecuritySearch no disponible. Verifica instalación.",
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "searcher_not_available"}
            }

        cve_id = input_data.get("cve_id")
        search_query = input_data.get("search_query")
        severity = input_data.get("severity", "critical")
        limit = input_data.get("limit", 5)

        # Validar que al menos un parámetro esté presente
        if not cve_id and not search_query:
            return {
                "success": False,
                "error": "Debes proporcionar 'cve_id' o 'search_query'",
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "missing_parameters"}
            }

        try:
            if cve_id:
                # Búsqueda de CVE específico
                if not self._validate_cve_id(cve_id):
                    return {
                        "success": False,
                        "error": "Formato de CVE inválido: '" + cve_id + "'. Usa formato: CVE-YYYY-NNNNN",
                        "output": None,
                        "metadata": {"skill_name": self.name, "reason": "invalid_cve_format"}
                    }

                logger.info("🔐 Buscando CVE: " + cve_id.upper())
                results = self.searcher.buscar_cve(cve_id)

            else:
                # Búsqueda de CVEs recientes por término
                logger.info("🔐 Buscando CVEs recientes: '" + search_query + "' (severidad: " + severity + ")")
                results = self.searcher.buscar_cve_recientes(limit=limit, severity=severity)

            execution_time = int((time.time() - start_time) * 1000)

            if results and 'error' not in results[0]:
                # Formatear resultados para respuesta estructurada
                formatted_results = []
                for r in results[:limit]:
                    formatted_results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("snippet", ""),
                        "source": r.get("domain", "")
                    })

                return {
                    "success": True,
                    "output": formatted_results,
                    "error": None,
                    "metadata": {
                        "skill_name": self.name,
                        "skill_version": self.version,
                        "execution_time_ms": execution_time,
                        "results_count": len(formatted_results),
                        "query": cve_id or search_query
                    }
                }
            else:
                return {
                    "success": False,
                    "error": results[0].get("error", "No se encontraron resultados"),
                    "output": None,
                    "metadata": {"skill_name": self.name, "reason": "no_results"}
                }

        except Exception as e:
            logger.error("❌ Error en CveLookupSkill: " + str(e))
            return {
                "success": False,
                "error": "Error: " + str(e)[:200],
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "unexpected_error"}
            }