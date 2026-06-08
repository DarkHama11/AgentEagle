from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("AgentEagle.NotificationService")


class BaseNotificationService(ABC):
    """
    Interfaz abstracta para servicios de notificación.
    Implementa el patrón Strategy para permitir múltiples canales.
    """

    @abstractmethod
    def send(self, message: str, **kwargs) -> Dict[str, Any]:
        """
        Envía una notificación.

        :param message: Mensaje a enviar
        :param kwargs: Parámetros adicionales específicos del canal
        :return: Diccionario con resultado (status, message_id, etc.)
        """
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """Verifica si el canal está habilitado."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Prueba la conexión con el servicio."""
        pass

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Nombre del canal (telegram, email, slack, etc.)"""
        pass
        