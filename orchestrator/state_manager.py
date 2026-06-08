import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional

class StateManager:
    """Gestiona el estado de ejecución de los jobs en formato JSON."""

    # Estados posibles del job
    STATUS_RUNNING = "RUNNING"
    STATUS_WAITING_HUMAN = "WAITING_HUMAN"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"
    STATUS_TIMEOUT = "TIMEOUT"
    STATUS_CANCELLED = "CANCELLED"

    def __init__(self, state_dir: str):
        self.state_dir = state_dir
        os.makedirs(self.state_dir, exist_ok=True)

    def _get_state_file(self, job_id: str) -> str:
        return os.path.join(self.state_dir, f"{job_id}.json")

    def create_initial_state(self, job_id: str, pipeline_name: str, total_steps: int) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        state = {
            "job_id": job_id,
            "pipeline": pipeline_name,
            "status": self.STATUS_RUNNING,
            "current_step": None,
            "current_step_index": 0,
            "current_step_status": None,
            "completed_steps": [],
            "total_steps": total_steps,
            "results": {},
            "payload": {},
            "pending_approval": None,
            "created_at": now,
            "updated_at": now
        }
        self.save_state(state)
        return state

    def save_state(self, state: Dict[str, Any]) -> None:
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        file_path = self._get_state_file(state["job_id"])
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(state, file, indent=2, ensure_ascii=False)

    def load_state(self, job_id: str) -> Optional[Dict[str, Any]]:
        file_path = self._get_state_file(job_id)
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)

    def update_step(self, state: Dict[str, Any], step_id: str, step_index: int = None) -> None:
        state["current_step"] = step_id
        if step_index is not None:
            state["current_step_index"] = step_index
        state["current_step_status"] = "RUNNING"
        self.save_state(state)

    def update_step_status(self, job_id: str, status: str) -> None:
        state = self.load_state(job_id)
        if state:
            state["current_step_status"] = status
            self.save_state(state)

    def mark_completed(self, state: Dict[str, Any], step_id: str, result: Dict[str, Any]) -> None:
        if step_id not in state["completed_steps"]:
            state["completed_steps"].append(step_id)
        state["results"][step_id] = result
        state["current_step_status"] = "COMPLETED"
        self.save_state(state)

    def mark_failed(self, state: Dict[str, Any], error_message: str) -> None:
        state["status"] = self.STATUS_FAILED
        state["current_step_status"] = "FAILED"
        state["error"] = error_message
        self.save_state(state)

    def mark_finished(self, state: Dict[str, Any]) -> None:
        state["status"] = self.STATUS_COMPLETED
        state["current_step"] = "DONE"
        state["current_step_status"] = "FINISHED"
        self.save_state(state)

    # Métodos para WAITING_HUMAN
    def mark_waiting_human(self, state: Dict[str, Any], approval_id: str) -> None:
        """Marca el job como esperando aprobación humana."""
        state["status"] = self.STATUS_WAITING_HUMAN
        state["pending_approval"] = approval_id
        state["current_step_status"] = "WAITING_HUMAN"
        self.save_state(state)

    def mark_approved(self, state: Dict[str, Any]) -> None:
        """Marca el job como aprobado y listo para continuar."""
        state["status"] = self.STATUS_RUNNING
        state["pending_approval"] = None
        state["current_step_status"] = "APPROVED"
        self.save_state(state)

    def mark_rejected(self, state: Dict[str, Any], reason: str = "") -> None:
        """Marca el job como rechazado por el humano."""
        state["status"] = self.STATUS_REJECTED
        state["pending_approval"] = None
        state["current_step_status"] = "REJECTED"
        state["rejection_reason"] = reason
        self.save_state(state)

    def update_payload(self, state: Dict[str, Any], payload: Dict[str, Any]) -> None:
        """Actualiza el payload del job (para reanudación)."""
        state["payload"] = payload
        self.save_state(state)