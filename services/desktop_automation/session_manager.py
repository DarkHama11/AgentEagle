from typing import Dict, Optional
from dto.desktop_automation.session_dto import SessionState
import uuid
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    _sessions: Dict[str, SessionState] = {}

    @classmethod
    def create_session(cls, backend_type: str) -> str:
        session_id = str(uuid.uuid4())
        cls._sessions[session_id] = SessionState(session_id=session_id, backend_type=backend_type)
        return session_id

    @classmethod
    def close_session(cls, session_id: str):
        if session_id in cls._sessions:
            session = cls._sessions.pop(session_id)
            if session.app_instance:
                try:
                    session.app_instance.kill()
                except Exception:
                    pass
