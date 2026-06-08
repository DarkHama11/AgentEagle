import os
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("AgentEagle.TelegramFileService")


class TelegramFileService:
    def __init__(self, bot_token: str, uploads_dir: str = "data/uploads"):
        self.bot_token = bot_token
        self.uploads_dir = uploads_dir
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.file_base_url = f"https://api.telegram.org/file/bot{bot_token}"

        os.makedirs(uploads_dir, exist_ok=True)
        logger.info(f"TelegramFileService inicializado. Uploads: {uploads_dir}")

    def download_file(self, file_id: str, job_id: str, original_filename: Optional[str] = None) -> Dict[str, Any]:
        try:
            file_info = self._get_file_info(file_id)
            if not file_info:
                return {"status": "error", "error": "No se pudo obtener información del archivo"}

            file_path_telegram = file_info.get('file_path')
            if not file_path_telegram:
                return {"status": "error", "error": "file_path no encontrado en la respuesta"}

            if original_filename:
                filename = self._sanitize_filename(original_filename)
            else:
                filename = os.path.basename(file_path_telegram)

            job_dir = os.path.join(self.uploads_dir, job_id)
            os.makedirs(job_dir, exist_ok=True)

            local_path = os.path.join(job_dir, filename)

            download_url = f"{self.file_base_url}/{file_path_telegram}"
            logger.info(f"Descargando archivo desde Telegram: {download_url}")

            response = requests.get(download_url, timeout=120, stream=True)
            response.raise_for_status()

            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            file_size_local = os.path.getsize(local_path)
            extension = os.path.splitext(filename)[1].lower().lstrip('.')

            logger.info(f"✅ Archivo descargado: {local_path} ({file_size_local} bytes)")

            return {
                "status": "success",
                "local_path": local_path,
                "filename": filename,
                "extension": extension,
                "file_size": file_size_local,
                "job_id": job_id,
                "job_dir": job_dir
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error descargando archivo: {e}")
            return {"status": "error", "error": f"Error de red: {str(e)}"}
        except Exception as e:
            logger.error(f"Error inesperado descargando archivo: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def _get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = requests.post(
                f"{self.base_url}/getFile",
                json={"file_id": file_id},
                timeout=10
            )
            response.raise_for_status()
            result = response.json()

            if result.get('ok'):
                return result.get('result')
            else:
                logger.error(f"Error en getFile: {result.get('description')}")
                return None
        except Exception as e:
            logger.error(f"Error obteniendo info del archivo: {e}")
            return None

    def _sanitize_filename(self, filename: str) -> str:
        dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        return filename.strip()