import os
import sys
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Punto de entrada principal de AgentEagle con Telegram"""

    logger.info("=" * 70)
    logger.info("🦅 AgentEagle - Iniciando sistema completo...")
    logger.info("=" * 70)

    # 1. Inicializar EventBus
    from core.event_bus import EventBus
    event_bus = EventBus()
    logger.info("✅ EventBus inicializado")

    # 2. Registrar agentes
    from agents.functional.conversion_agent import ConversionAgent
    from agents.functional.desktop_automation_agent import DesktopAutomationAgent

    ConversionAgent(event_bus)
    logger.info("✅ ConversionAgent registrado")

    DesktopAutomationAgent(event_bus)
    logger.info("✅ DesktopAutomationAgent registrado")

    # 3. Configurar Telegram
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token:
        logger.error("❌ TELEGRAM_BOT_TOKEN no configurado en .env")
        sys.exit(1)

    if not chat_id:
        logger.error("❌ TELEGRAM_CHAT_ID no configurado en .env")
        sys.exit(1)

    # 4. Inicializar Bridge (conecta Telegram con RPA)
    from telegram_conversion_bridge import TelegramConversionBridge
    bridge = TelegramConversionBridge(event_bus, bot_token)
    logger.info("✅ TelegramConversionBridge inicializado")

    # 5. Inicializar sistema de Telegram
    from telegram import UnifiedTelegramListener
    from telegram.command_handler import TelegramCommandHandler
    from telegram.message_listener import TelegramMessageListener

    allowed_chat_ids = {chat_id}

    # Command Handler
    command_handler = TelegramCommandHandler(
        bot_token=bot_token,
        allowed_chat_ids=allowed_chat_ids,
        event_bus=event_bus
    )
    logger.info("✅ TelegramCommandHandler inicializado")

    # Message Listener
    message_listener = TelegramMessageListener(
        event_bus=event_bus,
        bot_token=bot_token,
        allowed_chat_ids=allowed_chat_ids,
        supported_formats=["pdf", "docx", "png", "jpg", "jpeg"],
        command_handler=command_handler
    )
    logger.info("✅ TelegramMessageListener inicializado")

    # Unified Listener
    unified_listener = UnifiedTelegramListener(
        bot_token=bot_token,
        allowed_chat_ids=allowed_chat_ids,
        poll_interval=2
    )

    # Registrar handlers
    unified_listener.register_message_handler(message_listener.handle_message)
    unified_listener.register_callback_handler(message_listener.handle_callback)
    logger.info("✅ Handlers registrados en UnifiedTelegramListener")

    # 6. Iniciar el listener
    unified_listener.start()

    logger.info("=" * 70)
    logger.info("🤖 Bot de Telegram ACTIVO")
    logger.info(f"📱 Chat autorizado: {chat_id}")
    logger.info("💡 Comandos disponibles:")
    logger.info("   /start    - Mensaje de bienvenida")
    logger.info("   /menu     - Menú principal")
    logger.info("   /pdf2word - Convertir PDF a Word")
    logger.info("   /word2pdf - Convertir Word a PDF")
    logger.info("   /ocr      - Extraer texto de imagen")
    logger.info("   /status   - Estado del sistema")
    logger.info("   /help     - Ayuda")
    logger.info("=" * 70)
    logger.info("🟢 Sistema en ejecución. Presiona Ctrl+C para detener.")

    # 7. Mantener el sistema corriendo
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n🛑 Deteniendo sistema...")
        unified_listener.stop()
        logger.info("✅ Sistema detenido")
        sys.exit(0)


if __name__ == "__main__":
    main()