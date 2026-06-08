import logging
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
