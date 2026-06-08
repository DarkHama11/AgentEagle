from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class BaseAutomationBackend(ABC):
    """
    Backend abstracto para interactuar con Windows UI.
    Implementaciones: UIAutomation, pywinauto, AutoHotkey, PyAutoGUI
    """

    @property
    @abstractmethod
    def backend_name(self) -> str:
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """1 = más prioritario, 4 = último recurso"""
        pass

    @abstractmethod
    async def find_window(self, title: str, class_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Busca una ventana por título y/o clase"""
        pass

    @abstractmethod
    async def click_element(self, element_id: str, session_id: str) -> bool:
        """Hace clic en un elemento por su identificador"""
        pass

    @abstractmethod
    async def type_text(self, element_id: str, text: str, session_id: str) -> bool:
        """Escribe texto en un elemento"""
        pass

    @abstractmethod
    async def get_element_text(self, element_id: str, session_id: str) -> str:
        """Obtiene el texto de un elemento"""
        pass

    @abstractmethod
    async def wait_for_element(self, element_id: str, timeout: int = 30) -> bool:
        """Espera a que un elemento aparezca"""
        pass

    @abstractmethod
    async def take_screenshot(self, region: Optional[Dict] = None) -> bytes:
        """Toma una captura de pantalla"""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Verifica si el backend está disponible en el sistema"""
        pass