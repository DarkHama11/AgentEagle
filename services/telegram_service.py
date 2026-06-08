import logging
import requests
from typing import Dict, Any, Optional
from .notification_service import BaseNotificationService

logger = logging.getLogger("AgentEagle.TelegramService")


class TelegramService(BaseNotificationService):
    def __init__(self, bot_token: str, chat_id: str, parse_mode: str = "HTML", disable_notification: bool = False):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.parse_mode = parse_mode
        self.disable_notification = disable_notification
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self._enabled = True
        logger.info(f"TelegramService inicializado para chat_id: {chat_id}")

    @property
    def channel_name(self) -> str:
        return "telegram"

    def is_enabled(self) -> bool:
        return self._enabled and bool(self.bot_token) and bool(self.chat_id)

    def send(self, message: str, **kwargs) -> Dict[str, Any]:
        if not self.is_enabled():
            return {"status": "disabled", "message": "Telegram no está configurado"}

        chat_id = kwargs.get('chat_id', self.chat_id)
        parse_mode = kwargs.get('parse_mode', self.parse_mode)

        try:
            response = requests.post(f"{self.base_url}/sendMessage", json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_notification": self.disable_notification
            }, timeout=10)
            response.raise_for_status()
            result = response.json()

            if result.get('ok'):
                message_id = result.get('result', {}).get('message_id')
                logger.info(f"✅ Mensaje enviado a Telegram. ID: {message_id}")
                return {"status": "success", "message_id": message_id, "channel": "telegram", "chat_id": chat_id}
            return {"status": "error", "channel": "telegram", "error": result.get('description', 'Error desconocido')}
        except Exception as e:
            logger.error(f"❌ Error enviando a Telegram: {e}")
            return {"status": "error", "channel": "telegram", "error": str(e)}

    def send_with_inline_keyboard(self, chat_id: str, text: str, inline_keyboard: Dict[str, Any],
                                  parse_mode: str = "HTML") -> Dict[str, Any]:
        if not self.is_enabled():
            return {"status": "disabled"}
        try:
            response = requests.post(f"{self.base_url}/sendMessage", json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "reply_markup": inline_keyboard
            }, timeout=10)
            response.raise_for_status()
            result = response.json()
            if result.get('ok'):
                return {"status": "success", "message_id": result['result']['message_id'], "channel": "telegram"}
            return {"status": "error", "error": result.get('description')}
        except Exception as e:
            logger.error(f"Error enviando mensaje con inline keyboard: {e}")
            return {"status": "error", "error": str(e)}

    def test_connection(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/getMe", timeout=5)
            response.raise_for_status()
            return response.json().get('ok', False)
        except Exception:
            return False