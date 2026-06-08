import logging
import threading
import time
import requests
from typing import Dict, Any, Optional, Set, Callable, List

logger = logging.getLogger("AgentEagle.UnifiedTelegramListener")


class UnifiedTelegramListener:
    """
    Listener unificado que procesa TODOS los updates de Telegram en un solo hilo.
    Maneja tanto callback_query (botones) como messages (documentos).
    Evita el error 409 Conflict de Telegram.
    """

    def __init__(
            self,
            bot_token: str,
            allowed_chat_ids: Set[str],
            poll_interval: int = 2
    ):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.allowed_chat_ids = allowed_chat_ids
        self.poll_interval = poll_interval

        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._last_update_id = 0
        self._lock = threading.RLock()

        # Handlers registrados
        self._callback_handlers: List[Callable] = []  # Para callback_query (botones)
        self._message_handlers: List[Callable] = []  # Para messages (documentos)

        self._initialize_offset()

        logger.info(f"UnifiedTelegramListener inicializado. Chats autorizados: {len(allowed_chat_ids)}")

    def _initialize_offset(self) -> None:
        try:
            response = requests.post(
                f"{self.base_url}/getUpdates",
                json={"offset": -1, "timeout": 0},
                timeout=5
            )
            if response.status_code == 200:
                result = response.json().get('result', [])
                if result:
                    self._last_update_id = result[-1].get('update_id', 0)
                    logger.info(f"Offset inicializado en: {self._last_update_id}")
        except Exception as e:
            logger.debug(f"No se pudo inicializar offset: {e}")

    def register_callback_handler(self, handler: Callable[[Dict], None]) -> None:
        """Registra un handler para callback_query (botones inline)."""
        self._callback_handlers.append(handler)
        logger.info(f"Handler de callbacks registrado: {handler.__name__}")

    def register_message_handler(self, handler: Callable[[Dict], None]) -> None:
        """Registra un handler para messages (documentos, fotos, texto)."""
        self._message_handlers.append(handler)
        logger.info(f"Handler de mensajes registrado: {handler.__name__}")

    def start(self) -> None:
        if self._running:
            logger.warning("UnifiedTelegramListener ya está corriendo")
            return

        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            name="UnifiedTelegramListener",
            daemon=True
        )
        self._poll_thread.start()
        logger.info("✅ UnifiedTelegramListener iniciado")

    def stop(self) -> None:
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=5)
        logger.info("🛑 UnifiedTelegramListener detenido")

    def _poll_loop(self) -> None:
        logger.info("Iniciando loop de polling unificado...")
        while self._running:
            try:
                self._process_updates()
            except Exception as e:
                logger.error(f"Error en poll loop: {e}", exc_info=True)
            time.sleep(self.poll_interval)

    def _process_updates(self) -> None:
        try:
            response = requests.post(
                f"{self.base_url}/getUpdates",
                json={
                    "offset": self._last_update_id + 1 if self._last_update_id else 0,
                    "timeout": 5,
                    "allowed_updates": ["message", "callback_query"]
                },
                timeout=15
            )
            response.raise_for_status()
            result = response.json()

            if not result.get('ok'):
                return

            for update in result.get('result', []):
                update_id = update.get('update_id', 0)
                self._last_update_id = max(self._last_update_id, update_id)

                if update.get('callback_query'):
                    self._dispatch_callback(update['callback_query'])

                if update.get('message'):
                    self._dispatch_message(update['message'])

        except requests.exceptions.Timeout:
            pass
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error HTTP en polling: {e}")
        except Exception as e:
            logger.error(f"Error procesando updates: {e}")

    def _dispatch_callback(self, callback_query: Dict[str, Any]) -> None:
        """Distribuye callback_query a TODOS los handlers registrados."""
        for handler in self._callback_handlers:
            try:
                handler(callback_query)
            except Exception as e:
                logger.error(f"Error en callback handler {handler.__name__}: {e}", exc_info=True)

    def _dispatch_message(self, message: Dict[str, Any]) -> None:
        """Distribuye messages a todos los handlers registrados."""
        for handler in self._message_handlers:
            try:
                handler(message)
            except Exception as e:
                logger.error(f"Error en message handler {handler.__name__}: {e}", exc_info=True)

    def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML",
                     reply_markup: Optional[Dict] = None) -> Optional[int]:
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup

            response = requests.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=10
            )
            if response.status_code == 200 and response.json().get('ok'):
                return response.json()['result']['message_id']
            return None
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")
            return None