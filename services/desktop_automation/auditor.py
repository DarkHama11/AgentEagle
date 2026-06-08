import logging
import json
from datetime import datetime
logger = logging.getLogger(__name__)

class AutomationAuditor:
    @staticmethod
    def log_action(session_id: str, action: str, status: str, details: str = ""):
        logger.info(f"[AUDIT] {session_id} | {action} | {status} | {details}")
