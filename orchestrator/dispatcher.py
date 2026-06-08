from typing import Dict, Any
from agents.registry import AgentRegistry


class Dispatcher:
    """Ejecutor de agentes. Delega la resolución al AgentRegistry."""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    def execute(self, agent_name: str, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.registry is None:
            raise ValueError("El Dispatcher requiere un AgentRegistry válido.")

        agent = self.registry.get_agent(agent_name)
        return agent.execute(action, payload)