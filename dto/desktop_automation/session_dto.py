from dataclasses import dataclass
from typing import Optional, Any
from datetime import datetime

@dataclass
class SessionState:
    session_id: str
    backend_type: str
    process_id: Optional[int] = None
    app_instance: Optional[Any] = None
    is_active: bool = False
    created_at: datetime = datetime.now()
