import os
import json
import logging
import threading
from typing import Dict, List, Optional
from datetime import datetime, timezone
from .approval_request import ApprovalRequest, ApprovalStatus

logger = logging.getLogger("AgentEagle.ApprovalStore")


class ApprovalStore:
    """
    Almacén persistente de solicitudes de aprobación.
    Guarda cada solicitud en un archivo JSON individual.
    Thread-safe para acceso concurrente.
    """

    def __init__(self, store_dir: str = "approvals"):
        self.store_dir = store_dir
        self._lock = threading.RLock()
        os.makedirs(store_dir, exist_ok=True)
        logger.info(f"ApprovalStore inicializado en: {store_dir}")

    def _get_file_path(self, approval_id: str) -> str:
        """Retorna la ruta del archivo para un approval_id."""
        return os.path.join(self.store_dir, f"{approval_id}.json")

    def save(self, request: ApprovalRequest) -> None:
        """Guarda o actualiza una solicitud de aprobación."""
        with self._lock:
            file_path = self._get_file_path(request.approval_id)
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(request.to_dict(), f, indent=2, ensure_ascii=False)
                logger.debug(f"Solicitud guardada: {request.approval_id}")
            except Exception as e:
                logger.error(f"Error guardando solicitud {request.approval_id}: {e}")
                raise

    def load(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Carga una solicitud de aprobación por su ID."""
        with self._lock:
            file_path = self._get_file_path(approval_id)
            if not os.path.exists(file_path):
                return None
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return ApprovalRequest.from_dict(data)
            except Exception as e:
                logger.error(f"Error cargando solicitud {approval_id}: {e}")
                return None

    def list_all(self, status_filter: Optional[str] = None) -> List[ApprovalRequest]:
        """Lista todas las solicitudes, opcionalmente filtradas por estado."""
        with self._lock:
            requests = []
            for filename in os.listdir(self.store_dir):
                if not filename.endswith('.json'):
                    continue
                file_path = os.path.join(self.store_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    request = ApprovalRequest.from_dict(data)
                    if status_filter is None or request.status == status_filter:
                        requests.append(request)
                except Exception as e:
                    logger.warning(f"Error leyendo {filename}: {e}")

            # Ordenar por fecha de creación (más reciente primero)
            requests.sort(key=lambda r: r.created_at, reverse=True)
            return requests

    def list_by_job(self, job_id: str) -> List[ApprovalRequest]:
        """Lista todas las solicitudes de un job específico."""
        all_requests = self.list_all()
        return [r for r in all_requests if r.job_id == job_id]

    def list_pending(self) -> List[ApprovalRequest]:
        """Lista solo las solicitudes pendientes."""
        return self.list_all(status_filter=ApprovalStatus.PENDING.value)

    def delete(self, approval_id: str) -> bool:
        """Elimina una solicitud (uso administrativo)."""
        with self._lock:
            file_path = self._get_file_path(approval_id)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Solicitud eliminada: {approval_id}")
                return True
            return False

    def check_timeouts(self) -> List[str]:
        """
        Verifica solicitudes expiradas y las marca como TIMEOUT.
        Retorna lista de approval_ids que expiraron.
        """
        with self._lock:
            expired_ids = []
            for request in self.list_all(status_filter=ApprovalStatus.PENDING.value):
                if request.is_expired():
                    request.mark_timeout()
                    self.save(request)
                    expired_ids.append(request.approval_id)
                    logger.warning(f"Solicitud expirada: {request.approval_id}")
            return expired_ids