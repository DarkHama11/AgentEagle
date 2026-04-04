# src/agents/skills/__init__.py
"""AgentEagle++ - Sistema de Skills para acciones especializadas."""

from .base_skill import BaseSkill, SkillExecutionError
from .skill_registry import SkillRegistry

# Skills disponibles (se registran automáticamente)
from .aws_cli_skill import AwsCliSkill
from .cve_lookup_skill import CveLookupSkill
from .compliance_check_skill import ComplianceCheckSkill
from .file_ops_skill import FileOpsSkill  # ← NUEVA
from .mitre_mapping_skill import MitreMappingSkill  # ← NUEVA

__all__ = [
    "BaseSkill",
    "SkillExecutionError",
    "SkillRegistry",
    "AwsCliSkill",
    "CveLookupSkill",
    "ComplianceCheckSkill",
    "FileOpsSkill",  # ← NUEVA
    "MitreMappingSkill",  # ← NUEVA
]