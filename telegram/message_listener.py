import os
import uuid
import logging
import requests
from typing import Dict, Any, Optional, Set

logger = logging.getLogger("AgentEagle.TelegramMessageListener")


class TelegramMessageListener:
    def __init__(
            self,
            event_bus,
            bot_token: str,
            allowed_chat_ids: Set[str],
            supported_formats: list,
            max_file_size_mb: int = 20,
            command_handler=None
    ):
        self.event_bus = event_bus
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.allowed_chat_ids = allowed_chat_ids
        self.supported_formats = [f.lower() for f in supported_formats]
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.command_handler = command_handler

        logger.info(f"TelegramMessageListener inicializado. Formatos: {self.supported_formats}")

    def start(self) -> None:
        logger.info("ℹ️  TelegramMessageListener: polling delegado a UnifiedTelegramListener")

    def stop(self) -> None:
        logger.info("ℹ️  TelegramMessageListener: sin recursos que liberar")

    def handle_message(self, message: Dict[str, Any]) -> None:
        self._handle_message(message)

    def handle_callback(self, callback_query: Dict[str, Any]) -> None:
        """Maneja callbacks de comandos (cmd:doc, cmd:print, etc.)"""
        callback_data = callback_query.get('data', '')

        if not callback_data.startswith('cmd:'):
            return

        if not self.command_handler:
            return

        message = callback_query.get('message', {})
        chat_id = str(message.get('chat', {}).get('id', ''))
        callback_id = callback_query.get('id', '')

        command = callback_data.replace('cmd:', '')

        logger.info(f"📨 [MessageListener] Callback de comando procesado: {command} para chat {chat_id}")

        # 🆕 Mapeo actualizado con smart_convert
        mode_mapping = {
            'doc': 'analyze',
            'process': 'analyze',
            'pay': 'print',
            'payment': 'print',
            'print': 'print',
            'imprimir': 'print',
            'pdf2word': 'pdf2word',
            'word2pdf': 'word2pdf',
            'ocr': 'ocr',
            'texto': 'ocr',
            'smart_convert': 'smart_reconstruct',  # 🆕
            'reconstruir': 'smart_reconstruct',  # 🆕
            'status': None,
            'printers': None,
            'help': None,
        }

        new_mode = mode_mapping.get(command)
        if new_mode:
            self.command_handler.set_chat_mode(chat_id, new_mode)
            logger.info(f"✅ Modo de chat {chat_id} actualizado a: {new_mode}")

        try:
            requests.post(
                f"{self.base_url}/answerCallbackQuery",
                json={
                    "callback_query_id": callback_id,
                    "text": f"Ejecutando /{command}",
                    "show_alert": False
                },
                timeout=5
            )
        except Exception as e:
            logger.error(f"Error respondiendo callback: {e}")

        handler_method = self.command_handler.commands.get(command)
        if handler_method:
            try:
                handler_method(chat_id, '', callback_query)
            except Exception as e:
                logger.error(f"Error ejecutando comando desde callback: {e}", exc_info=True)

    def _handle_message(self, message: Dict[str, Any]) -> None:
        chat = message.get('chat', {})
        chat_id = str(chat.get('id', ''))
        from_user = message.get('from', {})
        user_id = from_user.get('id')
        username = from_user.get('username', 'unknown')
        message_id = message.get('message_id')
        caption = message.get('caption', '').strip()

        if chat_id not in self.allowed_chat_ids:
            logger.debug(f"Mensaje ignorado de chat no autorizado: {chat_id}")
            return

        text = message.get('text', '')
        if text and text.strip().startswith('/'):
            if self.command_handler:
                is_command = self.command_handler.handle_command(message)
                if is_command:
                    return

        document = message.get('document')
        if document:
            self._handle_document(document, chat_id, user_id, username, message_id, caption)
            return

        photo = message.get('photo')
        if photo:
            best_photo = max(photo, key=lambda p: p.get('file_size', 0))
            self._handle_photo(best_photo, chat_id, user_id, username, message_id, caption)
            return

    def _handle_document(self, document: Dict, chat_id: str, user_id: int,
                         username: str, message_id: int, caption: str = "") -> None:
        file_id = document.get('file_id')
        file_name = document.get('file_name', 'documento')
        mime_type = document.get('mime_type', '')
        file_size = document.get('file_size', 0)

        if file_size > self.max_file_size_bytes:
            self._send_message(chat_id, f"❌ Archivo demasiado grande ({file_size / 1024 / 1024:.1f} MB).")
            return

        extension = os.path.splitext(file_name)[1].lower().lstrip('.')
        if extension not in self.supported_formats:
            self._send_message(chat_id, f"❌ Formato no soportado: .{extension}")
            return

        job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"

        mode = 'print'
        if self.command_handler:
            mode = self.command_handler.get_chat_mode(chat_id)

        logger.info(f"📄 Documento recibido: {file_name} | Modo: {mode} | Caption: '{caption}'")

        # 🆕 Validación para smart_reconstruct
        if mode == 'smart_reconstruct' and extension != 'pdf':
            self._send_message(chat_id,
                               "❌ Este modo requiere un archivo <b>PDF</b>.\n\nUsa /smart_convert y envía un PDF.")
            return

        if mode == 'pdf2word' and extension != 'pdf':
            self._send_message(chat_id, "❌ Este modo requiere un archivo <b>PDF</b>.\n\nUsa /pdf2word y envía un PDF.")
            return

        if mode == 'word2pdf' and extension != 'docx':
            self._send_message(chat_id,
                               "❌ Este modo requiere un archivo <b>Word (DOCX)</b>.\n\nUsa /word2pdf y envía un DOCX.")
            return

        if mode == 'ocr' and extension not in ['pdf', 'png', 'jpg', 'jpeg', 'bmp', 'tiff']:
            self._send_message(chat_id, "❌ Este modo requiere una <b>imagen</b> o <b>PDF escaneado</b>.")
            return

        # 🆕 Determinar evento según modo (incluye smart_reconstruct)
        if mode == 'smart_reconstruct':
            event_type = 'conversion.pdf_to_word_smart'
            self._send_message(chat_id,
                               f"📥 <b>PDF recibido</b>\n\n🧠 <b>Reconstruyendo diseño lógico...</b>\n🆔 <b>Job:</b> <code>{job_id}</code>")
        elif mode == 'ocr':
            if extension == 'pdf':
                event_type = 'conversion.ocr_pdf'
                self._send_message(chat_id,
                                   f" <b>PDF recibido</b>\n\n <b>Extrayendo texto con OCR...</b>\n🆔 <b>Job:</b> <code>{job_id}</code>")
            else:
                event_type = 'conversion.ocr_image'
                self._send_message(chat_id,
                                   f"🖼️ <b>Imagen recibida</b>\n\n🔍 <b>Extrayendo texto con OCR...</b>\n🆔 <b>Job:</b> <code>{job_id}</code>")
        elif mode == 'pdf2word':
            event_type = 'conversion.pdf_to_word'
            self._send_message(chat_id,
                               f"📥 <b>PDF recibido</b>\n\n🔄 <b>Convirtiendo PDF → Word...</b>\n🆔 <b>Job:</b> <code>{job_id}</code>")
        elif mode == 'word2pdf':
            event_type = 'conversion.word_to_pdf'
            self._send_message(chat_id,
                               f"📥 <b>DOCX recibido</b>\n\n🔄 <b>Convirtiendo Word → PDF...</b>\n <b>Job:</b> <code>{job_id}</code>")
        elif mode == 'analyze':
            event_type = 'document.analysis_requested'
            self._send_message(chat_id,
                               f" <b>Documento recibido</b>\n\n <b>Analizando con IA (sin imprimir)...</b>\n🆔 <b>Job:</b> <code>{job_id}</code>")
        else:  # print
            event_type = 'document.received'
            if caption:
                self._send_message(chat_id,
                                   f"📥 <b>Documento recibido</b>\n\n📝 <b>Instrucciones:</b> <code>{caption}</code>\n🆔 <b>Job:</b> <code>{job_id}</code>\n\n🖨️ <b>Analizando para imprimir...</b>")
            else:
                self._send_message(chat_id,
                                   f"📥 <b>Documento recibido</b>\n\n🆔 <b>Job:</b> <code>{job_id}</code>\n\n🖨️ <b>Analizando para imprimir...</b>")

        self.event_bus.publish(event_type, {
            "job_id": job_id,
            "print_job_id": job_id,
            "telegram_chat_id": chat_id,
            "telegram_message_id": message_id,
            "telegram_user_id": user_id,
            "telegram_username": username,
            "file_id": file_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "file_size": file_size,
            "extension": extension,
            "caption": caption,
            "source": "telegram_listener"
        })

    def _handle_photo(self, photo: Dict, chat_id: str, user_id: int,
                      username: str, message_id: int, caption: str = "") -> None:
        file_id = photo.get('file_id')
        file_size = photo.get('file_size', 0)

        if file_size > self.max_file_size_bytes:
            self._send_message(chat_id, f"❌ Imagen demasiado grande ({file_size / 1024 / 1024:.1f} MB)")
            return

        job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
        file_name = f"photo_{job_id}.jpg"

        mode = 'print'
        if self.command_handler:
            mode = self.command_handler.get_chat_mode(chat_id)

        if mode == 'ocr':
            event_type = 'conversion.ocr_image'
            self._send_message(chat_id,
                               f"🖼️ <b>Imagen recibida</b>\n\n <b>Extrayendo texto con OCR...</b>\n🆔 <b>Job:</b> <code>{job_id}</code>")
        elif mode == 'analyze':
            event_type = 'document.analysis_requested'
            self._send_message(chat_id,
                               f"🖼️ <b>Imagen recibida</b>\n\n🔍 <b>Analizando...</b>\n🆔 <b>Job:</b> <code>{job_id}</code>")
        else:
            event_type = 'document.received'
            self._send_message(chat_id,
                               f"🖼️ <b>Imagen recibida</b>\n\n🖨️ <b>Analizando para imprimir...</b>\n🆔 <b>Job:</b> <code>{job_id}</code>")

        self.event_bus.publish(event_type, {
            "job_id": job_id,
            "print_job_id": job_id,
            "telegram_chat_id": chat_id,
            "telegram_message_id": message_id,
            "telegram_user_id": user_id,
            "telegram_username": username,
            "photo_file_id": file_id,
            "caption": caption,
            "source": "telegram_listener"
        })

    def _send_message(self, chat_id: str, text: str) -> None:
        try:
            requests.post(f"{self.base_url}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                          timeout=10)
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")