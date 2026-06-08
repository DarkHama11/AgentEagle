from typing import Dict, Any
import logging
from agents.base_agent import BaseAgent      # Import absoluto
from event_bus.event import Event            # Import absoluto (sin puntos)

logger = logging.getLogger("AgentEagle.Notification")

class NotificationAgent(BaseAgent):
    name = "notification_agent"
    description = "Envía notificaciones sobre estados del sistema."
    capabilities = ["send_email", "send_slack"]

    def __init__(self, event_bus=None):
        super().__init__(event_bus)
        if self.event_bus:
            self.event_bus.subscribe("payment.completed", self.on_payment_completed)
            self.event_bus.subscribe("step.failed", self.on_step_failed)

    def on_payment_completed(self, event: Event) -> None:
        logger.info(f"📧 NOTIFICACIÓN: Pago completado para factura {event.payload.get('invoice_id')}")
        if self.event_bus:
            self.event_bus.publish(Event(
                event_type="notification.sent",
                source=self.name,
                payload={"message": "Pago exitoso notificado"}
            ))

    def on_step_failed(self, event: Event) -> None:
        logger.error(f"🚨 ALERTA: Fallo en paso {event.payload.get('step')}: {event.payload.get('error')}")

    def execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "success", "result": "Notification agent is event-driven."}