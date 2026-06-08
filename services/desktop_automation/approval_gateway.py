import logging
from typing import Optional

from dto.desktop_automation.action_dto import AutomationAction
from approval.approval_manager import ApprovalManager
from event_bus.event import Event

logger = logging.getLogger("AgentEagle.DesktopAutomation.ApprovalGateway")


class ApprovalGateway:
    """
    Puerta de aprobación para acciones críticas de automatización.
    """

    CRITICAL_ACTIONS = [
        "delete_file",
        "send_email",
        "modify_system_settings",
        "execute_script"
    ]

    def __init__(self, approval_manager: Optional[ApprovalManager], event_bus):
        self.approval_manager = approval_manager
        self.event_bus = event_bus

    async def request_approval(self, action: AutomationAction) -> bool:
        """Solicita aprobación humana para una acción crítica"""
        if not action.requires_approval:
            return True

        logger.info(f"Solicitando aprobación para acción: {action.action_id}")

        # Publicar evento de aprobación requerida
        self.event_bus.publish(Event(
            event_type="desktop.approval_required",
            source="desktop_automation_agent",
            payload={
                "action_id": action.action_id,
                "action_type": action.action_type.value,
                "reason": action.approval_reason or "Acción crítica requiere aprobación humana"
            }
        ))

        # Esperar respuesta (implementación simplificada)
        # En producción, esto sería asíncrono con callbacks
        return False  # Por defecto denegado hasta implementar el flujo completo