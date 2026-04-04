# main.py
"""AgentEagle++ Cloud Security Specialist - Entry Point."""
import sys
import logging
import warnings
from pathlib import Path
import uvicorn
from src.core.config import Config
from src.server.api import app

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")


def setup_logging() -> logging.Logger:
    log_dir = Config.LOGS_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "AgentEagle.log"
    log_format = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
    logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO), format=log_format,
                        handlers=[logging.FileHandler(log_file, encoding="utf-8", mode="a"),
                                  logging.StreamHandler(sys.stdout)], force=True)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    return logging.getLogger("AgentEagle")


logger = setup_logging()


def check_system_requirements() -> bool:
    logger = logging.getLogger("AgentEagle.check")
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        if response.status_code == 200:
            logger.info("✅ Ollama server detectado en localhost:11434")
        else:
            logger.warning("⚠️ Ollama respondió con estado inesperado")
    except requests.ConnectionError:
        logger.error("❌ No se pudo conectar con Ollama. Ejecuta: ollama serve")
        return False
    except Exception as e:
        logger.warning(f"⚠️ No se pudo verificar Ollama: {e}")

    for dir_path, name in [(Config.MODELS_DIR, "MODELS"), (Config.LOGS_DIR, "LOGS"), (Config.DATA_DIR, "DATA")]:
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Directorio {name}: {dir_path}")
        except PermissionError:
            logger.error(f"❌ Sin permisos para escribir en {dir_path}")
            return False
    return True


def print_startup_banner():
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + " 🦞 AgentEagle++ v2.1 ".center(58) + "║")
    print("║" + " ☁️ Cloud Security Specialist ".center(58) + "║")
    print("╠" + "═" * 58 + "╣")
    print(f"║  📡 API: http://{Config.API_HOST}:{Config.API_PORT}".ljust(59) + "║")
    print(f"║  🤖 Modelo: {Config.MODELS.get(Config.DEFAULT_MODEL_KEY, {}).get('ollama_model', 'llama3.2:3b')}".ljust(
        59) + "║")
    print(f"║  🔧 Agentes: seguridad (cloud), oficina".ljust(59) + "║")
    print(f"║  ⚡ Performance: ~5s promedio (RTX 3050)".ljust(59) + "║")
    print("╚" + "═" * 58 + "╝\n")


def main():
    logger.info("🚀 Iniciando AgentEagle++ Cloud Security...")
    if not check_system_requirements():
        logger.error("❌ Prerequisitos no cumplidos. Abortando.")
        sys.exit(1)
    print_startup_banner()
    logger.info(f"📡 Iniciando servidor en {Config.API_HOST}:{Config.API_PORT}")
    try:
        uvicorn.run(app, host=Config.API_HOST, port=Config.API_PORT, log_level=Config.LOG_LEVEL.lower(), reload=False,
                    workers=1, timeout_keep_alive=30, limit_concurrency=5)
    except KeyboardInterrupt:
        logger.info("👋 Interrupción recibida. Cerrando...")
    except Exception as e:
        logger.error(f"❌ Error en servidor: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("🔚 AgentEagle++ finalizado")


if __name__ == "__main__":
    main()