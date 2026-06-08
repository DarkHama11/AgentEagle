import os
import yaml
import logging
from typing import Dict, Any, List, Optional
from agents.base_agent import BaseAgent
from event_bus.event import Event
from services.notification_service import BaseNotificationService
from services.telegram_service import TelegramService
from services.message_template_service import MessageTemplateService

logger = logging.getLogger("AgentEagle.NotificationAgent")


class NotificationAgent(BaseAgent):
    name = "notification_agent"
    description = "Agente reactivo que envía notificaciones por Telegram, Email, Slack, etc."
    capabilities = ["send_telegram", "send_notification", "handle_event"]

    SUBSCRIBED_EVENTS = [
        "document.processed", "document.failed", "pipeline.completed", "pipeline.failed",
        "payment.waiting_human", "payment.completed", "payment.failed",
        "approval.required", "approval.approved", "approval.rejected"
    ]

    def __init__(self, event_bus=None, state_manager=None, config_path: Optional[str] = None, approval_manager=None):
        super().__init__(event_bus)
        self.state_manager = state_manager
        self.approval_manager = approval_manager

        self._setup_logging()
        self.config = self._load_config(config_path)
        self.template_service = MessageTemplateService(format_type="HTML")
        self.notification_services: List[BaseNotificationService] = []

        # Canal de aprobaciones (se inicializa en _initialize_channels)
        self.telegram_approval_channel = None

        self._initialize_channels()

        if self.event_bus:
            self._subscribe_to_events()

        logger.info(f"NotificationAgent inicializado con {len(self.notification_services)} canales activos")

    def _setup_logging(self) -> None:
        if logger.handlers:
            return
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        logs_dir = os.path.join(base_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        log_file = os.path.join(logs_dir, "notification_agent.log")
        file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(base_dir, "config", "notifications.yaml")
        if not os.path.exists(config_path):
            logger.warning(f"Config no encontrada: {config_path}")
            return {}
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            return {}

    def _initialize_channels(self) -> None:
        telegram_config = self.config.get('telegram', {})

        if not telegram_config.get('enabled', False):
            logger.warning("⚠️ Telegram no está habilitado en la configuración")
            return

        bot_token = telegram_config.get('bot_token', '')
        chat_id = telegram_config.get('chat_id', '')

        if not bot_token or not chat_id:
            logger.error("❌ Falta bot_token o chat_id en la configuración de Telegram")
            return

        # 1. Canal de notificaciones (mensajes simples)
        try:
            telegram_service = TelegramService(
                bot_token=bot_token,
                chat_id=chat_id,
                parse_mode=telegram_config.get('parse_mode', 'HTML'),
                disable_notification=telegram_config.get('disable_notification', False)
            )
            self.notification_services.append(telegram_service)
            logger.info("✅ Canal Telegram (notificaciones) habilitado")
        except Exception as e:
            logger.error(f"❌ Error inicializando TelegramService: {e}", exc_info=True)

        # 2. Canal de aprobaciones interactivas (botones inline)
        if self.approval_manager:
            try:
                from approval_channels.telegram_channel import TelegramApprovalChannel

                self.telegram_approval_channel = TelegramApprovalChannel(
                    approval_manager=self.approval_manager,
                    bot_token=bot_token,
                    default_chat_id=chat_id,
                    config_path=None
                )
                logger.info("✅ Canal Telegram (aprobaciones interactivas) habilitado")
            except Exception as e:
                logger.error(f"❌ Error inicializando TelegramApprovalChannel: {e}", exc_info=True)
                self.telegram_approval_channel = None
        else:
            logger.warning("⚠️ ApprovalManager no proporcionado. Canal de aprobaciones deshabilitado.")

    def _subscribe_to_events(self) -> None:
        for event_type in self.SUBSCRIBED_EVENTS:
            self.event_bus.subscribe(event_type, self.handle_event)

    def handle_event(self, event: Event) -> None:
        logger.info(f"📨 Evento recibido: {event.event_type} de {event.source}")
        try:
            # Para approval.required, usar canal interactivo con botones
            if event.event_type == "approval.required" and self.telegram_approval_channel:
                result = self.telegram_approval_channel.send_approval_request(
                    approval_id=event.payload.get('approval_id'),
                    job_id=event.payload.get('job_id'),
                    pipeline_name=event.payload.get('pipeline_name'),
                    title=event.payload.get('title'),
                    description=event.payload.get('description'),
                    payload=event.payload.get('payload', {})
                )
                logger.info(f"✅ Solicitud de aprobación enviada con botones inline: {result}")
                return

            # Para otros eventos, usar el flujo normal de plantillas
            template_func = self.template_service.get_template(event.event_type)
            message = template_func(event.payload)
            self.send_notification(message, event.event_type, event.payload)
        except Exception as e:
            logger.error(f"❌ Error manejando evento {event.event_type}: {e}", exc_info=True)

    def send_notification(self, message: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        results = {}
        for service in self.notification_services:
            try:
                result = service.send(message)
                results[service.channel_name] = result
                logger.info(
                    f"📤 Notificación enviada | Canal: {service.channel_name} | Evento: {event_type} | Status: {result.get('status')}")
            except Exception as e:
                logger.error(f"❌ Error enviando por {service.channel_name}: {e}")
                results[service.channel_name] = {"status": "error", "error": str(e)}
        return results

    def execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if action == "send_notification":
            return {"status": "success",
                    "results": self.send_notification(payload.get('message', ''), "manual", payload)}
        elif action == "send_telegram":
            return {"status": "success", "result": self.send_telegram(payload.get('message', ''))}
        elif action == "test_connection":
            return {"status": "success",
                    "results": {s.channel_name: s.test_connection() for s in self.notification_services}}
        return {"status": "error", "result": f"Acción '{action}' no soportada"}

    def send_telegram(self, message: str, **kwargs) -> Dict[str, Any]:
        for service in self.notification_services:
            if service.channel_name == "telegram":
                return service.send(message, **kwargs)
        return {"status": "disabled", "message": "Telegram no está configurado"}