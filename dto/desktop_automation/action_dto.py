from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class ActionRequest:
    session_id: str
    action_type: str
    payload: Dict[str, Any]
    timeout: int = 60

@dataclass
class ActionResult:
    session_id: str
    success: bool
    message: str
    output_data: Optional[Dict[str, Any]] = None
    error_details: Optional[str] = None
