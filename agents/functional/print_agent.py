import os
import json
import yaml
import uuid
import logging
import requests
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from agents.base_agent import BaseAgent
from event_bus.event import Event

from services.telegram_file_service import TelegramFileService
from services.cups_service import CupsService
from services.print_rules_service import PrintRulesService
from services.printer_manager import PrinterManager
from services.print_decision_service import PrintDecisionService
from services.llm_service import LLMService
from services.model_manager import ModelManager
from services.caption_parser_service import CaptionParserService

logger = logging.getLogger("AgentEagle.PrintAgent")


class PrintAgent(BaseAgent):
    name = "print_agent"
    description = "Agente inteligente de impresión con análisis IA y aprobación"
    capabilities = ["smart_print", "print_decision", "print_status", "list_printers"]

    _pending_decisions: Dict[str, Dict[str, Any]] = {}
    _decisions_lock = threading.Lock()

    def __init__(
            self,
            event_bus=None,
            state_manager=None,
            telegram_file_service: Optional[TelegramFileService] = None,
            approval_manager=None,
            config_path: Optional[str] = None
    ):
        super().__init__(event_bus)
        self.state_manager = state_manager
        self.telegram_file_service = telegram_file_service
        self.approval_manager = approval_manager

        self.config = self._load_config(config_path)
        printing_config = self.config.get('printing', {})

        self.enabled = printing_config.get('enabled', True)
        self.uploads_dir = printing_config.get('uploads_dir', 'data/uploads')
        self.state_dir = printing_config.get('state_dir', 'state/prints')

        self.printer_manager = PrinterManager()
        self.rules_service = PrintRulesService()

        print_mode = self.printer_manager.get_print_mode()
        self.print_service = CupsService.create(
            mode=print_mode,
            simulation_dir=os.path.join(self.uploads_dir, 'simulation')
        )

        self.llm_service = LLMService()
        self.model_manager = ModelManager()
        self.decision_service = PrintDecisionService(self.llm_service, self.model_manager)

        os.makedirs(self.uploads_dir, exist_ok=True)
        os.makedirs(self.state_dir, exist_ok=True)

        if self.event_bus and self.enabled:
            self._subscribe_to_events()

        logger.info(
            f"Smart PrintAgent inicializado (modo: {print_mode}, IA: {'habilitada' if self.rules_service.should_use_ai() else 'deshabilitada'})")

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(base_dir, "config", "notifications.yaml")
        if not os.path.exists(config_path):
            return {}
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error cargando config: {e}")
            return {}

    def _subscribe_to_events(self) -> None:
        self.event_bus.subscribe("document.received", self.handle_document_received)
        self.event_bus.subscribe("document.analysis_requested", self.handle_analysis_requested)  # 🆕
        self.event_bus.subscribe("print.approval_response", self.handle_approval_response)
        logger.info(
            "📡 Smart PrintAgent suscrito a: document.received, document.analysis_requested, print.approval_response")

    # ============================================================
    # 🆕 NUEVO: MANEJO DE SOLO ANÁLISIS (SIN IMPRIMIR)
    # ============================================================
    def handle_analysis_requested(self, event: Event) -> None:
        """Maneja un documento recibido SOLO para análisis, sin imprimir."""
        payload = event.payload
        print_job_id = payload.get('print_job_id')
        file_id = payload.get('file_id')
        file_name = payload.get('file_name', 'documento')
        chat_id = payload.get('telegram_chat_id')
        username = payload.get('telegram_username', 'usuario')

        logger.info(f"🔍 Modo Análisis: Procesando {print_job_id} ({file_name})")

        try:
            # 1. Descargar archivo
            download_result = self.telegram_file_service.download_file(
                file_id=file_id, job_id=print_job_id, original_filename=file_name
            )
            if download_result.get('status') != 'success':
                raise RuntimeError(f"Error descargando: {download_result.get('error')}")

            file_path = download_result['local_path']

            # 2. Analizar documento
            analysis = self._analyze_document(file_path, print_job_id)
            if analysis.get('status') != 'success':
                raise RuntimeError(f"Error analizando: {analysis.get('error')}")

            doc_type = analysis.get('document_type', 'other')
            confidence = analysis.get('confidence', 0.0)
            fields = analysis.get('fields', {})
            processing_time = analysis.get('processing_time', 0.0)

            # 3. Formatear respuesta para Telegram
            fields_text = "\n".join(
                [f"  • <b>{k.replace('_', ' ').title()}:</b> {v}" for k, v in list(fields.items())[:8]])
            if len(fields) > 8:
                fields_text += f"\n  • <i>... y {len(fields) - 8} campos más</i>"
            elif not fields:
                fields_text = "  • <i>No se extrajeron campos relevantes</i>"

            message = (
                f"🔍 <b>Análisis Completado</b>\n\n"
                f"📄 <b>Archivo:</b> {file_name}\n"
                f"🏷️ <b>Tipo:</b> {doc_type}\n"
                f"🎯 <b>Confianza:</b> {confidence:.2%}\n"
                f"⏱️ <b>Tiempo:</b> {processing_time:.2f}s\n\n"
                f"📦 <b>Campos Extraídos:</b>\n{fields_text}\n\n"
                f"✅ <i>Documento analizado correctamente. No se realizó ninguna impresión.</i>"
            )

            self._send_telegram_message(chat_id, message)
            logger.info(f"✅ Análisis completado y notificado para {print_job_id}")

        except Exception as e:
            logger.error(f"❌ Error en análisis {print_job_id}: {e}", exc_info=True)
            self._notify_error(chat_id, print_job_id, file_name, str(e))

    # ============================================================
    # FLUJO PRINCIPAL DE IMPRESIÓN (EXISTENTE)
    # ============================================================
    def handle_document_received(self, event: Event) -> None:
        payload = event.payload
        print_job_id = payload.get('print_job_id')
        file_id = payload.get('file_id')
        file_name = payload.get('file_name', 'documento')
        chat_id = payload.get('telegram_chat_id')
        username = payload.get('telegram_username', 'usuario')
        caption = payload.get('caption', '')

        logger.info(f"📄 Smart PrintAgent procesando: {print_job_id} ({file_name}) | Caption: '{caption}'")
        state = self._create_print_state(print_job_id, payload)

        try:
            self._update_print_state(state, "DOWNLOADING")
            self._publish_event("print.started",
                                {"print_job_id": print_job_id, "file_name": file_name, "username": username,
                                 "stage": "downloading"})

            download_result = self.telegram_file_service.download_file(file_id=file_id, job_id=print_job_id,
                                                                       original_filename=file_name)
            if download_result.get('status') != 'success':
                raise RuntimeError(f"Error descargando: {download_result.get('error')}")

            file_path = download_result['local_path']
            self._update_print_state(state, "DOWNLOADED", {"file_path": file_path})

            caption_parser = CaptionParserService()
            user_instructions = caption_parser.parse(caption)
            if user_instructions["has_instructions"]:
                logger.info(f"📝 Instrucciones del usuario detectadas: {user_instructions}")
                self._update_print_state(state, "CAPTION_PARSED", {"user_instructions": user_instructions})

            self._update_print_state(state, "ANALYZING")
            self._publish_event("print.started",
                                {"print_job_id": print_job_id, "file_name": file_name, "username": username,
                                 "stage": "analyzing"})

            analysis = self._analyze_document(file_path, print_job_id)
            if analysis.get('status') != 'success':
                raise RuntimeError(f"Error analizando: {analysis.get('error')}")

            doc_type = analysis.get('document_type', 'other')
            confidence = analysis.get('confidence', 0.0)
            fields = analysis.get('fields', {})
            raw_text = analysis.get('raw_text', '')

            self._update_print_state(state, "ANALYZED",
                                     {"document_type": doc_type, "confidence": confidence, "fields": fields})

            self._update_print_state(state, "DECIDING")
            decision = self.decision_service.decide(document_type=doc_type, confidence=confidence, fields=fields,
                                                    raw_text=raw_text, file_name=file_name)

            if user_instructions["has_instructions"]:
                if user_instructions["copies"] is not None:
                    decision["copies"] = caption_parser.validate_copies(user_instructions["copies"])
                    decision["decision_source"] = "user_override"
                if user_instructions["printer_group"] is not None:
                    decision["printer_group"] = user_instructions["printer_group"]
                    decision["decision_source"] = "user_override"
                decision["requires_approval"] = False

            self._update_print_state(state, "DECIDED", {"decision": decision})
            self._publish_event("print.decision_made",
                                {"print_job_id": print_job_id, "decision": decision, "document_type": doc_type,
                                 "user_caption": caption})

            if not decision.get('should_print', False):
                self._update_print_state(state, "SKIPPED", {"reason": decision.get('reason', 'No requiere impresión')})
                self._notify_skipped(chat_id, print_job_id, file_name, decision, doc_type, fields)
                self._publish_event("print.skipped", {"print_job_id": print_job_id, "reason": decision.get('reason')})
                return

            printer_group = decision.get('printer_group', 'general')
            printer = self.printer_manager.get_printer_for_group(printer_group)

            if decision.get('requires_approval', False):
                self._request_approval_and_print(state=state, print_job_id=print_job_id, chat_id=chat_id,
                                                 file_name=file_name, file_path=file_path, printer=printer,
                                                 printer_group=printer_group, copies=decision.get('copies', 1),
                                                 doc_type=doc_type, fields=fields, decision=decision, username=username)
            else:
                self._execute_print(state=state, print_job_id=print_job_id, chat_id=chat_id, file_name=file_name,
                                    file_path=file_path, printer=printer, printer_group=printer_group,
                                    copies=decision.get('copies', 1), doc_type=doc_type, fields=fields,
                                    decision=decision, username=username)

        except Exception as e:
            logger.error(f"❌ Error en Smart PrintAgent {print_job_id}: {e}", exc_info=True)
            self._update_print_state(state, "FAILED", {"error": str(e)})
            self._publish_event("print.failed", {"print_job_id": print_job_id, "file_name": file_name, "error": str(e)})
            self._notify_error(chat_id, print_job_id, file_name, str(e))

    def _analyze_document(self, file_path: str, job_id: str) -> Dict[str, Any]:
        try:
            from agents.functional.document_agent import DocumentAgent
            doc_agent = DocumentAgent(event_bus=None, state_manager=None)
            result = doc_agent.execute("process", {"file_path": file_path, "job_id": job_id})
            if result.get('status') != 'success':
                return {"status": "error", "error": result.get('result', 'Error desconocido')}
            return {"status": "success", "document_type": result.get('document_type', 'other'),
                    "confidence": result.get('confidence', 0.0), "fields": result.get('fields', {}),
                    "raw_text": result.get('raw_text', ''), "processing_time": result.get('processing_time', 0.0)}
        except Exception as e:
            logger.error(f"Error analizando documento: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def _request_approval_and_print(self, state: Dict[str, Any], print_job_id: str, chat_id: str, file_name: str,
                                    file_path: str, printer: str, printer_group: str, copies: int, doc_type: str,
                                    fields: Dict[str, Any], decision: Dict[str, Any], username: str) -> None:
        approval_id = f"PRTAPR-{uuid.uuid4().hex[:8].upper()}"
        print_data = {"print_job_id": print_job_id, "chat_id": chat_id, "file_name": file_name, "file_path": file_path,
                      "printer": printer, "printer_group": printer_group, "copies": copies, "doc_type": doc_type,
                      "fields": fields, "decision": decision, "username": username, "state": state}
        with PrintAgent._decisions_lock:
            PrintAgent._pending_decisions[approval_id] = print_data
        self._update_print_state(state, "WAITING_APPROVAL", {"approval_id": approval_id})
        self._send_print_confirmation(chat_id=chat_id, print_job_id=print_job_id, approval_id=approval_id,
                                      file_name=file_name, printer=printer, printer_group=printer_group, copies=copies,
                                      doc_type=doc_type, fields=fields, decision=decision)
        logger.info(f"⏸️ Aprobación solicitada: {approval_id} para {print_job_id}")

    def handle_approval_response(self, event: Event) -> None:
        payload = event.payload
        approval_id = payload.get('approval_id')
        action = payload.get('action')
        with PrintAgent._decisions_lock:
            print_data = PrintAgent._pending_decisions.pop(approval_id, None)
        if not print_data:
            logger.warning(f"Aprobación no encontrada o ya procesada: {approval_id}")
            return
        if action == 'approved':
            logger.info(f"✅ Impresión aprobada: {approval_id}")
            self._execute_print(state=print_data['state'], print_job_id=print_data['print_job_id'],
                                chat_id=print_data['chat_id'], file_name=print_data['file_name'],
                                file_path=print_data['file_path'], printer=print_data['printer'],
                                printer_group=print_data['printer_group'], copies=print_data['copies'],
                                doc_type=print_data['doc_type'], fields=print_data['fields'],
                                decision=print_data['decision'], username=print_data['username'])
        else:
            logger.info(f"❌ Impresión rechazada: {approval_id}")
            self._update_print_state(print_data['state'], "CANCELLED", {"reason": "Rechazada por el usuario"})
            self._publish_event("print.cancelled",
                                {"print_job_id": print_data['print_job_id'], "approval_id": approval_id})
            self._notify_cancelled(print_data['chat_id'], print_data['print_job_id'], print_data['file_name'])

    def _execute_print(self, state: Dict[str, Any], print_job_id: str, chat_id: str, file_name: str, file_path: str,
                       printer: str, printer_group: str, copies: int, doc_type: str, fields: Dict[str, Any],
                       decision: Dict[str, Any], username: str) -> None:
        try:
            self._update_print_state(state, "PRINTING")
            self._publish_event("print.started",
                                {"print_job_id": print_job_id, "file_name": file_name, "stage": "printing",
                                 "printer": printer})
            print_result = self.print_service.print_file(file_path=file_path, job_id=print_job_id, printer=printer,
                                                         copies=copies)
            if print_result.get('status') != 'success':
                raise RuntimeError(f"Error imprimiendo: {print_result.get('error')}")
            self._update_print_state(state, "COMPLETED",
                                     {"cups_job_id": print_result.get('cups_job_id'), "printer": printer,
                                      "printer_group": printer_group, "copies": copies,
                                      "simulated": print_result.get('simulated', False)})
            self._publish_event("print.completed",
                                {"print_job_id": print_job_id, "file_name": file_name, "printer": printer,
                                 "printer_group": printer_group, "copies": copies, "username": username,
                                 "simulated": print_result.get('simulated', False)})
            logger.info(f"✅ Impresión completada: {print_job_id} en {printer}")
            self._notify_completed(chat_id, print_job_id, file_name, printer, copies, print_result)
        except Exception as e:
            logger.error(f"❌ Error imprimiendo {print_job_id}: {e}", exc_info=True)
            self._update_print_state(state, "FAILED", {"error": str(e)})
            self._publish_event("print.failed", {"print_job_id": print_job_id, "error": str(e)})
            self._notify_error(chat_id, print_job_id, file_name, str(e))

    def _send_print_confirmation(self, chat_id: str, print_job_id: str, approval_id: str, file_name: str, printer: str,
                                 printer_group: str, copies: int, doc_type: str, fields: Dict[str, Any],
                                 decision: Dict[str, Any]) -> None:
        summary_parts = [f"  • <b>{k.replace('_', ' ').title()}:</b> {v}" for k, v in list(fields.items())[:4]]
        summary = "\n".join(summary_parts) if summary_parts else "  • Sin campos relevantes"
        message = (
            f"📄 <b>Documento Detectado - Requiere Aprobación</b>\n\n🏷️ <b>Tipo:</b> {doc_type}\n📄 <b>Archivo:</b> {file_name}\n🆔 <b>Job:</b> <code>{print_job_id}</code>\n\n📦 <b>Campos:</b>\n{summary}\n\n🖨️ <b>Estrategia de Impresión:</b>\n  • Impresora: {printer}\n  • Grupo: {printer_group}\n  • Copias: {copies}\n  • Prioridad: {decision.get('priority', 'normal')}\n  • Razón: {decision.get('reason', 'N/A')}\n\n👇 <b>¿Desea imprimir?</b>")
        inline_keyboard = {"inline_keyboard": [[{"text": "✅ Imprimir", "callback_data": f"print_approve:{approval_id}"},
                                                {"text": "❌ Cancelar",
                                                 "callback_data": f"print_reject:{approval_id}"}]]}
        try:
            if self.telegram_file_service:
                requests.post(f"{self.telegram_file_service.base_url}/sendMessage",
                              json={"chat_id": chat_id, "text": message, "parse_mode": "HTML",
                                    "reply_markup": inline_keyboard}, timeout=10)
        except Exception as e:
            logger.error(f"Error enviando confirmación: {e}")

    def _notify_completed(self, chat_id: str, print_job_id: str, file_name: str, printer: str, copies: int,
                          print_result: Dict[str, Any]) -> None:
        simulated = print_result.get('simulated', False)
        mode_text = "SIMULACIÓN" if simulated else "REAL"
        icon = "🧪" if simulated else "🖨️"
        message = f"{icon} <b>Impresión {mode_text} Completada</b>\n\n📄 <b>Archivo:</b> {file_name}\n🆔 <b>Job:</b> <code>{print_job_id}</code>\n🖨️ <b>Impresora:</b> {printer}\n📋 <b>Copias:</b> {copies}\n🕐 <b>Hora:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n✅ <b>Estado:</b> COMPLETADO"
        self._send_telegram_message(chat_id, message)

    def _notify_skipped(self, chat_id: str, print_job_id: str, file_name: str, decision: Dict[str, Any], doc_type: str,
                        fields: Dict[str, Any]) -> None:
        message = f"🚫 <b>Documento No Requiere Impresión</b>\n\n📄 <b>Archivo:</b> {file_name}\n🆔 <b>Job:</b> <code>{print_job_id}</code>\n🏷️ <b>Tipo:</b> {doc_type}\n📝 <b>Razón:</b> {decision.get('reason', 'No especificada')}\n\nℹ️ El documento fue analizado pero no requiere impresión física."
        self._send_telegram_message(chat_id, message)

    def _notify_cancelled(self, chat_id: str, print_job_id: str, file_name: str) -> None:
        message = f"❌ <b>Impresión Cancelada</b>\n\n📄 <b>Archivo:</b> {file_name}\n🆔 <b>Job:</b> <code>{print_job_id}</code>\n🕐 <b>Hora:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        self._send_telegram_message(chat_id, message)

    def _notify_error(self, chat_id: str, print_job_id: str, file_name: str, error: str) -> None:
        message = f"❌ <b>Error en Impresión/Análisis</b>\n\n📄 <b>Archivo:</b> {file_name}\n🆔 <b>Job:</b> <code>{print_job_id}</code>\n🔴 <b>Error:</b> {error[:200]}\n🕐 <b>Hora:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        self._send_telegram_message(chat_id, message)

    def _send_telegram_message(self, chat_id: str, text: str) -> None:
        if not self.telegram_file_service or not chat_id:
            return
        try:
            requests.post(f"{self.telegram_file_service.base_url}/sendMessage",
                          json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")

    def _create_print_state(self, print_job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        state = {"print_job_id": print_job_id, "status": "RECEIVED", "file_name": payload.get('file_name'),
                 "file_size": payload.get('file_size'), "extension": payload.get('extension'),
                 "username": payload.get('telegram_username'), "chat_id": payload.get('telegram_chat_id'),
                 "created_at": now, "updated_at": now, "history": [{"status": "RECEIVED", "timestamp": now}]}
        self._save_print_state(state)
        return state

    def _update_print_state(self, state: Dict[str, Any], new_status: str, extra: Optional[Dict] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        state["status"] = new_status
        state["updated_at"] = now
        if extra:
            state.update(extra)
        state["history"].append({"status": new_status, "timestamp": now})
        self._save_print_state(state)

    def _save_print_state(self, state: Dict[str, Any]) -> None:
        file_path = os.path.join(self.state_dir, f"{state['print_job_id']}.json")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error guardando estado: {e}")

    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self.event_bus:
            self.event_bus.publish(Event(event_type=event_type, source=self.name, payload=payload))

    def execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if action == "list_printers":
            return {"status": "success", "printers": self.print_service.list_printers(),
                    "groups": self.printer_manager.get_all_groups(), "mode": self.printer_manager.get_print_mode()}
        elif action == "print_status":
            print_job_id = payload.get('print_job_id')
            if not print_job_id:
                return {"status": "error", "result": "Falta print_job_id"}
            state_file = os.path.join(self.state_dir, f"{print_job_id}.json")
            if not os.path.exists(state_file):
                return {"status": "error", "result": f"Job no encontrado: {print_job_id}"}
            with open(state_file, 'r', encoding='utf-8') as f:
                return {"status": "success", "state": json.load(f)}
        return {"status": "error", "result": f"Acción no soportada: {action}"}