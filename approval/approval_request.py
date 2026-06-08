import uuid
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
from enum import Enum


class ApprovalStatus(str, Enum):
    """Estados posibles de una solicitud de aprobación."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


@dataclass
class ApprovalRequest:
    """
    Modelo inmutable que representa una solicitud de aprobación humana.
    """
    job_id: str
    pipeline_name: str
    step_id: str
    requested_by: str
    title: str
    description: str
    payload: Dict[str, Any]
    approval_id: str = field(default_factory=lambda: f"APR-{uuid.uuid4().hex[:8].upper()}")
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = field(default=None)
    status: str = field(default=ApprovalStatus.PENDING.value)
    resolved_at: Optional[datetime] = field(default=None)
    resolved_by: Optional[str] = field(default=None)
    resolution_notes: Optional[str] = field(default=None)

    def __post_init__(self):
        """Validaciones y configuración por defecto."""
        # Si no se especifica expiración, usar 24 horas por defecto
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(hours=24)

        # Asegurar que los timestamps tengan timezone
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if self.expires_at and self.expires_at.tzinfo is None:
            self.expires_at = self.expires_at.replace(tzinfo=timezone.utc)

    def is_expired(self) -> bool:
        """Verifica si la solicitud ha expirado."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def can_be_resolved(self) -> bool:
        """Verifica si la solicitud puede ser aprobada/rechazada."""
        return self.status == ApprovalStatus.PENDING.value and not self.is_expired()

    def approve(self, resolved_by: str = "system", notes: str = "") -> None:
        """Marca la solicitud como aprobada."""
        if not self.can_be_resolved():
            raise ValueError(f"No se puede aprobar: estado actual es {self.status}")
        self.status = ApprovalStatus.APPROVED.value
        self.resolved_at = datetime.now(timezone.utc)
        self.resolved_by = resolved_by
        self.resolution_notes = notes

    def reject(self, resolved_by: str = "system", notes: str = "") -> None:
        """Marca la solicitud como rechazada."""
        if not self.can_be_resolved():
            raise ValueError(f"No se puede rechazar: estado actual es {self.status}")
        self.status = ApprovalStatus.REJECTED.value
        self.resolved_at = datetime.now(timezone.utc)
        self.resolved_by = resolved_by
        self.resolution_notes = notes

    def cancel(self, reason: str = "") -> None:
        """Cancela la solicitud."""
        self.status = ApprovalStatus.CANCELLED.value
        self.resolved_at = datetime.now(timezone.utc)
        self.resolution_notes = reason

    def mark_timeout(self) -> None:
        """Marca la solicitud como expirada."""
        self.status = ApprovalStatus.TIMEOUT.value
        self.resolved_at = datetime.now(timezone.utc)
        self.resolution_notes = "Tiempo de espera agotado"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para serialización."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['expires_at'] = self.expires_at.isoformat() if self.expires_at else None
        data['resolved_at'] = self.resolved_at.isoformat() if self.resolved_at else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ApprovalRequest':
        """Crea una instancia desde un diccionario."""
        data = data.copy()
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('expires_at'), str):
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        if isinstance(data.get('resolved_at'), str):
            data['resolved_at'] = datetime.fromisoformat(data['resolved_at'])
        return cls(**data)