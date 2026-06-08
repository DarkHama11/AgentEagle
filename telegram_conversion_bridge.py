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
    Maneja documentos (PDFs, Word) y fotos (OCR).
    Para OCR, envía el texto directamente en el chat.
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

        # Mapeo de job_id -> datos de Telegram
        self._pending_jobs: Dict[str, Dict] = {}
        self._lock = threading.Lock()

        # Suscribirse a eventos
        self._subscribe_events()

        logger.info("✅ TelegramConversionBridge inicializado")

    def _subscribe_events(self):
        """Se suscribe a los eventos relevantes"""
        # Conversión de documentos
        self.event_bus.subscribe("conversion.pdf_to_word", self._handle_pdf_to_word)
        self.event_bus.subscribe("conversion.word_to_pdf", self._handle_word_to_pdf)

        # OCR (imágenes y PDFs escaneados)
        self.event_bus.subscribe("conversion.ocr_pdf", self._handle_ocr_pdf)
        self.event_bus.subscribe("conversion.ocr_image", self._handle_ocr_image)

        # Respuestas de conversión
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

        # 🆕 Manejar tanto documentos como fotos
        file_id = payload.get("file_id") or payload.get("photo_file_id")
        file_name = payload.get("file_name", f"imagen_{job_id[:8]}.jpg")

        if not chat_id or not file_id:
            logger.error(f"❌ Datos de Telegram faltantes para job {job_id}")
            logger.error(f"   chat_id: {chat_id}, file_id: {file_id}")
            if chat_id:
                self._send_message(chat_id, "❌ Error: No se pudo obtener el archivo. Intenta nuevamente.")
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
        output_data = payload.get("output_data", {})

        with self._lock:
            job_data = self._pending_jobs.pop(request_id, None)

        if not job_data:
            # No es un job de Telegram, ignorar
            return

        chat_id = job_data["chat_id"]
        file_name = job_data["file_name"]
        conversion_type = job_data["conversion_type"]

        if success and output_path and os.path.exists(output_path):
            # 🆕 Para OCR, enviar el texto directamente en el chat
            if conversion_type in ["ocr_image", "ocr_pdf"]:
                self._send_ocr_result(chat_id, file_name, output_path, output_data)
            else:
                # Para conversiones (PDF→Word, etc.), enviar el archivo
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

    def _send_ocr_result(self, chat_id: str, file_name: str, output_path: str, output_data: Dict):
        """Envía el resultado del OCR directamente en el chat (como en la imagen)"""
        try:
            # Leer el texto extraído
            with open(output_path, 'r', encoding='utf-8') as f:
                texto_extraido = f.read()

            # Calcular estadísticas
            num_palabras = len(texto_extraido.split())
            num_caracteres = len(texto_extraido)

            # 🆕 Formato como en la imagen
            mensaje = (
                f"📄 <b>Texto Extraído (OCR)</b>\n\n"
                f"📁 <b>Archivo:</b> {file_name}\n"
                f"📊 <b>Palabras:</b> {num_palabras}\n"
                f"📏 <b>Caracteres:</b> {num_caracteres}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<code>{texto_extraido}</code>"
            )

            # Si el texto es muy largo (>4096 caracteres), dividirlo en varios mensajes
            max_length = 4000  # Telegram tiene límite de 4096

            if len(mensaje) <= max_length:
                # Enviar todo en un solo mensaje
                self._send_message(chat_id, mensaje, parse_mode="HTML")
            else:
                # Dividir en partes
                header = (
                    f"📄 <b>Texto Extraído (OCR)</b>\n\n"
                    f"📁 <b>Archivo:</b> {file_name}\n"
                    f"📊 <b>Palabras:</b> {num_palabras}\n"
                    f"📏 <b>Caracteres:</b> {num_caracteres}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                )

                # Enviar header
                self._send_message(chat_id, header, parse_mode="HTML")

                # Enviar texto en bloques
                inicio = 0
                while inicio < len(texto_extraido):
                    fin = min(inicio + max_length, len(texto_extraido))
                    bloque = texto_extraido[inicio:fin]

                    # Asegurar que no corte una palabra a la mitad
                    if fin < len(texto_extraido):
                        ultimo_espacio = bloque.rfind(' ')
                        if ultimo_espacio > 0:
                            bloque = bloque[:ultimo_espacio]

                    self._send_message(
                        chat_id,
                        f"<code>{bloque}</code>",
                        parse_mode="HTML"
                    )
                    inicio += len(bloque)

            logger.info(f"✅ Texto OCR enviado a chat {chat_id} ({num_palabras} palabras)")

        except Exception as e:
            logger.error(f"❌ Error enviando texto OCR: {e}")
            self._send_message(chat_id, f"❌ Error mostrando el texto: {str(e)}")
            # Fallback: enviar como archivo
            try:
                self._send_document(chat_id, output_path)
            except:
                pass

    def _send_message(self, chat_id: str, text: str, parse_mode: str = "HTML") -> None:
        """Envía un mensaje a Telegram"""
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")

    def _send_ocr_result(self, chat_id: str, file_name: str, output_path: str, output_data: Dict):
        """Envía el resultado del OCR directamente en el chat con recuadro y botón copiar"""
        try:
            # Leer el texto extraído
            with open(output_path, 'r', encoding='utf-8') as f:
                texto_extraido = f.read()

            # 🆕 ESCAPAR caracteres HTML (crítico para que <pre> funcione)
            texto_extraido = (
                texto_extraido
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
            )

            # Calcular estadísticas
            num_palabras = len(texto_extraido.split())
            num_caracteres = len(texto_extraido)

            # 🆕 Header con estadísticas
            header = (
                f"📄 <b>Texto Extraído (OCR)</b>\n\n"
                f"📁 <b>Archivo:</b> {file_name}\n"
                f"📊 <b>Palabras:</b> {num_palabras}\n"
                f"📏 <b>Caracteres:</b> {num_caracteres}\n\n"
            )

            # 🆕 Usar <pre> para el recuadro con botón "Copiar"
            # Telegram muestra el botón copiar solo con <pre>
            texto_bloque = f"<pre>{texto_extraido}</pre>"

            mensaje_completo = header + texto_bloque

            # Telegram tiene límite de 4096 caracteres por mensaje
            max_length = 4000

            if len(mensaje_completo) <= max_length:
                # Todo en un mensaje
                self._send_message(chat_id, mensaje_completo, parse_mode="HTML")
            else:
                # Dividir en partes
                # 1. Enviar header primero
                self._send_message(chat_id, header, parse_mode="HTML")

                # 2. Enviar el texto en bloques con <pre>
                inicio = 0
                while inicio < len(texto_extraido):
                    fin = min(inicio + 3500, len(texto_extraido))
                    bloque = texto_extraido[inicio:fin]

                    # No cortar palabras a la mitad
                    if fin < len(texto_extraido):
                        ultimo_espacio = bloque.rfind(' ')
                        if ultimo_espacio > 0:
                            bloque = bloque[:ultimo_espacio]

                    self._send_message(
                        chat_id,
                        f"<pre>{bloque}</pre>",
                        parse_mode="HTML"
                    )
                    inicio += len(bloque)

            logger.info(f"✅ Texto OCR enviado a chat {chat_id} ({num_palabras} palabras)")

        except Exception as e:
            logger.error(f"❌ Error enviando texto OCR: {e}")
            self._send_message(chat_id, f"❌ Error mostrando el texto: {str(e)}")
            # Fallback: enviar como archivo
            try:
                self._send_document(chat_id, output_path)
            except:
                pass