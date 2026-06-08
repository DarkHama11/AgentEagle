import os
import json
import logging
import threading
import requests
import yaml
from typing import Dict, Any, Optional, Set
from datetime import datetime, timezone
from .base_channel import BaseApprovalChannel

logger = logging.getLogger("AgentEagle.TelegramApprovalChannel")


class TelegramApprovalChannel(BaseApprovalChannel):
    """
    Canal de aprobación interactivo vía Telegram.
    Maneja:
    - Aprobaciones de pipeline (approve:/reject:)
    - Aprobaciones de impresión (print_approve:/print_reject:)
    - Callbacks de comandos del menú (cmd:) - solo muestra mensaje informativo
    """

    def __init__(self, approval_manager, bot_token: str, default_chat_id: str,
                 config_path: Optional[str] = None):
        self.approval_manager = approval_manager
        self.bot_token = bot_token
        self.default_chat_id = default_chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

        self._lock = threading.RLock()
        self._message_registry: Dict[str, Dict[str, Any]] = {}
        self._authorized_chat_ids: Set[str] = set()

        self._load_config(config_path)
        self._setup_audit_logging()

        logger.info(f"TelegramApprovalChannel inicializado. Usuarios autorizados: {len(self._authorized_chat_ids)}")

    def _load_config(self, config_path: Optional[str]) -> None:
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "notifications.yaml")

        if not os.path.exists(config_path):
            self._authorized_chat_ids = {str(self.default_chat_id)}
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            telegram_config = config.get('telegram', {})
            approval_ids = telegram_config.get('approval_chat_ids', [])
            self._authorized_chat_ids = {str(self.default_chat_id)}
            for chat_id in approval_ids:
                self._authorized_chat_ids.add(str(chat_id))
        except Exception as e:
            logger.error(f"Error cargando config: {e}")
            self._authorized_chat_ids = {str(self.default_chat_id)}

    def _setup_audit_logging(self) -> None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logs_dir = os.path.join(base_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        self.audit_logger = logging.getLogger("AgentEagle.TelegramApprovals.Audit")
        self.audit_logger.setLevel(logging.INFO)
        self.audit_logger.propagate = False

        if not self.audit_logger.handlers:
            audit_file = os.path.join(logs_dir, "telegram_approvals_audit.jsonl")
            handler = logging.FileHandler(audit_file, encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.audit_logger.addHandler(handler)

    def _log_audit(self, approval_id: str, action: str, telegram_user: str,
                   telegram_user_id: Any, extra: Optional[Dict] = None) -> None:
        entry = {
            "approval_id": approval_id,
            "action": action,
            "telegram_user": telegram_user,
            "telegram_user_id": telegram_user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel": "telegram"
        }
        if extra:
            entry.update(extra)
        self.audit_logger.info(json.dumps(entry, ensure_ascii=False))

    @property
    def channel_name(self) -> str:
        return "telegram"

    def is_user_authorized(self, user_id: Any) -> bool:
        return str(user_id) in self._authorized_chat_ids

    # ============================================================
    # MÉTODOS DE ENVÍO
    # ============================================================

    def send_approval_request(self, approval_id: str, job_id: str, pipeline_name: str,
                              title: str, description: str, payload: Dict[str, Any],
                              chat_id: Optional[str] = None) -> Dict[str, Any]:
        target_chat_id = chat_id or self.default_chat_id
        doc_type = payload.get('document_type', 'N/A')
        amount = payload.get('amount', 'N/A')
        supplier = payload.get('supplier', 'N/A')

        message_text = (
            f"⚠️ <b>APROBACIÓN REQUERIDA</b>\n\n"
            f"📋 <b>Título:</b> {title}\n"
            f"📝 <b>Descripción:</b> {description}\n\n"
            f"🔄 <b>Pipeline:</b> {pipeline_name}\n"
            f"🆔 <b>Job:</b> <code>{job_id}</code>\n"
            f"🔑 <b>Approval:</b> <code>{approval_id}</code>\n\n"
            f"📦 <b>Detalles:</b>\n"
            f"  • Tipo: {doc_type}\n"
            f"  • Proveedor: {supplier}\n"
            f"  • Monto: {amount}\n\n"
            f"👇 <b>Selecciona una acción:</b>"
        )

        inline_keyboard = {"inline_keyboard": [[
            {"text": "✅ Aprobar", "callback_data": f"approve:{approval_id}"},
            {"text": "❌ Rechazar", "callback_data": f"reject:{approval_id}"}
        ]]}

        try:
            response = requests.post(f"{self.base_url}/sendMessage", json={
                "chat_id": target_chat_id,
                "text": message_text,
                "parse_mode": "HTML",
                "reply_markup": inline_keyboard
            }, timeout=10)
            response.raise_for_status()
            result = response.json()

            if result.get('ok'):
                message_id = result['result']['message_id']
                with self._lock:
                    self._message_registry[approval_id] = {
                        "chat_id": target_chat_id,
                        "message_id": message_id
                    }

                self._log_audit(approval_id, "request_sent", "system", 0,
                                {"chat_id": target_chat_id, "message_id": message_id})

                return {
                    "status": "success",
                    "chat_id": target_chat_id,
                    "message_id": message_id,
                    "channel": "telegram"
                }
            return {"status": "error", "error": result.get('description', 'Error desconocido')}
        except Exception as e:
            logger.error(f"Error enviando solicitud: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def update_message_approved(self, chat_id: str, message_id: int,
                                approval_id: str, resolved_by: str) -> bool:
        new_text = (
            f"✅ <b>APROBADO</b>\n\n"
            f"🔑 <b>Approval:</b> <code>{approval_id}</code>\n"
            f"👤 <b>Usuario:</b> {resolved_by}\n"
            f"🕐 <b>Hora:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self._edit_message(chat_id, message_id, new_text)

    def update_message_rejected(self, chat_id: str, message_id: int,
                                approval_id: str, resolved_by: str) -> bool:
        new_text = (
            f"❌ <b>RECHAZADO</b>\n\n"
            f"🔑 <b>Approval:</b> <code>{approval_id}</code>\n"
            f"👤 <b>Usuario:</b> {resolved_by}\n"
            f"🕐 <b>Hora:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self._edit_message(chat_id, message_id, new_text)

    def _edit_message(self, chat_id: str, message_id: int, new_text: str) -> bool:
        try:
            response = requests.post(f"{self.base_url}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": new_text,
                "parse_mode": "HTML"
            }, timeout=10)
            return response.status_code == 200 and response.json().get('ok', False)
        except Exception as e:
            logger.error(f"Error editando mensaje: {e}")
            return False

    # ============================================================
    # MÉTODOS DE POLLING (DELEGADOS)
    # ============================================================

    def start(self) -> None:
        logger.info("ℹ️  TelegramApprovalChannel: polling delegado a UnifiedTelegramListener")

    def stop(self) -> None:
        logger.info("ℹ️  TelegramApprovalChannel: sin recursos que liberar")

    # ============================================================
    # ROUTER PRINCIPAL DE CALLBACKS
    # ============================================================

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """Router principal que distribuye callbacks según su tipo."""
        callback_data = callback_query.get('data', '')

        # Callbacks de comandos del menú (manejado por MessageListener, pero damos fallback)
        if callback_data.startswith('cmd:'):
            self._handle_command_callback(callback_query)
            return

        # Callbacks de aprobación de impresión
        if callback_data.startswith('print_approve:') or callback_data.startswith('print_reject:'):
            self._handle_print_callback(callback_query)
            return

        # Callbacks de aprobación de pipeline
        self._handle_callback_query(callback_query)

    # ============================================================
    # 🆕 CALLBACKS DE COMANDOS DEL MENÚ (FALLBACK)
    # ============================================================

    def _handle_command_callback(self, callback_query: Dict[str, Any]) -> None:
        """
        Fallback para callbacks de comandos.
        El manejo real lo hace TelegramMessageListener.handle_callback
        que actualiza el modo del chat. Este método solo muestra un mensaje informativo.
        """
        try:
            callback_data = callback_query.get('data', '')
            message = callback_query.get('message', {})
            chat_id = message.get('chat', {}).get('id')

            command = callback_data.replace('cmd:', '')

            command_messages = {
                "doc": "🔍 <b>Modo Solo Análisis</b>\n\nEnvía un archivo para analizar con IA (sin imprimir).",
                "pay": "💰 <b>Modo Pago con Aprobación</b>\n\nEnvía una factura para procesar con aprobación.",
                "print": "🖨️ <b>Modo Smart Print</b>\n\nEnvía un archivo para imprimir con IA.\n💡 Usa caption como <code>2</code> o <code>3 finance</code>",
                "pdf2word": "🔄 <b>Modo PDF → Word</b>\n\nEnvía un archivo PDF y lo convertiré a Word (DOCX).",
                "word2pdf": "🔄 <b>Modo Word → PDF</b>\n\nEnvía un archivo Word (DOCX) y lo convertiré a PDF.",
                "ocr": "🔍 <b>Modo OCR</b>\n\nEnvía una imagen o PDF escaneado y extraeré el texto.",
                "status": "📊 <b>Estado del Sistema</b>\n\nUsa <code>/status</code> para ver el estado completo.",
                "printers": "🖨️ <b>Impresoras</b>\n\nUsa <code>/printers</code> para ver la lista completa.",
                "help": "❓ <b>Ayuda</b>\n\nUsa <code>/help</code> para ver la guía completa."
            }

            text = command_messages.get(command, f"❓ Comando no reconocido: <code>{command}</code>")

            self._answer_callback(callback_query.get('id'), f"Ejecutando /{command}")

            if chat_id:
                requests.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML"
                    },
                    timeout=10
                )

            logger.info(f"📨 Command callback procesado (fallback): {command}")

        except Exception as e:
            logger.error(f"Error en command callback: {e}", exc_info=True)

    # ============================================================
    # CALLBACKS DE APROBACIÓN DE IMPRESIÓN
    # ============================================================

    def _handle_print_callback(self, callback_query: Dict[str, Any]) -> None:
        try:
            callback_data = callback_query.get('data', '')
            from_user = callback_query.get('from', {})
            user_id = from_user.get('id')
            username = from_user.get('username', 'unknown')
            first_name = from_user.get('first_name', 'unknown')
            message = callback_query.get('message', {})
            chat_id = message.get('chat', {}).get('id')
            message_id = message.get('message_id')

            logger.info(f"📨 Print callback recibido: '{callback_data}' de @{username}")

            if ':' not in callback_data:
                self._answer_callback(callback_query.get('id'), "❌ Callback inválido", show_alert=True)
                return

            action, approval_id = callback_data.split(':', 1)
            user_display = f"@{username}" if username != 'unknown' else first_name

            if not self.is_user_authorized(user_id):
                logger.warning(f"⚠️ Usuario NO autorizado intentó aprobar impresión: @{username}")
                self._answer_callback(callback_query.get('id'), "🚫 No autorizado", show_alert=True)
                self._log_audit(approval_id, "print_unauthorized_attempt", f"@{username}", user_id)
                return

            if action == "print_approve":
                self._process_print_approval(approval_id, user_display, user_id, chat_id, message_id,
                                             callback_query.get('id'))
            elif action == "print_reject":
                self._process_print_rejection(approval_id, user_display, user_id, chat_id, message_id,
                                              callback_query.get('id'))
            else:
                self._answer_callback(callback_query.get('id'), f"❌ Acción desconocida: {action}", show_alert=True)
        except Exception as e:
            logger.error(f"Error en print callback: {e}", exc_info=True)

    def _process_print_approval(self, approval_id: str, user_display: str, user_id: Any,
                                chat_id: Any, message_id: int, callback_id: str) -> None:
        try:
            if chat_id and message_id:
                new_text = (
                    f"✅ <b>IMPRESIÓN APROBADA</b>\n\n"
                    f"🔑 <b>Aprobación:</b> <code>{approval_id}</code>\n"
                    f"👤 <b>Usuario:</b> {user_display}\n"
                    f"🕐 <b>Hora:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"⏳ Iniciando impresión..."
                )
                self._edit_message(chat_id, message_id, new_text)

            self._answer_callback(callback_id, "✅ Impresión aprobada", show_alert=False)

            if self.approval_manager and self.approval_manager.event_bus:
                from event_bus.event import Event
                self.approval_manager.event_bus.publish(Event(
                    event_type="print.approval_response",
                    source="telegram_approval_channel",
                    payload={
                        "approval_id": approval_id,
                        "action": "approved",
                        "resolved_by": user_display
                    }
                ))

            self._log_audit(approval_id, "print_approved", user_display, user_id,
                            {"chat_id": chat_id, "message_id": message_id})

            logger.info(f"✅ Impresión aprobada: {approval_id} por {user_display}")
        except Exception as e:
            logger.error(f"Error aprobando impresión: {e}", exc_info=True)
            self._answer_callback(callback_id, f"❌ Error: {str(e)}", show_alert=True)

    def _process_print_rejection(self, approval_id: str, user_display: str, user_id: Any,
                                 chat_id: Any, message_id: int, callback_id: str) -> None:
        try:
            if chat_id and message_id:
                new_text = (
                    f"❌ <b>IMPRESIÓN CANCELADA</b>\n\n"
                    f"🔑 <b>Aprobación:</b> <code>{approval_id}</code>\n"
                    f"👤 <b>Usuario:</b> {user_display}\n"
                    f"🕐 <b>Hora:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                self._edit_message(chat_id, message_id, new_text)

            self._answer_callback(callback_id, "❌ Impresión cancelada", show_alert=False)

            if self.approval_manager and self.approval_manager.event_bus:
                from event_bus.event import Event
                self.approval_manager.event_bus.publish(Event(
                    event_type="print.approval_response",
                    source="telegram_approval_channel",
                    payload={
                        "approval_id": approval_id,
                        "action": "rejected",
                        "resolved_by": user_display
                    }
                ))

            self._log_audit(approval_id, "print_rejected", user_display, user_id,
                            {"chat_id": chat_id, "message_id": message_id})

            logger.info(f"❌ Impresión rechazada: {approval_id} por {user_display}")
        except Exception as e:
            logger.error(f"Error rechazando impresión: {e}", exc_info=True)
            self._answer_callback(callback_id, f"❌ Error: {str(e)}", show_alert=True)

    # ============================================================
    # CALLBACKS DE APROBACIÓN DE PIPELINE
    # ============================================================

    def _handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        try:
            callback_data = callback_query.get('data', '')
            from_user = callback_query.get('from', {})
            user_id = from_user.get('id')
            username = from_user.get('username', 'unknown')
            first_name = from_user.get('first_name', 'unknown')
            message = callback_query.get('message', {})
            chat_id = message.get('chat', {}).get('id')
            message_id = message.get('message_id')

            logger.info(f"📨 Callback recibido: '{callback_data}' de @{username} (ID: {user_id})")

            if ':' not in callback_data:
                self._answer_callback(callback_query.get('id'), "❌ Callback inválido", show_alert=True)
                return

            action, approval_id = callback_data.split(':', 1)
            user_display = f"@{username}" if username != 'unknown' else first_name

            if not self.is_user_authorized(user_id):
                logger.warning(f"⚠️ Usuario NO autorizado: @{username} (ID: {user_id})")
                self._answer_callback(callback_query.get('id'), "🚫 No estás autorizado para aprobar", show_alert=True)
                self._log_audit(approval_id, "unauthorized_attempt", f"@{username}", user_id)
                return

            if action == "approve":
                self._process_approval(approval_id, user_display, user_id, chat_id, message_id,
                                       callback_query.get('id'))
            elif action == "reject":
                self._process_rejection(approval_id, user_display, user_id, chat_id, message_id,
                                        callback_query.get('id'))
            else:
                self._answer_callback(callback_query.get('id'), f"❌ Acción desconocida: {action}", show_alert=True)
        except Exception as e:
            logger.error(f"Error manejando callback: {e}", exc_info=True)

    def _process_approval(self, approval_id: str, user_display: str, user_id: Any,
                          chat_id: Any, message_id: int, callback_id: str) -> None:
        try:
            self.approval_manager.approve(
                approval_id=approval_id,
                resolved_by=f"telegram:{user_display}",
                notes=f"Aprobado desde Telegram por {user_display}"
            )
            if chat_id and message_id:
                self.update_message_approved(chat_id, message_id, approval_id, user_display)
            self._answer_callback(callback_id, "✅ Aprobación completada", show_alert=False)
            self._log_audit(approval_id, "approved", user_display, user_id,
                            {"chat_id": chat_id, "message_id": message_id})
            logger.info(f"✅ Aprobación procesada: {approval_id} por {user_display}")
        except Exception as e:
            logger.error(f"Error aprobando {approval_id}: {e}", exc_info=True)
            self._answer_callback(callback_id, f"❌ Error: {str(e)}", show_alert=True)

    def _process_rejection(self, approval_id: str, user_display: str, user_id: Any,
                           chat_id: Any, message_id: int, callback_id: str) -> None:
        try:
            self.approval_manager.reject(
                approval_id=approval_id,
                resolved_by=f"telegram:{user_display}",
                notes=f"Rechazado desde Telegram por {user_display}"
            )
            if chat_id and message_id:
                self.update_message_rejected(chat_id, message_id, approval_id, user_display)
            self._answer_callback(callback_id, "❌ Solicitud rechazada", show_alert=False)
            self._log_audit(approval_id, "rejected", user_display, user_id,
                            {"chat_id": chat_id, "message_id": message_id})
            logger.info(f"❌ Rechazo procesado: {approval_id} por {user_display}")
        except Exception as e:
            logger.error(f"Error rechazando {approval_id}: {e}", exc_info=True)
            self._answer_callback(callback_id, f"❌ Error: {str(e)}", show_alert=True)

    def _answer_callback(self, callback_query_id: str, text: str, show_alert: bool = False) -> None:
        try:
            requests.post(f"{self.base_url}/answerCallbackQuery", json={
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": show_alert
            }, timeout=5)
        except Exception:
            pass