import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict

@dataclass(frozen=True)
class Event:
    """Modelo inmutable para eventos del sistema."""
    event_type: str
    source: str
    payload: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "payload": self.payload
        }