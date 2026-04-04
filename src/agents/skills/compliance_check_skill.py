# src/agents/skills/compliance_check_skill.py
"""AgentEagle++ - Skill para verificar compliance contra frameworks (CIS, NIST, ISO)."""
from .base_skill import BaseSkill, SkillExecutionError
from typing import Dict, Any, Optional, List
import logging
import time

logger = logging.getLogger(__name__)

try:
    from tools.security_search import SecuritySearch

    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False
    logger.warning("⚠️ SecuritySearch no disponible para ComplianceCheckSkill")


class ComplianceCheckSkill(BaseSkill):
    """
    Skill para buscar información de compliance frameworks.

    ✅ Frameworks: CIS Benchmarks, NIST, ISO 27001, PCI DSS
    ✅ Ideal para: consultar controles específicos, mejores prácticas
    """

    name = "compliance_check"
    description = "Busca información de frameworks de compliance (CIS, NIST, ISO 27001, PCI DSS)"
    version = "1.0.0"
    category = "compliance"

    parameters = {
        "framework": {
            "type": str,
            "description": "Framework de compliance: cis, nist, iso, pci",
            "required": True,
            "enum": ["cis", "nist", "iso", "pci", "hipaa", "gdpr"]
        },
        "service": {
            "type": str,
            "description": "Servicio cloud específico (ej: 'aws s3', 'azure ad')",
            "required": False,
            "example": "aws s3"
        },
        "control_id": {
            "type": str,
            "description": "ID de control específico (ej: 'CIS 1.1', 'NIST AC-1')",
            "required": False,
            "example": "CIS 1.1"
        },
        "limit": {
            "type": int,
            "description": "Número máximo de resultados",
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
        logger.info(f"✅ ComplianceCheckSkill inicializada")

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta la búsqueda de información de compliance."""
        start_time = time.time()

        if not self.searcher:
            return {
                "success": False,
                "error": "SecuritySearch no disponible.",
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "searcher_not_available"}
            }

        framework = input_data.get("framework", "").lower()
        service = input_data.get("service", "")
        control_id = input_data.get("control_id", "")
        limit = input_data.get("limit", 5)

        if not framework:
            return {
                "success": False,
                "error": "Parámetro 'framework' es requerido",
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "missing_framework"}
            }

        try:
            # Construir query específico
            if control_id:
                query = framework.upper() + " " + control_id + " control requirements"
            elif service:
                query = framework.upper() + " benchmark " + service + " security controls"
            else:
                query = framework.upper() + " security framework overview"

            logger.info("📋 Buscando compliance: " + query)
            results = self.searcher.search_safe(query, num_results=limit, source_filter="compliance")

            execution_time = int((time.time() - start_time) * 1000)

            if results and 'error' not in results[0]:
                formatted_results = []
                for r in results[:limit]:
                    formatted_results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("snippet", ""),
                        "source": r.get("domain", ""),
                        "framework": framework.upper()
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
                        "framework": framework.upper(),
                        "query": query
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
            logger.error("❌ Error en ComplianceCheckSkill: " + str(e))
            return {
                "success": False,
                "error": "Error: " + str(e)[:200],
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "unexpected_error"}
            }