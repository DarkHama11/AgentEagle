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

        # 🆕 Determinar el action_type correcto según el archivo y formato
        action_type = self._determine_action_type(file_path, target_format, payload)

        if not file_path or not os.path.exists(file_path):
            self._publish_response(request_id, user_id, False, "Archivo no encontrado")
            return

        logger.info(f"[ConversionAgent] 📋 Archivo: {os.path.basename(file_path)}")
        logger.info(f"[ConversionAgent] 🎯 Target: {target_format} | Action: {action_type}")

        # 1. Intento primario (API - deshabilitado para pruebas)
        primary_works = False
        if primary_works:
            out_path = file_path.rsplit('.', 1)[0] + f".{target_format}"
            self._publish_response(request_id, user_id, True, "Primario OK", out_path)
            return

        # 2. Fallback a RPA
        logger.warning(f"[ConversionAgent] Fallo primario. Iniciando fallback RPA con {action_type}...")
        self._trigger_rpa(request_id, user_id, file_path, target_format, action_type)

    def _determine_action_type(self, file_path: str, target_format: str, payload: Dict) -> str:
        """Determina el tipo de acción según el archivo y formato destino"""
        if not file_path:
            return "PDF_TO_WORD"

        extension = os.path.splitext(file_path)[1].lower()

        # 🆕 PRIORIDAD 1: Si es una imagen → OCR (sin importar nada más)
        if extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']:
            logger.info(f"[ConversionAgent] 🖼️ Imagen detectada: {extension} → OCR_IMAGE")
            return "OCR_IMAGE"

        # 🆕 PRIORIDAD 2: Si el target es txt → OCR
        if target_format == "txt":
            if extension == '.pdf':
                logger.info(f"[ConversionAgent] 📄 PDF con target txt → OCR_PDF")
                return "OCR_PDF"
            logger.info(f"[ConversionAgent] 🖼️ Archivo con target txt → OCR_IMAGE")
            return "OCR_IMAGE"

        # 🆕 PRIORIDAD 3: Si es PDF y target es docx → PDF_TO_WORD
        if extension == '.pdf' and target_format == 'docx':
            logger.info(f"[ConversionAgent] 📄 PDF → PDF_TO_WORD")
            return "PDF_TO_WORD"

        # 🆕 PRIORIDAD 4: Si es DOCX y target es pdf → WORD_TO_PDF
        if extension in ['.docx', '.doc'] and target_format == 'pdf':
            logger.info(f"[ConversionAgent] 📝 DOCX → WORD_TO_PDF")
            return "WORD_TO_PDF"

        # Default
        logger.warning(f"[ConversionAgent] ⚠️ Tipo no reconocido, usando PDF_TO_WORD por defecto")
        return "PDF_TO_WORD"

    def _trigger_rpa(self, request_id: str, user_id: str, file_path: str,
                     target_format: str, action_type: str):
        out_path = file_path.rsplit('.', 1)[0] + f".{target_format}"
        wait_event = threading.Event()
        with self._lock:
            self._pending_rpa[request_id] = wait_event

        try:
            # 🆕 Log importante
            logger.info(f"[ConversionAgent] 🎯 Enviando a RPA con action_type: {action_type}")

            self.publish("DESKTOP_AUTOMATION_REQUEST", {
                "request_id": request_id,
                "user_id": user_id,
                "action_type": action_type,  # ← AHORA USA EL CORRECTO
                "payload": {"input_path": file_path, "output_path": out_path},
                "timeout": 120
            })

            if wait_event.wait(timeout=130):
                with self._lock:
                    result = self._rpa_results.pop(request_id, {})
                if result.get("success"):
                    self._publish_response(
                        request_id, user_id, True,
                        result.get("message"),
                        result.get("output_data", {}).get("output_path")
                    )
                else:
                    self._publish_response(
                        request_id, user_id, False,
                        f"Fallo RPA: {result.get('error_details')}"
                    )
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

    def _publish_response(self, request_id: str, user_id: str, success: bool,
                          message: str, out_path: Optional[str] = None):
        self.publish("CONVERSION_RESPONSE", {
            "request_id": request_id,
            "user_id": user_id,
            "success": success,
            "message": message,
            "output_path": out_path
        })