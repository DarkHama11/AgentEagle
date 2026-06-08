import os
import uuid
import logging
import threading
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("AgentEagle.TelegramConversionBridge")


class TelegramConversionBridge:
    """
    Puente entre Telegram y el sistema RPA de AgentEagle.

    Flujo:
    1. Recibe evento 'conversion.pdf_to_word' de Telegram
    2. Descarga el PDF desde Telegram
    3. Publica 'CONVERSION_REQUEST' para el sistema RPA
    4. Escucha 'CONVERSION_RESPONSE'
    5. Envía el archivo .docx de vuelta a Telegram
    """

    def __init__(self, event_bus, bot_token: str):
        self.event_bus = event_bus
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

        # Directorios temporales
        self.upload_dir = Path("data/telegram_uploads")
        self.output_dir = Path("data/telegram_outputs")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Mapeo de request_id -> datos de Telegram
        self._pending_jobs: Dict[str, Dict] = {}
        self._lock = threading.Lock()

        # Suscribirse a eventos
        self._subscribe_events()

        logger.info("✅ TelegramConversionBridge inicializado")

    def _subscribe_events(self):
        """Se suscribe a los eventos relevantes"""
        self.event_bus.subscribe("conversion.pdf_to_word", self._handle_pdf_to_word)
        self.event_bus.subscribe("conversion.word_to_pdf", self._handle_word_to_pdf)
        self.event_bus.subscribe("conversion.ocr_pdf", self._handle_ocr_pdf)
        self.event_bus.subscribe("conversion.ocr_image", self._handle_ocr_image)
        self.event_bus.subscribe("CONVERSION_RESPONSE", self._handle_conversion_response)

    def _handle_pdf_to_word(self, event: Dict[str, Any]):
        """Maneja el evento de conversión PDF → Word desde Telegram"""
        payload = event.get("payload", {})
        self._process_conversion(payload, "pdf_to_word")

    def _handle_word_to_pdf(self, event: Dict[str, Any]):
        """Maneja el evento de conversión Word → PDF desde Telegram"""
        payload = event.get("payload", {})
        self._process_conversion(payload, "word_to_pdf")

    def _handle_ocr_pdf(self, event: Dict[str, Any]):
        """Maneja el evento OCR de PDF desde Telegram"""
        payload = event.get("payload", {})
        self._process_conversion(payload, "ocr_pdf")

    def _handle_ocr_image(self, event: Dict[str, Any]):
        """Maneja el evento OCR de imagen desde Telegram"""
        payload = event.get("payload", {})
        self._process_conversion(payload, "ocr_image")

    def _process_conversion(self, payload: Dict[str, Any], conversion_type: str):
        """Procesa una solicitud de conversión"""
        job_id = payload.get("job_id", str(uuid.uuid4()))
        chat_id = payload.get("telegram_chat_id")
        file_id = payload.get("file_id")
        file_name = payload.get("file_name", "documento")

        if not chat_id or not file_id:
            logger.error(f"❌ Datos de Telegram faltantes para job {job_id}")
            return

        logger.info(f"📥 Procesando {conversion_type} para chat {chat_id}: {file_name}")

        # Descargar archivo desde Telegram
        try:
            local_path = self._download_telegram_file(file_id, file_name, job_id)
            if not local_path:
                self._send_message(chat_id, "❌ Error descargando el archivo. Intenta nuevamente.")
                return
        except Exception as e:
            logger.error(f"❌ Error descargando archivo: {e}")
            self._send_message(chat_id, f"❌ Error: {str(e)}")
            return

        # Guardar información del job
        request_id = str(uuid.uuid4())
        with self._lock:
            self._pending_jobs[request_id] = {
                "chat_id": chat_id,
                "file_name": file_name,
                "local_path": local_path,
                "conversion_type": conversion_type,
                "message_id": payload.get("telegram_message_id")
            }

        # Determinar el target_format y action_type según el tipo de conversión
        if conversion_type == "pdf_to_word":
            target_format = "docx"
            action_type = "PDF_TO_WORD"
        elif conversion_type == "word_to_pdf":
            target_format = "pdf"
            action_type = "WORD_TO_PDF"
        elif conversion_type in ["ocr_pdf", "ocr_image"]:
            target_format = "txt"
            action_type = "OCR"
        else:
            target_format = "docx"
            action_type = "PDF_TO_WORD"

        # Publicar evento para el sistema RPA
        self.event_bus.publish("CONVERSION_REQUEST", {
            "request_id": request_id,
            "file_path": str(local_path),
            "target_format": target_format,
            "user_id": f"telegram_{chat_id}",
            "output_directory": str(self.output_dir)
        })

        logger.info(f"📤 Conversión solicitada: {request_id} ({conversion_type})")

    def _download_telegram_file(self, file_id: str, file_name: str, job_id: str) -> Optional[Path]:
        """Descarga un archivo desde Telegram"""
        try:
            # Paso 1: Obtener la ruta del archivo
            response = requests.post(
                f"{self.base_url}/getFile",
                json={"file_id": file_id},
                timeout=10
            )
            response.raise_for_status()
            result = response.json()

            if not result.get("ok"):
                logger.error(f"❌ Error getFile: {result}")
                return None

            file_path = result["result"]["file_path"]
            download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"

            # Paso 2: Descargar el archivo
            response = requests.get(download_url, timeout=60)
            response.raise_for_status()

            # Paso 3: Guardar localmente
            safe_name = f"{job_id}_{file_name}"
            local_path = self.upload_dir / safe_name

            with open(local_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"✅ Archivo descargado: {local_path} ({len(response.content)} bytes)")
            return local_path

        except Exception as e:
            logger.error(f"❌ Error descargando archivo de Telegram: {e}")
            return None

    def _handle_conversion_response(self, event: Dict[str, Any]):
        """Maneja la respuesta de conversión del sistema RPA"""
        payload = event.get("payload", {})
        request_id = payload.get("request_id")
        success = payload.get("success", False)
        output_path = payload.get("output_path")
        message = payload.get("message", "")

        with self._lock:
            job_data = self._pending_jobs.pop(request_id, None)

        if not job_data:
            # No es un job de Telegram, ignorar
            return

        chat_id = job_data["chat_id"]
        file_name = job_data["file_name"]

        if success and output_path and os.path.exists(output_path):
            # Enviar el archivo convertido de vuelta a Telegram
            try:
                self._send_message(
                    chat_id,
                    f"✅ <b>Conversión completada</b>\n\n"
                    f"📄 {file_name}\n"
                    f"📤 Enviando archivo..."
                )

                self._send_document(chat_id, output_path)

                logger.info(f"✅ Archivo enviado a chat {chat_id}: {output_path}")

            except Exception as e:
                logger.error(f"❌ Error enviando archivo a Telegram: {e}")
                self._send_message(chat_id, f"❌ Error enviando el archivo: {str(e)}")

            # Limpiar archivos temporales
            try:
                os.remove(job_data["local_path"])
                if os.path.exists(output_path):
                    os.remove(output_path)
            except Exception as e:
                logger.warning(f"⚠️ No se pudieron eliminar archivos temporales: {e}")
        else:
            # Conversión falló
            error_msg = message or "Error desconocido"
            self._send_message(
                chat_id,
                f"❌ <b>Error en la conversión</b>\n\n"
                f"📄 {file_name}\n\n"
                f"⚠️ {error_msg}"
            )
            logger.error(f"❌ Conversión falló para chat {chat_id}: {error_msg}")

    def _send_message(self, chat_id: str, text: str) -> None:
        """Envía un mensaje a Telegram"""
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")

    def _send_document(self, chat_id: str, file_path: str) -> None:
        """Envía un documento a Telegram"""
        try:
            with open(file_path, 'rb') as f:
                files = {'document': f}
                data = {'chat_id': chat_id}
                requests.post(
                    f"{self.base_url}/sendDocument",
                    data=data,
                    files=files,
                    timeout=60
                )
        except Exception as e:
            logger.error(f"Error enviando documento: {e}")
            raise
