import os
import uuid
import logging
import threading
from typing import Dict, Any, Optional

from orchestrator.pipeline_loader import PipelineLoader
from orchestrator.dispatcher import Dispatcher
from orchestrator.state_manager import StateManager
from event_bus.base_event_bus import BaseEventBus
from event_bus.event import Event
from approval.approval_manager import ApprovalManager


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.job_id = getattr(record, 'job_id', 'SYSTEM')
        record.step = getattr(record, 'step', 'INIT')
        record.status = getattr(record, 'status', 'INFO')
        return True


class Orchestrator:
    def __init__(
            self,
            pipelines_dir: str,
            state_dir: str,
            logs_dir: str,
            event_bus: BaseEventBus,
            dispatcher: Dispatcher,
            approval_manager: Optional[ApprovalManager] = None
    ):
        self.pipeline_loader = PipelineLoader(pipelines_dir)
        self.dispatcher = dispatcher
        self.state_manager = StateManager(state_dir)
        self.event_bus = event_bus
        self.approval_manager = approval_manager or ApprovalManager(event_bus=event_bus)

        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, "orchestrator.log")

        self.logger = logging.getLogger("AgentEagleOrchestrator")
        self.logger.setLevel(logging.INFO)

        if not self.logger.handlers:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            console_handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s | %(job_id)s | %(step)s | %(status)s | %(message)s')
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)

            context_filter = ContextFilter()
            file_handler.addFilter(context_filter)
            console_handler.addFilter(context_filter)

            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def _log(self, job_id: str, step: str, status: str, message: str) -> None:
        extra = {'job_id': job_id, 'step': step, 'status': status}
        self.logger.info(message, extra=extra)

    def run_pipeline(self, pipeline_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta un pipeline completo. Si encuentra type: approval, pausa y espera."""
        job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
        return self._execute_pipeline(job_id, pipeline_name, payload, start_index=0)

    def _execute_pipeline(
            self,
            job_id: str,
            pipeline_name: str,
            payload: Dict[str, Any],
            start_index: int = 0,
            existing_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Ejecuta el pipeline desde un índice específico."""

        self.event_bus.publish(Event(
            event_type="pipeline.started",
            source="orchestrator",
            payload={"job_id": job_id, "pipeline": pipeline_name, "start_index": start_index}
        ))
        self._log(job_id, "INIT", "STARTED", f"Iniciando pipeline: {pipeline_name} (desde paso {start_index})")

        try:
            pipeline_config = self.pipeline_loader.load(pipeline_name)
            steps = pipeline_config.get("steps", [])

            if existing_state:
                state = existing_state
                state["status"] = StateManager.STATUS_RUNNING
                self.state_manager.save_state(state)
            else:
                state = self.state_manager.create_initial_state(job_id, pipeline_name, len(steps))

            self.state_manager.update_payload(state, payload)

            # Evento para pausar/reanudar
            resume_event = threading.Event()
            resume_status = {"status": None}

            def on_approval_resolved(status: str):
                resume_status["status"] = status
                resume_event.set()

            self.approval_manager.register_resume_callback(job_id, on_approval_resolved)

            try:
                for step_index in range(start_index, len(steps)):
                    step = steps[step_index]
                    step_id = step["id"]
                    step_type = step.get("type", "action")

                    self.state_manager.update_step(state, step_id, step_index)

                    # Manejar paso de aprobación humana
                    if step_type == "approval":
                        result = self._handle_approval_step(
                            job_id, pipeline_name, step, state, payload, resume_event, resume_status
                        )

                        if result["action"] == "pause":
                            return state
                        elif result["action"] == "continue":
                            continue
                        elif result["action"] == "abort":
                            self.state_manager.mark_rejected(state, result.get("reason", ""))
                            self._log(job_id, step_id, "REJECTED", "Pipeline rechazado por aprobador humano")
                            return state

                    # Paso normal de acción
                    agent_name = step.get("agent")
                    action = step.get("action")

                    if not agent_name or not action:
                        raise ValueError(f"Paso {step_id} inválido: falta 'agent' o 'action'")

                    self.event_bus.publish(Event(
                        event_type="step.started",
                        source="orchestrator",
                        payload={"job_id": job_id, "step": step_id, "agent": agent_name, "action": action}
                    ))

                    self._log(job_id, step_id, "RUNNING", f"Ejecutando agente '{agent_name}' con acción '{action}'")

                    try:
                        result = self.dispatcher.execute(agent_name, action, payload)

                        if result.get("status") == "success":
                            self.state_manager.mark_completed(state, step_id, result)
                            self.event_bus.publish(Event(
                                event_type="step.completed",
                                source="orchestrator",
                                payload={"job_id": job_id, "step": step_id, "result": result}
                            ))
                            self._log(job_id, step_id, "SUCCESS", result.get("result", "Completado"))

                            if "data" in result:
                                payload.update(result["data"])
                                self.state_manager.update_payload(state, payload)
                        else:
                            raise RuntimeError(f"Agente reportó error: {result.get('result')}")

                    except Exception as e:
                        error_msg = str(e)
                        self.event_bus.publish(Event(
                            event_type="step.failed",
                            source="orchestrator",
                            payload={"job_id": job_id, "step": step_id, "error": error_msg}
                        ))
                        self.state_manager.mark_failed(state, error_msg)
                        raise RuntimeError(f"Pipeline falló en '{step_id}': {error_msg}")

                self.state_manager.mark_finished(state)
                self.event_bus.publish(Event(
                    event_type="pipeline.completed",
                    source="orchestrator",
                    payload={"job_id": job_id, "pipeline": pipeline_name}
                ))
                self._log(job_id, "FINAL", "COMPLETED", "Ejecución finalizada con éxito.")
                return state

            finally:
                self.approval_manager.unregister_resume_callback(job_id)

        except Exception as e:
            self.event_bus.publish(Event(
                event_type="pipeline.failed",
                source="orchestrator",
                payload={"job_id": job_id, "pipeline": pipeline_name, "error": str(e)}
            ))
            self._log(job_id, "INIT", "FAILED", str(e))
            raise

    def _handle_approval_step(
            self,
            job_id: str,
            pipeline_name: str,
            step: Dict[str, Any],
            state: Dict[str, Any],
            payload: Dict[str, Any],
            resume_event: threading.Event,
            resume_status: Dict[str, str]
    ) -> Dict[str, Any]:
        """Maneja un paso de tipo 'approval'."""
        step_id = step["id"]
        title = step.get("title", "Aprobación requerida")
        description = step.get("description", "")
        expires_in_hours = step.get("expires_in_hours", 24)

        self._log(job_id, step_id, "WAITING", f"Solicitando aprobación humana: {title}")

        approval_request = self.approval_manager.request_approval(
            job_id=job_id,
            pipeline_name=pipeline_name,
            step_id=step_id,
            requested_by="orchestrator",
            title=title,
            description=description,
            payload=payload,
            expires_in_hours=expires_in_hours
        )

        self.state_manager.mark_waiting_human(state, approval_request.approval_id)

        self.event_bus.publish(Event(
            event_type="step.waiting_human",
            source="orchestrator",
            payload={
                "job_id": job_id,
                "step": step_id,
                "approval_id": approval_request.approval_id
            }
        ))

        self._log(job_id, step_id, "PAUSED", f"Pipeline pausado. Approval ID: {approval_request.approval_id}")
        resume_event.wait()

        status = resume_status.get("status")
        self._log(job_id, step_id, "RESUMED", f"Aprobación resuelta: {status}")

        if status == "APPROVED":
            self.state_manager.mark_approved(state)
            self.state_manager.mark_completed(state, step_id, {
                "status": "success",
                "result": f"Aprobado: {approval_request.approval_id}"
            })
            return {"action": "continue"}

        elif status == "REJECTED":
            return {
                "action": "abort",
                "reason": f"Rechazado por aprobador humano. Approval ID: {approval_request.approval_id}"
            }

        else:
            return {
                "action": "abort",
                "reason": f"Estado desconocido: {status}"
            }

    def resume_pipeline(self, job_id: str) -> Dict[str, Any]:
        """Reanuda un pipeline que estaba en WAITING_HUMAN."""
        state = self.state_manager.load_state(job_id)
        if not state:
            raise ValueError(f"Job no encontrado: {job_id}")

        if state["status"] != StateManager.STATUS_WAITING_HUMAN:
            raise ValueError(f"Job {job_id} no está en estado WAITING_HUMAN")

        pipeline_name = state["pipeline"]
        start_index = state.get("current_step_index", 0) + 1
        payload = state.get("payload", {})

        return self._execute_pipeline(
            job_id=job_id,
            pipeline_name=pipeline_name,
            payload=payload,
            start_index=start_index,
            existing_state=state
        )