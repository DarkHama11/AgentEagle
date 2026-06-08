from abc import ABC, abstractmethod
from typing import Any
from dto.desktop_automation.action_dto import ActionRequest, ActionResult

class BaseAutomationPlugin(ABC):
    @property
    @abstractmethod
    def action_type(self) -> str:
        pass

    @abstractmethod
    def execute(self, request: ActionRequest, backend: Any) -> ActionResult:
        pass

    def cleanup(self, backend: Any):
        pass