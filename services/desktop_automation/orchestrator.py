import asyncio
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

from .base_plugin import BaseAutomationPlugin
from .plugin_registry import PluginRegistry
from .session_manager import SessionManager
from .retry_strategy import RetryStrategy
from .recovery_manager import RecoveryManager
from .approval_gateway import ApprovalGateway
from .auditor import Auditor

from dto.desktop_automation.action_dto import AutomationAction, ActionResult, ActionStatus
from dto.desktop_automation.session_dto import AutomationSession, SessionStatus
from event_bus.event import Event

logger = logging.getLogger("AgentEagle.DesktopAutomation.Orchestrator")


class DesktopOrchestrator:
    """
    Orquestador principal que coordina la ejecución de acciones
    a través de plugins, manejando reintentos, recuperación y aprobaciones.
    """

    def __init__(self, event_bus, approval_manager=None):
        self.event_bus = event_bus
        self.plugin_registry = PluginRegistry()
        self.session_manager = SessionManager()
        self.retry_strategy = RetryStrategy()
        self.recovery_manager = RecoveryManager()
        self.approval_gateway = ApprovalGateway(approval_manager, event_bus)
        self.auditor = Auditor()

    async def execute_action(self, action: AutomationAction) -> ActionResult:
        """Ejecuta una acción completa con reintentos y recuperación"""
        start_time = time.time()
        result = None

        # Publicar evento de inicio
        self._publish_event("desktop.action_started", {
            "action_id": action.action_id,
            "action_type": action.action_type.value,
            "plugin": action.plugin_name
        })

        # Verificar si requiere aprobación
        if action.requires_approval:
            approved = await self.approval_gateway.request_approval(action)
            if not approved:
                return ActionResult(
                    action_id=action.action_id,
                    status=ActionStatus.FAILED,
                    success=False,
                    error="Aprobación denegada por el usuario"
                )

        # Intentar ejecutar con reintentos
        for attempt in range(1, action.max_retries + 1):
            try:
                plugin = self.plugin_registry.find_plugin_for_action(action)
                if not plugin:
                    raise ValueError(f"No hay plugin disponible para la acción {action.action_type.value}")

                # Obtener o crear sesión
                session = self.session_manager.get_or_create_session(action.plugin_name)

                # Ejecutar acción
                result = await plugin.execute(action, session)

                if result.success:
                    result.execution_time_ms = int((time.time() - start_time) * 1000)
                    result.completed_at = datetime.now()
                    self._publish_event("desktop.action_completed", {
                        "action_id": action.action_id,
                        "success": True
                    })
                    return result

                # Si falló, intentar recuperación
                if attempt < action.max_retries:
                    recovered = await self.recovery_manager.attempt_recovery(
                        plugin, result.error, session
                    )
                    if recovered:
                        self._publish_event("desktop.recovery_completed", {
                            "action_id": action.action_id,
                            "attempt": attempt
                        })
                        continue

                result.retries_used = attempt

            except Exception as e:
                logger.error(f"Error en intento {attempt}: {e}", exc_info=True)
                if attempt < action.max_retries:
                    await self.retry_strategy.wait_before_retry(attempt)
                    continue
                result = ActionResult(
                    action_id=action.action_id,
                    status=ActionStatus.FAILED,
                    success=False,
                    error=str(e)
                )

        # Si llegamos aquí, todos los intentos fallaron
        result.status = ActionStatus.FAILED
        result.success = False
        result.execution_time_ms = int((time.time() - start_time) * 1000)
        self._publish_event("desktop.action_failed", {
            "action_id": action.action_id,
            "error": result.error
        })
        return result

    def _publish_event(self, event_type: str, payload: Dict[str, Any]):
        if self.event_bus:
            self.event_bus.publish(Event(
                event_type=event_type,
                source="desktop_automation_agent",
                payload=payload
            ))