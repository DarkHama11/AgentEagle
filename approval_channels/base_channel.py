from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseApprovalChannel(ABC):
    """Interfaz abstracta para canales de aprobación interactiva."""

    @property
    @abstractmethod
    def channel_name(self) -> str:
        pass

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def send_approval_request(
            self,
            approval_id: str,
            job_id: str,
            pipeline_name: str,
            title: str,
            description: str,
            payload: Dict[str, Any],
            chat_id: Optional[str] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def update_message_approved(self, chat_id: str, message_id: int, approval_id: str, resolved_by: str) -> bool:
        pass

    @abstractmethod
    def update_message_rejected(self, chat_id: str, message_id: int, approval_id: str, resolved_by: str) -> bool:
        pass

    @abstractmethod
    def is_user_authorized(self, user_id: Any) -> bool:
        pass