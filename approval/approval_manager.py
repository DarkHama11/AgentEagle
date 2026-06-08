import logging
import threading
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timezone

from .approval_request import ApprovalRequest, ApprovalStatus
from .approval_store import ApprovalStore

logger = logging.getLogger("AgentEagle.ApprovalManager")


class ApprovalManager:
    """
    Gestor central de aprobaciones humanas.
    Coordina la creación, resolución y notificación de solicitudes.
    Patrón Singleton para consistencia global.
    """

    _instance: Optional['ApprovalManager'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, store_dir: str = "approvals", event_bus=None):
        if self._initialized:
            return

        self.store = ApprovalStore(store_dir=store_dir)
        self.event_bus = event_bus
        self._resume_callbacks: Dict[str, Callable] = {}
        self._callback_lock = threading.Lock()

        self._initialized = True
        logger.info("ApprovalManager inicializado (Singleton)")

    def request_approval(
            self,
            job_id: str,
            pipeline_name: str,
            step_id: str,
            requested_by: str,
            title: str,
            description: str,
            payload: Dict[str, Any],
            expires_in_hours: int = 24
    ) -> ApprovalRequest:
        """
        Crea una nueva solicitud de aprobación.

        :return: ApprovalRequest creada
        """
        from datetime import timedelta

        request = ApprovalRequest(
            job_id=job_id,
            pipeline_name=pipeline_name,
            step_id=step_id,
            requested_by=requested_by,
            title=title,
            description=description,
            payload=payload,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
        )

        self.store.save(request)
        logger.info(f"Solicitud de aprobación creada: {request.approval_id} para job {job_id}")

        # Publicar evento
        if self.event_bus:
            from event_bus.event import Event
            self.event_bus.publish(Event(
                event_type="approval.required",
                source="approval_manager",
                payload={
                    "approval_id": request.approval_id,
                    "job_id": job_id,
                    "pipeline_name": pipeline_name,
                    "step_id": step_id,
                    "title": title,
                    "description": description,
                    "payload": payload,
                    "expires_at": request.expires_at.isoformat()
                }
            ))

        return request

    def approve(
            self,
            approval_id: str,
            resolved_by: str = "user",
            notes: str = ""
    ) -> ApprovalRequest:
        """
        Aprueba una solicitud y reanuda el pipeline.

        :raises ValueError: Si la solicitud no existe o no puede aprobarse
        """
        request = self.store.load(approval_id)
        if not request:
            raise ValueError(f"Solicitud no encontrada: {approval_id}")

        request.approve(resolved_by=resolved_by, notes=notes)
        self.store.save(request)

        logger.info(f"Solicitud aprobada: {approval_id} por {resolved_by}")

        # Publicar evento
        if self.event_bus:
            from event_bus.event import Event
            self.event_bus.publish(Event(
                event_type="approval.approved",
                source="approval_manager",
                payload={
                    "approval_id": approval_id,
                    "job_id": request.job_id,
                    "pipeline_name": request.pipeline_name,
                    "step_id": request.step_id,
                    "resolved_by": resolved_by,
                    "notes": notes
                }
            ))

        # Reanudar pipeline si hay callback registrado
        self._trigger_resume(request.job_id, ApprovalStatus.APPROVED.value)

        return request

    def reject(
            self,
            approval_id: str,
            resolved_by: str = "user",
            notes: str = ""
    ) -> ApprovalRequest:
        """
        Rechaza una solicitud y finaliza el pipeline.

        :raises ValueError: Si la solicitud no existe o no puede rechazarse
        """
        request = self.store.load(approval_id)
        if not request:
            raise ValueError(f"Solicitud no encontrada: {approval_id}")

        request.reject(resolved_by=resolved_by, notes=notes)
        self.store.save(request)

        logger.info(f"Solicitud rechazada: {approval_id} por {resolved_by}")

        # Publicar evento
        if self.event_bus:
            from event_bus.event import Event
            self.event_bus.publish(Event(
                event_type="approval.rejected",
                source="approval_manager",
                payload={
                    "approval_id": approval_id,
                    "job_id": request.job_id,
                    "pipeline_name": request.pipeline_name,
                    "step_id": request.step_id,
                    "resolved_by": resolved_by,
                    "notes": notes
                }
            ))

        # Notificar al pipeline para que se detenga
        self._trigger_resume(request.job_id, ApprovalStatus.REJECTED.value)

        return request

    def get_request(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Obtiene una solicitud por su ID."""
        return self.store.load(approval_id)

    def list_pending(self) -> List[ApprovalRequest]:
        """Lista todas las solicitudes pendientes."""
        return self.store.list_pending()

    def list_all(self, status_filter: Optional[str] = None) -> List[ApprovalRequest]:
        """Lista todas las solicitudes."""
        return self.store.list_all(status_filter=status_filter)

    def register_resume_callback(self, job_id: str, callback: Callable[[str], None]) -> None:
        """
        Registra un callback que se ejecutará cuando se resuelva una aprobación.
        El callback recibe el status final (APPROVED/REJECTED).
        """
        with self._callback_lock:
            self._resume_callbacks[job_id] = callback
            logger.debug(f"Callback registrado para job {job_id}")

    def unregister_resume_callback(self, job_id: str) -> None:
        """Elimina el callback de un job."""
        with self._callback_lock:
            if job_id in self._resume_callbacks:
                del self._resume_callbacks[job_id]

    def _trigger_resume(self, job_id: str, status: str) -> None:
        """Ejecuta el callback registrado para un job."""
        with self._callback_lock:
            callback = self._resume_callbacks.get(job_id)

        if callback:
            try:
                logger.info(f"Ejecutando callback de reanudación para job {job_id}")
                callback(status)
            except Exception as e:
                logger.error(f"Error en callback de reanudación para {job_id}: {e}", exc_info=True)
        else:
            logger.warning(f"No hay callback registrado para job {job_id}")

    @classmethod
    def reset_instance(cls) -> None:
        """Reinicia el singleton (solo para testing)."""
        with cls._lock:
            cls._instance = None