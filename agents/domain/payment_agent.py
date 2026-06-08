from typing import Dict, Any
from agents.base_agent import BaseAgent      # Import absoluto
from event_bus.event import Event            # Import absoluto (sin puntos)

class PaymentAgent(BaseAgent):
    name = "payment_agent"
    description = "Agente que procesa pagos tras la extracción de documentos."
    capabilities = ["process_payment", "validate_invoice"]

    def __init__(self, event_bus=None):
        super().__init__(event_bus)
        # Suscribirse automáticamente al iniciar
        if self.event_bus:
            self.event_bus.subscribe("document.processed", self.on_document_processed)

    def on_document_processed(self, event: Event) -> None:
        """Reacciona automáticamente cuando un documento es procesado."""
        invoice_id = event.payload.get("invoice_id")
        if invoice_id:
            # Simular procesamiento de pago
            if self.event_bus:
                self.event_bus.publish(Event(
                    event_type="payment.completed",
                    source=self.name,
                    payload={"invoice_id": invoice_id, "amount": 150.00, "status": "paid"}
                ))

    def execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "success", "result": "Payment agent is event-driven."}