import os
import time
import logging
from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent
from event_bus.event import Event

logger = logging.getLogger("AgentEagle.DocumentAgent")


class DocumentAgent(BaseAgent):
    """
    Agente especializado en procesamiento de documentos.
    Capacidades: OCR, clasificación, extracción de datos.
    """

    name = "document_agent"
    description = "Agente para OCR, clasificación y extracción de datos de documentos."
    capabilities = ["ocr", "classify", "extract", "process"]

    def __init__(self, event_bus=None, state_manager=None):
        super().__init__(event_bus)
        self.state_manager = state_manager

        # Servicios se inicializarán de forma perezosa
        self._ocr_service = None
        self._llm_service = None
        self._model_manager = None
        self._classification_service = None
        self._extraction_service = None

        logger.info("DocumentAgent inicializado")

    def _ensure_services_initialized(self):
        """Inicializa los servicios solo si no están creados aún."""
        if self._ocr_service is None:
            from services.ocr_service import TesseractOCRService
            from services.llm_service import LLMService
            from services.model_manager import ModelManager
            from services.classification_service import ClassificationService
            from services.extraction_service import ExtractionService

            logger.info("Inicializando servicios del DocumentAgent (lazy init)...")
            self._ocr_service = TesseractOCRService()
            self._llm_service = LLMService()
            self._model_manager = ModelManager()
            self._classification_service = ClassificationService(self._llm_service, self._model_manager)
            self._extraction_service = ExtractionService(self._llm_service, self._model_manager)

    @property
    def ocr_service(self):
        self._ensure_services_initialized()
        return self._ocr_service

    @property
    def llm_service(self):
        self._ensure_services_initialized()
        return self._llm_service

    @property
    def model_manager(self):
        self._ensure_services_initialized()
        return self._model_manager

    @property
    def classification_service(self):
        self._ensure_services_initialized()
        return self._classification_service

    @property
    def extraction_service(self):
        self._ensure_services_initialized()
        return self._extraction_service

    def execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta una acción específica del DocumentAgent."""
        start_time = time.time()

        logger.info(f"🔥 DocumentAgent.execute() llamado con acción: '{action}'")
        logger.info(f"📦 Payload recibido: {payload}")

        try:
            if action == "ocr":
                result = self._action_ocr(payload)
            elif action == "classify":
                result = self._action_classify(payload)
            elif action == "extract":
                result = self._action_extract(payload)
            elif action == "process":
                result = self._action_process(payload)
            else:
                result = {
                    "status": "error",
                    "result": f"Acción '{action}' no soportada por DocumentAgent"
                }

            processing_time = time.time() - start_time
            logger.info(f"✅ Acción '{action}' completada en {processing_time:.2f}s")

            return result

        except Exception as e:
            logger.error(f"❌ Error ejecutando acción '{action}': {e}", exc_info=True)
            return {
                "status": "error",
                "result": str(e)
            }

    def _action_ocr(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Acción: Extraer texto de un documento."""
        file_path = payload.get("file_path")
        if not file_path:
            return {"status": "error", "result": "Falta 'file_path' en el payload"}

        job_id = payload.get("job_id", "UNKNOWN")

        logger.info(f"📄 Iniciando OCR para: {file_path}")

        # Actualizar estado
        if self.state_manager:
            self.state_manager.update_step_status(job_id, "OCR_RUNNING")

        # Publicar evento de inicio
        if self.event_bus:
            self.event_bus.publish(Event(
                event_type="document.ocr_started",
                source=self.name,
                payload={"job_id": job_id, "file_path": file_path}
            ))

        try:
            text = self.ocr_service.extract_text(file_path)
            logger.info(f"✅ OCR completado: {len(text)} caracteres extraídos")

            # Actualizar estado
            if self.state_manager:
                self.state_manager.update_step_status(job_id, "OCR_COMPLETED")

            # Publicar evento de completado
            if self.event_bus:
                self.event_bus.publish(Event(
                    event_type="document.ocr_completed",
                    source=self.name,
                    payload={
                        "job_id": job_id,
                        "file_path": file_path,
                        "text_length": len(text)
                    }
                ))

            return {
                "status": "success",
                "text": text,
                "file_path": file_path
            }

        except Exception as e:
            logger.error(f"❌ Error en OCR: {e}", exc_info=True)
            if self.state_manager:
                self.state_manager.update_step_status(job_id, "OCR_FAILED")
            return {"status": "error", "result": str(e)}

    def _action_classify(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Acción: Clasificar un documento."""
        text = payload.get("text")
        if not text:
            return {"status": "error", "result": "Falta 'text' en el payload"}

        job_id = payload.get("job_id", "UNKNOWN")

        logger.info(f"🔍 Iniciando clasificación de documento ({len(text)} caracteres)")

        if self.state_manager:
            self.state_manager.update_step_status(job_id, "CLASSIFICATION_RUNNING")

        if self.event_bus:
            self.event_bus.publish(Event(
                event_type="document.classification_started",
                source=self.name,
                payload={"job_id": job_id}
            ))

        try:
            classification = self.classification_service.classify(text)
            logger.info(f"✅ Clasificación completada: {classification}")

            if self.state_manager:
                self.state_manager.update_step_status(job_id, "CLASSIFICATION_COMPLETED")

            if self.event_bus:
                self.event_bus.publish(Event(
                    event_type="document.classified",
                    source=self.name,
                    payload={
                        "job_id": job_id,
                        "document_type": classification["document_type"],
                        "confidence": classification["confidence"]
                    }
                ))

            return {
                "status": "success",
                "document_type": classification["document_type"],
                "confidence": classification["confidence"]
            }

        except Exception as e:
            logger.error(f"❌ Error en clasificación: {e}", exc_info=True)
            if self.state_manager:
                self.state_manager.update_step_status(job_id, "CLASSIFICATION_FAILED")
            return {"status": "error", "result": str(e)}

    def _action_extract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Acción: Extraer campos estructurados."""
        document_type = payload.get("document_type")
        text = payload.get("text")

        if not document_type or not text:
            return {"status": "error", "result": "Faltan 'document_type' o 'text' en el payload"}

        job_id = payload.get("job_id", "UNKNOWN")

        logger.info(f"📦 Iniciando extracción de campos para tipo: {document_type}")

        if self.state_manager:
            self.state_manager.update_step_status(job_id, "EXTRACTION_RUNNING")

        if self.event_bus:
            self.event_bus.publish(Event(
                event_type="document.extraction_started",
                source=self.name,
                payload={"job_id": job_id, "document_type": document_type}
            ))

        try:
            extraction = self.extraction_service.extract(document_type, text)
            logger.info(f"✅ Extracción completada: {extraction.get('extracted_count', 0)} campos")

            if self.state_manager:
                self.state_manager.update_step_status(job_id, "EXTRACTION_COMPLETED")

            if self.event_bus:
                self.event_bus.publish(Event(
                    event_type="document.extracted",
                    source=self.name,
                    payload={
                        "job_id": job_id,
                        "document_type": document_type,
                        "fields_count": extraction.get("extracted_count", 0)
                    }
                ))

            return {
                "status": "success",
                "fields": extraction.get("fields", {}),
                "extracted_count": extraction.get("extracted_count", 0)
            }

        except Exception as e:
            logger.error(f"❌ Error en extracción: {e}", exc_info=True)
            if self.state_manager:
                self.state_manager.update_step_status(job_id, "EXTRACTION_FAILED")
            return {"status": "error", "result": str(e)}

    def _action_process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Acción completa: OCR → Clasificación → Extracción → Resultado Final
        """
        file_path = payload.get("file_path")
        if not file_path:
            return {"status": "error", "result": "Falta 'file_path' en el payload"}

        job_id = payload.get("job_id", "UNKNOWN")
        start_time = time.time()

        logger.info(f"🚀 Iniciando procesamiento completo de documento: {file_path}")
        logger.info(f"📋 Job ID: {job_id}")

        try:
            # Paso 1: OCR
            logger.info("=" * 60)
            logger.info("PASO 1/3: OCR - Extrayendo texto del documento")
            logger.info("=" * 60)
            ocr_result = self._action_ocr({"file_path": file_path, "job_id": job_id})
            if ocr_result["status"] != "success":
                logger.error(f"❌ OCR falló: {ocr_result.get('result')}")
                return ocr_result

            text = ocr_result["text"]
            logger.info(f"✅ OCR exitoso: {len(text)} caracteres extraídos")

            # Validar que se extrajo texto suficiente
            if len(text.strip()) < 50:
                error_msg = f"No se pudo extraer texto suficiente del documento (solo {len(text)} caracteres). "
                error_msg += "El PDF puede ser una imagen sin texto o estar dañado."
                logger.error(f"❌ {error_msg}")
                return {
                    "status": "error",
                    "result": error_msg
                }

            # Paso 2: Clasificación
            logger.info("=" * 60)
            logger.info("PASO 2/3: CLASIFICACIÓN - Determinando tipo de documento")
            logger.info("=" * 60)
            classification_result = self._action_classify({"text": text, "job_id": job_id})
            if classification_result["status"] != "success":
                logger.error(f"❌ Clasificación falló: {classification_result.get('result')}")
                return classification_result

            document_type = classification_result["document_type"]
            confidence = classification_result["confidence"]
            logger.info(f"✅ Clasificación exitosa: tipo={document_type}, confianza={confidence}")

            # Paso 3: Extracción
            logger.info("=" * 60)
            logger.info("PASO 3/3: EXTRACCIÓN - Obteniendo campos estructurados")
            logger.info("=" * 60)
            extraction_result = self._action_extract({
                "document_type": document_type,
                "text": text,
                "job_id": job_id
            })

            fields = extraction_result.get("fields", {}) if extraction_result["status"] == "success" else {}
            logger.info(f"✅ Extracción completada: {len(fields)} campos extraídos")

            # Resultado final
            processing_time = time.time() - start_time

            final_result = {
                "status": "success",
                "document_type": document_type,
                "confidence": confidence,
                "fields": fields,
                "raw_text": text[:500] + "..." if len(text) > 500 else text,
                "processing_time": processing_time,
                "file_path": file_path
            }

            logger.info("=" * 60)
            logger.info("🎉 PROCESAMIENTO COMPLETADO EXITOSAMENTE")
            logger.info("=" * 60)
            logger.info(f"📄 Tipo: {document_type}")
            logger.info(f"🎯 Confianza: {confidence}")
            logger.info(f"📦 Campos: {fields}")
            logger.info(f"⏱️  Tiempo: {processing_time:.2f}s")

            # Publicar evento de proceso completo
            if self.event_bus:
                self.event_bus.publish(Event(
                    event_type="document.processed",
                    source=self.name,
                    payload={
                        "job_id": job_id,
                        "document_type": document_type,
                        "confidence": confidence,
                        "fields_count": len(fields),
                        "processing_time": processing_time
                    }
                ))

            return final_result

        except Exception as e:
            logger.error(f"❌ Error en procesamiento completo: {e}", exc_info=True)
            return {"status": "error", "result": str(e)}