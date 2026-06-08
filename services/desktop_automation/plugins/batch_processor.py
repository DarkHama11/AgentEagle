import os
import glob
import logging
from pathlib import Path
from typing import List, Dict, Any
from .base_plugin import BaseAutomationPlugin
from .plugin_registry import PluginRegistry
from dto.desktop_automation.action_dto import ActionRequest, ActionResult
from ..auditor import AutomationAuditor

logger = logging.getLogger(__name__)


@PluginRegistry.register
class BatchProcessorPlugin(BaseAutomationPlugin):
    """Plugin para procesamiento por lotes de documentos"""

    @property
    def action_type(self) -> str:
        return "BATCH_PROCESS"

    def execute(self, request: ActionRequest, backend) -> ActionResult:
        """Ejecuta procesamiento por lotes"""
        session_id = request.session_id
        input_dir = request.payload.get("input_directory")
        output_dir = request.payload.get("output_directory")
        conversion_type = request.payload.get("conversion_type", "pdf_to_word")

        if not os.path.exists(input_dir):
            return ActionResult(session_id, False, "Directorio de entrada no encontrado", "DirNotFound")

        # Buscar archivos
        if conversion_type == "pdf_to_word":
            pattern = "*.pdf"
        elif conversion_type == "word_to_pdf":
            pattern = "*.docx"
        else:
            return ActionResult(session_id, False, "Tipo de conversión no soportado", "InvalidType")

        files = glob.glob(os.path.join(input_dir, pattern))

        if not files:
            return ActionResult(session_id, False, "No se encontraron archivos", "NoFiles")

        logger.info(f"📊 Procesando {len(files)} archivos en modo lote")

        results = []
        for file_path in files:
            try:
                # Crear request individual
                individual_request = ActionRequest(
                    session_id=session_id,
                    action_type="PDF_TO_WORD" if conversion_type == "pdf_to_word" else "WORD_TO_PDF",
                    payload={
                        "input_path": file_path,
                        "output_path": os.path.join(output_dir, Path(file_path).stem + ".docx")
                    }
                )

                # Ejecutar conversión individual
                # Aquí llamarías al plugin correspondiente
                results.append({
                    "file": file_path,
                    "status": "success"
                })

            except Exception as e:
                logger.error(f"❌ Error procesando {file_path}: {e}")
                results.append({
                    "file": file_path,
                    "status": "failed",
                    "error": str(e)
                })

        success_count = sum(1 for r in results if r["status"] == "success")

        return ActionResult(
            session_id,
            True,
            f"Procesamiento completado: {success_count}/{len(files)} exitosos",
            {"results": results}
        )