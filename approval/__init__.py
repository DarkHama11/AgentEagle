"""
Módulo de aprobación humana para AgentEagle 2.0.
Permite pausar pipelines en pasos sensibles y esperar aprobación del usuario.
"""

from .approval_request import ApprovalRequest, ApprovalStatus
from .approval_store import ApprovalStore
from .approval_manager import ApprovalManager
from .approval_api import ApprovalAPI

__all__ = [
    "ApprovalRequest",
    "ApprovalStatus",
    "ApprovalStore",
    "ApprovalManager",
    "ApprovalAPI"
]