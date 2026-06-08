from typing import Dict, Any
from ..base_agent import BaseAgent


class RouterAgent(BaseAgent):
    """Agente funcional para enrutamiento inteligente de tareas."""

    name = "router_agent"
    description = "Analiza la consulta y determina qué agente especializado debe manejarla."
    capabilities = ["route", "classify_intent"]

    def execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if action == "route":
            query = payload.get("query", "").lower()
            if "documento" in query or "pdf" in query:
                target = "document_agent"
            else:
                target = "general_agent"

            return {
                "status": "success",
                "result": f"Consulta enrutada a: {target}",
                "data": {"target_agent": target}
            }
        else:
            return {
                "status": "error",
                "result": f"Acción '{action}' no soportada por RouterAgent."
            }
        