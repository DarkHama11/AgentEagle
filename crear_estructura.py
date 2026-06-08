import os

# Definir la estructura completa de archivos y su contenido
files_to_create = {
    "core/__init__.py": "",

    "core/event_bus.py": """import logging
import threading
import uuid
from typing import Dict, List, Callable, Any

logger = logging.getLogger(__name__)

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, callback: Callable):
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
        logger.debug(f"[EventBus] Suscrito a: {event_type}")

    def publish(self, event_type: str, payload: Dict[str, Any]):
        logger.info(f"[EventBus] Publicando evento: {event_type}")
        with self._lock:
            callbacks = list(self._subscribers.get(event_type, []))

        event_data = {"type": event_type, "payload": payload, "id": str(uuid.uuid4())}
        for callback in callbacks:
            try:
                callback(event_data)
            except Exception as e:
                logger.error(f"[EventBus] Error en suscriptor: {e}", exc_info=True)
""",

    "core/agent.py": """import logging
from typing import Any, Dict
from core.event_bus import EventBus

logger = logging.getLogger(__name__)

class BaseAgent:
    def __init__(self, name: str, event_bus: EventBus):
        self.name = name
        self.event_bus = event_bus
        logger.info(f"[{self.name}] Inicializado.")

    def subscribe(self, event_type: str, callback: Any):
        self.event_bus.subscribe(event_type, callback)

    def publish(self, event_type: str, payload: Dict[str, Any]):
        self.event_bus.publish(event_type, payload)
""",

    "dto/__init__.py": "",
    "dto/desktop_automation/__init__.py": "",

    "dto/desktop_automation/action_dto.py": """from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class ActionRequest:
    session_id: str
    action_type: str
    payload: Dict[str, Any]
    timeout: int = 60

@dataclass
class ActionResult:
    session_id: str
    success: bool
    message: str
    output_data: Optional[Dict[str, Any]] = None
    error_details: Optional[str] = None
""",

    "dto/desktop_automation/session_dto.py": """from dataclasses import dataclass
from typing import Optional, Any
from datetime import datetime

@dataclass
class SessionState:
    session_id: str
    backend_type: str
    process_id: Optional[int] = None
    app_instance: Optional[Any] = None
    is_active: bool = False
    created_at: datetime = datetime.now()
""",

    "services/__init__.py": "",
    "services/desktop_automation/__init__.py": "",

    "services/desktop_automation/base_plugin.py": """from abc import ABC, abstractmethod
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
""",

    "services/desktop_automation/plugin_registry.py": """from typing import Dict, Type
from .base_plugin import BaseAutomationPlugin

class PluginRegistry:
    _plugins: Dict[str, Type[BaseAutomationPlugin]] = {}

    @classmethod
    def register(cls, plugin_class: Type[BaseAutomationPlugin]):
        instance = plugin_class()
        cls._plugins[instance.action_type] = plugin_class
        return plugin_class

    @classmethod
    def get_plugin(cls, action_type: str) -> BaseAutomationPlugin:
        if action_type not in cls._plugins:
            raise ValueError(f"Plugin no registrado para: {action_type}")
        return cls._plugins[action_type]()
""",

    "services/desktop_automation/session_manager.py": """from typing import Dict, Optional
from dto.desktop_automation.session_dto import SessionState
import uuid
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    _sessions: Dict[str, SessionState] = {}

    @classmethod
    def create_session(cls, backend_type: str) -> str:
        session_id = str(uuid.uuid4())
        cls._sessions[session_id] = SessionState(session_id=session_id, backend_type=backend_type)
        return session_id

    @classmethod
    def close_session(cls, session_id: str):
        if session_id in cls._sessions:
            session = cls._sessions.pop(session_id)
            if session.app_instance:
                try:
                    session.app_instance.kill()
                except Exception:
                    pass
""",

    "services/desktop_automation/retry_strategy.py": """import time
import logging
logger = logging.getLogger(__name__)

def retry_action(max_retries: int = 3, delay: float = 2.0):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                    else:
                        raise
        return wrapper
    return decorator
""",

    "services/desktop_automation/auditor.py": """import logging
import json
from datetime import datetime
logger = logging.getLogger(__name__)

class AutomationAuditor:
    @staticmethod
    def log_action(session_id: str, action: str, status: str, details: str = ""):
        logger.info(f"[AUDIT] {session_id} | {action} | {status} | {details}")
""",

    "services/desktop_automation/backends/__init__.py": "",

    "services/desktop_automation/backends/pywinauto_backend.py": """import logging
from pywinauto import Application
from ..retry_strategy import retry_action

logger = logging.getLogger(__name__)

class PywinautoBackend:
    def __init__(self):
        self.app = None

    def start(self, exe_path: str):
        logger.info(f"[Backend] Iniciando: {exe_path}")
        self.app = Application(backend="uia").start(exe_path)
        return self.app

    @retry_action(max_retries=3, delay=1.5)
    def click_button(self, window_title: str, button_id: str):
        window = self.app.window(title_re=window_title)
        window.wait('ready', timeout=10)
        window.child_window(auto_id=button_id, control_type="Button").click_input()

    @retry_action(max_retries=3, delay=1.5)
    def type_text(self, window_title: str, edit_id: str, text: str):
        window = self.app.window(title_re=window_title)
        window.wait('ready', timeout=10)
        window.child_window(auto_id=edit_id, control_type="Edit").set_text(text)

    def kill(self):
        if self.app and self.app.process:
            self.app.kill()
""",

    "services/desktop_automation/plugins/__init__.py": "",

    "services/desktop_automation/plugins/pdfgear_plugin.py": """import os
import logging
from ..base_plugin import BaseAutomationPlugin
from ..plugin_registry import PluginRegistry
from dto.desktop_automation.action_dto import ActionRequest, ActionResult
from ..auditor import AutomationAuditor

logger = logging.getLogger(__name__)

@PluginRegistry.register
class PDFGearPlugin(BaseAutomationPlugin):
    @property
    def action_type(self) -> str:
        return "PDF_TO_WORD"

    def execute(self, request: ActionRequest, backend) -> ActionResult:
        session_id = request.session_id
        input_path = request.payload.get("input_path")
        output_path = request.payload.get("output_path")

        if not os.path.exists(input_path):
            return ActionResult(session_id, False, "Archivo no encontrado", "FileNotFound")

        try:
            AutomationAuditor.log_action(session_id, "START", "INFO", input_path)
            backend.start(r"C:\\Program Files\\PDFgear\\PDFgear.exe")

            logger.info("[PDFGear] Simulación de conversión exitosa (Ajustar IDs con Inspect.exe)")
            AutomationAuditor.log_action(session_id, "COMPLETE", "SUCCESS", output_path)

            return ActionResult(session_id, True, "Conversión completada (Simulado)", {"output_path": output_path})
        except Exception as e:
            return ActionResult(session_id, False, "Fallo en automatización", str(e))
        finally:
            self.cleanup(backend)

    def cleanup(self, backend):
        try:
            backend.kill()
        except Exception:
            pass
""",

    "agents/__init__.py": "",
    "agents/functional/__init__.py": "",

    "agents/functional/desktop_automation_agent.py": """import logging
from core.event_bus import EventBus
from core.agent import BaseAgent
from services.desktop_automation.plugin_registry import PluginRegistry
from services.desktop_automation.session_manager import SessionManager
from services.desktop_automation.backends.pywinauto_backend import PywinautoBackend
from dto.desktop_automation.action_dto import ActionRequest

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
                "request_id": request_id, "session_id": session_id,
                "success": result.success, "message": result.message,
                "output_data": result.output_data, "error_details": result.error_details
            })
        except Exception as e:
            logger.error(f"Error en RPA: {e}", exc_info=True)
            self.publish("DESKTOP_AUTOMATION_RESPONSE", {"request_id": request_id, "success": False, "error_details": str(e)})
        finally:
            SessionManager.close_session(session_id)
""",

    "agents/functional/conversion_agent.py": """import logging
import threading
import os
from typing import Dict, Any, Optional
from core.agent import BaseAgent

logger = logging.getLogger(__name__)

class ConversionAgent(BaseAgent):
    def __init__(self, event_bus: Any):
        super().__init__("ConversionAgent", event_bus)
        self._pending_rpa = {}
        self._rpa_results = {}
        self._lock = threading.Lock()
        self.subscribe("CONVERSION_REQUEST", self._handle_conversion)
        self.subscribe("DESKTOP_AUTOMATION_RESPONSE", self._handle_rpa_response)

    def _handle_conversion(self, event: Dict[str, Any]):
        payload = event.get("payload", {})
        request_id = payload.get("request_id", "unknown")
        file_path = payload.get("file_path")
        target_format = payload.get("target_format", "docx").lower()
        user_id = payload.get("user_id", "system")

        if not file_path or not os.path.exists(file_path):
            self._publish_response(request_id, user_id, False, "Archivo no encontrado")
            return

        # 1. Intento primario (Simulado como fallido para probar fallback)
        primary_works = False
        if primary_works:
            out_path = file_path.rsplit('.', 1)[0] + f".{target_format}"
            self._publish_response(request_id, user_id, True, "Primario OK", out_path)
            return

        # 2. Fallback a RPA
        logger.warning(f"[{self.name}] Fallo primario. Iniciando fallback RPA...")
        self._trigger_rpa(request_id, user_id, file_path, target_format)

    def _trigger_rpa(self, request_id: str, user_id: str, file_path: str, target_format: str):
        out_path = file_path.rsplit('.', 1)[0] + f".{target_format}"
        wait_event = threading.Event()
        with self._lock:
            self._pending_rpa[request_id] = wait_event

        try:
            self.publish("DESKTOP_AUTOMATION_REQUEST", {
                "request_id": request_id, "user_id": user_id,
                "action_type": "PDF_TO_WORD",
                "payload": {"input_path": file_path, "output_path": out_path},
                "timeout": 120
            })

            if wait_event.wait(timeout=130):
                with self._lock:
                    result = self._rpa_results.pop(request_id, {})
                if result.get("success"):
                    self._publish_response(request_id, user_id, True, result.get("message"), result.get("output_data", {}).get("output_path"))
                else:
                    self._publish_response(request_id, user_id, False, f"Fallo RPA: {result.get('error_details')}")
            else:
                self._publish_response(request_id, user_id, False, "Timeout en RPA")
        finally:
            with self._lock:
                self._pending_rpa.pop(request_id, None)
                self._rpa_results.pop(request_id, None)

    def _handle_rpa_response(self, event: Dict[str, Any]):
        payload = event.get("payload", {})
        request_id = payload.get("request_id")
        with self._lock:
            if request_id in self._pending_rpa:
                self._rpa_results[request_id] = payload
                self._pending_rpa[request_id].set()

    def _publish_response(self, request_id: str, user_id: str, success: bool, message: str, out_path: Optional[str] = None):
        self.publish("CONVERSION_RESPONSE", {"request_id": request_id, "user_id": user_id, "success": success, "message": message, "output_path": out_path})
""",

    "main.py": """import logging
import sys
import time
import uuid
import os
from core.event_bus import EventBus
from agents.functional.conversion_agent import ConversionAgent
from agents.functional.desktop_automation_agent import DesktopAutomationAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

def initialize_system():
    logger.info("🚀 Iniciando AgentEagle Core...")
    event_bus = EventBus()
    ConversionAgent(event_bus)
    DesktopAutomationAgent(event_bus)
    logger.info("✅ Sistema inicializado.")
    return event_bus

def test_flow(event_bus: EventBus):
    logger.info("\\n" + "="*50 + "\\n🧪 INICIANDO PRUEBA DE CONVERSIÓN CON FALLBACK RPA\\n" + "="*50)

    test_file = "C:/temp/documento_ejemplo.pdf"
    os.makedirs("C:/temp", exist_ok=True)
    with open(test_file, "w") as f:
        f.write("PDF Falso para prueba")

    event_bus.publish("CONVERSION_REQUEST", {
        "request_id": str(uuid.uuid4()),
        "file_path": test_file,
        "target_format": "docx",
        "user_id": "telegram_user_123"
    })

if __name__ == "__main__":
    try:
        event_bus = initialize_system()
        test_flow(event_bus)
        logger.info("🟢 Sistema en ejecución. (Presiona Ctrl+C para detener)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\\n🛑 Deteniendo sistema...")
        sys.exit(0)
"""
}

# Ejecutar la creación
print("🛠️  Generando estructura del proyecto AgentEagle...\n")
for filepath, content in files_to_create.items():
    directory = os.path.dirname(filepath)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Creado: {filepath}")

print("\n🎉 ¡Estructura del proyecto creada exitosamente!")
print("Ahora puedes ejecutar: python main.py")