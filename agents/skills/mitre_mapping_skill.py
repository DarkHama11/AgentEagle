# src/agents/skills/mitre_mapping_skill.py
"""AgentEagle++ - Skill para mapear técnicas MITRE ATT&CK a controles de seguridad cloud."""
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
    logger.warning("⚠️ SecuritySearch no disponible para MitreMappingSkill")


class MitreMappingSkill(BaseSkill):
    """
    Skill para mapear técnicas MITRE ATT&CK a controles de seguridad cloud.

    ✅ Mapea técnicas MITRE a controles AWS/Azure/GCP
    ✅ Proporciona detección y mitigación específica por cloud provider
    ✅ Ideal para: equipos de seguridad, compliance, threat hunting
    """

    name = "mitre_mapping"
    description = "Mapea técnicas MITRE ATT&CK a controles de seguridad cloud (AWS/Azure/GCP) con detección y mitigación"
    version = "1.0.0"
    category = "security"

    # === Mapeo predefinido de técnicas MITRE a controles cloud ===
    MITRE_CLOUD_MAPPINGS = {
        "T1059": {  # Command and Scripting Interpreter
            "name": "Command and Scripting Interpreter",
            "tactic": "Execution",
            "aws_controls": [
                "AWS CloudTrail (logging de comandos API)",
                "AWS GuardDuty (detección de anomalías)",
                "AWS Systems Manager Session Manager (acceso controlado)",
                "Amazon Detective (investigación forense)"
            ],
            "azure_controls": [
                "Azure Activity Log",
                "Microsoft Defender for Cloud",
                "Azure Sentinel",
                "Azure Policy (restrict execution)"
            ],
            "gcp_controls": [
                "Cloud Audit Logs",
                "Security Command Center",
                "Cloud Security Command Center",
                "VPC Service Controls"
            ],
            "detection": [
                "Logging de ejecución de comandos (CloudTrail, Activity Log)",
                "Detección de scripts sospechosos (EDR/XDR)",
                "Monitoreo de procesos hijos inusuales",
                "Alertas por ejecución desde ubicaciones no comunes"
            ],
            "mitigation": [
                "Application whitelisting (AppLocker, WDAC)",
                "Restrict PowerShell execution policies",
                "Disable unnecessary scripting engines",
                "Implement least privilege IAM policies"
            ]
        },
        "T1078": {  # Valid Accounts
            "name": "Valid Accounts",
            "tactic": "Persistence, Privilege Escalation",
            "aws_controls": ["IAM Access Analyzer", "CloudTrail", "GuardDuty", "AWS SSO"],
            "azure_controls": ["Azure AD Identity Protection", "Azure AD Privileged Identity Management",
                               "Defender for Identity"],
            "gcp_controls": ["Cloud IAM", "Security Command Center", "BeyondCorp Enterprise"],
            "detection": ["Anomalous login patterns", "Impossible travel detection", "Privilege escalation monitoring"],
            "mitigation": ["MFA enforcement", "Short-lived credentials", "Regular access reviews",
                           "Principle of least privilege"]
        },
        "T1098": {  # Account Manipulation
            "name": "Account Manipulation",
            "tactic": "Persistence",
            "aws_controls": ["IAM Access Analyzer", "CloudTrail", "Config Rules"],
            "azure_controls": ["Azure AD Audit Logs", "Azure Policy", "Defender for Cloud Apps"],
            "gcp_controls": ["Cloud Audit Logs", "Organization Policies", "Security Command Center"],
            "detection": ["IAM policy change monitoring", "New user/role creation alerts",
                          "Permission escalation detection"],
            "mitigation": ["Require MFA for IAM changes", "Separation of duties", "Regular access audits",
                           "Automated policy validation"]
        },
        "T1530": {  # Data from Cloud Storage
            "name": "Data from Cloud Storage",
            "tactic": "Collection",
            "aws_controls": ["S3 Bucket Policies", "S3 Access Logs", "Macie", "CloudTrail"],
            "azure_controls": ["Azure Storage Analytics", "Azure Policy", "Microsoft Defender for Storage"],
            "gcp_controls": ["Cloud Storage Audit Logs", "VPC Service Controls", "Data Loss Prevention"],
            "detection": ["Unusual data access patterns", "Large data exfiltration detection",
                          "Cross-account access monitoring"],
            "mitigation": ["Encryption at rest (SSE-KMS)", "Bucket policies with least privilege", "VPC endpoints only",
                           "Data classification with Macie/DLP"]
        },
        "T1557": {  # Adversary-in-the-Middle
            "name": "Adversary-in-the-Middle",
            "tactic": "Collection, Credential Access",
            "aws_controls": ["AWS Certificate Manager", "Elastic Load Balancing", "CloudFront"],
            "azure_controls": ["Azure Application Gateway", "Azure Front Door", "Azure SSL/TLS"],
            "gcp_controls": ["Cloud Load Balancing", "Cloud CDN", "Certificate Authority Service"],
            "detection": ["Certificate transparency monitoring", "DNS anomaly detection", "Network traffic analysis"],
            "mitigation": ["Enforce HTTPS/TLS everywhere", "Certificate pinning", "HSTS headers",
                           "Regular certificate rotation"]
        }
    }

    parameters = {
        "technique_id": {
            "type": str,
            "description": "ID de técnica MITRE ATT&CK (ej: T1059, T1078)",
            "required": False,
            "example": "T1059"
        },
        "cloud_provider": {
            "type": str,
            "description": "Proveedor cloud: aws, azure, gcp, o all",
            "required": False,
            "enum": ["aws", "azure", "gcp", "all"],
            "default": "all"
        },
        "search_query": {
            "type": str,
            "description": "Búsqueda por nombre de técnica o táctica (si no se proporciona technique_id)",
            "required": False,
            "example": "command and script"
        },
        "include_detection": {
            "type": bool,
            "description": "Incluir métodos de detección en la respuesta",
            "required": False,
            "default": True
        },
        "include_mitigation": {
            "type": bool,
            "description": "Incluir métodos de mitigación en la respuesta",
            "required": False,
            "default": True
        },
    }

    required_permissions = ["network", "security_read"]
    default_timeout = 20

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.searcher = SecuritySearch(timeout=self.timeout) if SEARCH_AVAILABLE else None
        self._initialized = True
        logger.info("✅ MitreMappingSkill inicializada")

    def _validate_technique_id(self, technique_id: str) -> bool:
        """Valida formato de ID de técnica MITRE."""
        pattern = r'^[Tt]\d{4}(\.\d{3})?$'
        return bool(re.match(pattern, technique_id))

    def _get_mapping(self, technique_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene mapeo predefinido para una técnica."""
        technique_id_normalized = technique_id.upper()
        return self.MITRE_CLOUD_MAPPINGS.get(technique_id_normalized)

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta el mapeo de técnica MITRE a controles cloud."""
        start_time = time.time()

        if not self.searcher:
            return {
                "success": False,
                "error": "SecuritySearch no disponible. Verifica instalación.",
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "searcher_not_available"}
            }

        technique_id = input_data.get("technique_id")
        cloud_provider = input_data.get("cloud_provider", "all").lower()
        search_query = input_data.get("search_query")
        include_detection = input_data.get("include_detection", True)
        include_mitigation = input_data.get("include_mitigation", True)

        # Validar que al menos un parámetro de búsqueda esté presente
        if not technique_id and not search_query:
            return {
                "success": False,
                "error": "Debes proporcionar 'technique_id' o 'search_query'",
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "missing_parameters"}
            }

        try:
            mapping_result = None

            # === Búsqueda por technique_id ===
            if technique_id:
                if not self._validate_technique_id(technique_id):
                    return {
                        "success": False,
                        "error": "Formato de técnica MITRE inválido: '" + technique_id + "'. Usa formato: T#### o T###.###",
                        "output": None,
                        "metadata": {"skill_name": self.name, "reason": "invalid_technique_format"}
                    }

                logger.info("🎯 Buscando mapeo para técnica MITRE: " + technique_id.upper())
                mapping_result = self._get_mapping(technique_id.upper())

                # Si no hay mapeo predefinido, buscar en web
                if not mapping_result:
                    logger.info("⚠️ Mapeo predefinido no encontrado, buscando en fuentes oficiales...")
                    search_results = self.searcher.buscar_mitre_technique(technique_id)
                    if search_results and 'error' not in search_results[0]:
                        mapping_result = {
                            "technique_id": technique_id.upper(),
                            "name": "Consultar fuentes oficiales para detalles",
                            "tactic": "Consultar MITRE ATT&CK",
                            "aws_controls": ["Ver documentación AWS Security"],
                            "azure_controls": ["Ver documentación Microsoft Security"],
                            "gcp_controls": ["Ver documentación GCP Security"],
                            "detection": ["Consultar MITRE ATT&CK para detección específica"],
                            "mitigation": ["Consultar MITRE ATT&CK para mitigación específica"],
                            "external_resources": [r.get("url", "") for r in search_results[:3] if r.get("url")]
                        }

            # === Búsqueda por nombre/táctica ===
            elif search_query:
                logger.info("🎯 Buscando técnicas MITRE relacionadas con: '" + search_query + "'")
                search_results = self.searcher.search(
                    "MITRE ATT&CK " + search_query + " technique cloud security mapping",
                    num_results=5
                )

                if search_results and 'error' not in search_results[0]:
                    mapping_result = {
                        "search_query": search_query,
                        "related_techniques": "Consultar resultados de búsqueda",
                        "external_resources": [r.get("url", "") for r in search_results[:5] if r.get("url")],
                        "note": "Proporciona technique_id específico para mapeo detallado a controles cloud"
                    }

            execution_time = int((time.time() - start_time) * 1000)

            if mapping_result:
                # Filtrar por cloud_provider si no es "all"
                if cloud_provider != "all":
                    filtered_result = {
                        "technique_id": mapping_result.get("technique_id", technique_id),
                        "name": mapping_result.get("name", ""),
                        "tactic": mapping_result.get("tactic", ""),
                        "cloud_controls": mapping_result.get(cloud_provider + "_controls", []),
                    }
                    if include_detection:
                        filtered_result["detection"] = mapping_result.get("detection", [])
                    if include_mitigation:
                        filtered_result["mitigation"] = mapping_result.get("mitigation", [])
                    if "external_resources" in mapping_result:
                        filtered_result["external_resources"] = mapping_result["external_resources"]
                    if "note" in mapping_result:
                        filtered_result["note"] = mapping_result["note"]

                    mapping_result = filtered_result

                # Agregar metadata de tiempo de ejecución
                mapping_result["execution_time_ms"] = execution_time

                # ✅ CORREGIDO: Determinar fuente del mapeo correctamente
                mapping_source = "web_search"
                if technique_id and self._get_mapping(technique_id.upper()):
                    mapping_source = "predefined"

                return {
                    "success": True,
                    "output": mapping_result,
                    "error": None,
                    "metadata": {
                        "skill_name": self.name,
                        "skill_version": self.version,
                        "execution_time_ms": execution_time,
                        "technique_id": technique_id,
                        "cloud_provider": cloud_provider,
                        "mapping_source": mapping_source
                    }
                }
            else:
                return {
                    "success": False,
                    "error": "No se encontró mapeo para la técnica especificada. Intenta con técnicas comunes: T1059, T1078, T1098, T1530, T1557",
                    "output": None,
                    "metadata": {"skill_name": self.name, "reason": "no_mapping_found"}
                }

        except Exception as e:
            logger.error("❌ Error en MitreMappingSkill: " + str(e))
            return {
                "success": False,
                "error": "Error: " + str(e)[:200],
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "unexpected_error"}
            }