import logging
from core.event_bus import EventBus
from core.agent import BaseAgent
from services.desktop_automation.plugin_registry import PluginRegistry
from services.desktop_automation.session_manager import SessionManager
from services.desktop_automation.backends.pywinauto_backend import PywinautoBackend
from dto.desktop_automation.action_dto import ActionRequest

# ⚠️ IMPORTANTE: Esta línea fuerza la carga del plugin para que el decorador @PluginRegistry.register se ejecute
from services.desktop_automation.plugins import pdfgear_plugin

logger = logging.getLogger(__name__)


class DesktopAutomationAgent(BaseAgent):
    def __init__(self, event_bus: EventBus):
        super().__init__("DesktopAutomationAgent", event_bus)
        self.backend = PywinautoBackend()
        self.subscribe("DESKTOP_AUTOMATION_REQUEST", self._handle_request)

    def _handle_request(self, event):
        payload = event.get("payload", {})
        request_id = payload.get("request_id", "unknown")
        session_id = SessionManager.create_session("pywinauto")

        request = ActionRequest(
            session_id=session_id,
            action_type=payload.get("action_type"),
            payload=payload.get("payload", {}),
            timeout=payload.get("timeout", 60)
        )

        try:
            plugin = PluginRegistry.get_plugin(request.action_type)
            result = plugin.execute(request, self.backend)
            self.publish("DESKTOP_AUTOMATION_RESPONSE", {
                "request_id": request_id,
                "session_id": session_id,
                "success": result.success,
                "message": result.message,
                "output_data": result.output_data,
                "error_details": result.error_details
            })
        except Exception as e:
            logger.error(f"Error en RPA: {e}", exc_info=True)
            self.publish("DESKTOP_AUTOMATION_RESPONSE", {
                "request_id": request_id,
                "session_id": session_id,
                "success": False,
                "error_details": str(e)
            })
        finally:
            SessionManager.close_session(session_id)