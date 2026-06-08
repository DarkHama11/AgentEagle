import logging
import sys
import time
import uuid
import os
from core.event_bus import EventBus
from agents.functional.conversion_agent import ConversionAgent
from agents.functional.desktop_automation_agent import DesktopAutomationAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


def initialize_system():
    logger.info("🚀 Iniciando AgentEagle Core...")
    event_bus = EventBus()
    ConversionAgent(event_bus)
    DesktopAutomationAgent(event_bus)
    logger.info("✅ Sistema inicializado.")
    return event_bus


def test_flow(event_bus: EventBus):
    logger.info("\n" + "=" * 70)
    logger.info("🧪 INICIANDO PRUEBA DE CONVERSIÓN CON FALLBACK RPA")
    logger.info("=" * 70 + "\n")

    # ⚠️ RUTA DEL PDF REAL PROPORCIONADA ⚠️
    # La 'r' al principio es crucial para que Python lea las barras invertidas correctamente
    test_file = r"D:\cosas\git\DOCUMENTACION\Hv_Hama.pdf"

    # Verificación de seguridad
    if not os.path.exists(test_file):
        logger.error(f"❌ ERROR CRÍTICO: El archivo NO existe en la ruta: {test_file}")
        logger.error("Por favor, verifica que la ruta sea exacta y el archivo exista.")
        return

    logger.info(f"✅ Archivo de entrada encontrado: {test_file}")

    event_bus.publish("CONVERSION_REQUEST", {
        "request_id": str(uuid.uuid4()),
        "file_path": test_file,
        "target_format": "docx",
        "user_id": "telegram_user_123"
    })


if __name__ == "__main__":
    try:
        event_bus = initialize_system()
        test_flow(event_bus)
        logger.info("\n🟢 Sistema en ejecución. Esperando respuesta... (Presiona Ctrl+C para detener)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n🛑 Deteniendo sistema...")
        sys.exit(0)