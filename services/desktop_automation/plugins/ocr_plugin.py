import os
import logging
from pathlib import Path

from ..base_plugin import BaseAutomationPlugin
from ..plugin_registry import PluginRegistry
from dto.desktop_automation.action_dto import ActionRequest, ActionResult
from ..auditor import AutomationAuditor

logger = logging.getLogger(__name__)

# Intentar importar pytesseract
try:
    import pytesseract
    from PIL import Image

    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("⚠️ pytesseract no está instalado. OCR no estará disponible.")


@PluginRegistry.register
class OCRPlugin(BaseAutomationPlugin):
    """Plugin para extraer texto de imágenes usando Tesseract OCR"""

    @property
    def action_type(self) -> str:
        return "OCR_IMAGE"

    def execute(self, request: ActionRequest, backend) -> ActionResult:
        session_id = request.session_id
        input_path = request.payload.get("input_path")
        output_path = request.payload.get("output_path")

        logger.info(f"[OCR] 📥 Procesando imagen: {input_path}")

        if not TESSERACT_AVAILABLE:
            return ActionResult(
                session_id, False,
                "pytesseract no está instalado. Ejecuta: pip install pytesseract",
                "DependencyMissing"
            )

        if not os.path.exists(input_path):
            return ActionResult(session_id, False, "Archivo no encontrado", "FileNotFound")

        try:
            AutomationAuditor.log_action(session_id, "START", "INFO", input_path)

            # Abrir imagen
            logger.info("[OCR] 1. Abriendo imagen...")
            image = Image.open(input_path)

            # Configurar idioma (español + inglés)
            logger.info("[OCR] 2. Ejecutando OCR (español + inglés)...")
            texto = pytesseract.image_to_string(image, lang='spa+eng')

            if not texto.strip():
                logger.warning("[OCR] ⚠️ No se detectó texto en la imagen")
                texto = "[No se detectó texto en la imagen]"

            # Guardar resultado
            # Cambiar extensión a .txt
            if output_path:
                txt_path = str(Path(output_path).with_suffix('.txt'))
            else:
                txt_path = str(Path(input_path).with_suffix('.txt'))

            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(texto)

            logger.info(f"[OCR] ✅ Texto extraído: {len(texto)} caracteres")
            logger.info(f"[OCR] 💾 Guardado en: {txt_path}")

            AutomationAuditor.log_action(session_id, "COMPLETE", "SUCCESS", txt_path)

            return ActionResult(
                session_id,
                True,
                f"OCR completado. {len(texto)} caracteres extraídos.",
                output_data={"output_path": txt_path, "text": texto}
            )

        except Exception as e:
            logger.error(f"[OCR] ❌ Error: {e}", exc_info=True)
            return ActionResult(session_id, False, "Error durante OCR", str(e))

    def cleanup(self, backend):
        pass


@PluginRegistry.register
class OCRPdfPlugin(BaseAutomationPlugin):
    """Plugin para OCR de PDFs escaneados"""

    @property
    def action_type(self) -> str:
        return "OCR_PDF"

    def execute(self, request: ActionRequest, backend) -> ActionResult:
        session_id = request.session_id
        input_path = request.payload.get("input_path")
        output_path = request.payload.get("output_path")

        logger.info(f"[OCR-PDF] 📥 Procesando PDF: {input_path}")

        if not TESSERACT_AVAILABLE:
            return ActionResult(
                session_id, False,
                "pytesseract no está instalado.",
                "DependencyMissing"
            )

        try:
            # Importar pdf2image
            try:
                from pdf2image import convert_from_path
            except ImportError:
                return ActionResult(
                    session_id, False,
                    "pdf2image no está instalado. Ejecuta: pip install pdf2image",
                    "DependencyMissing"
                )

            AutomationAuditor.log_action(session_id, "START", "INFO", input_path)

            # Convertir PDF a imágenes
            logger.info("[OCR-PDF] 1. Convirtiendo PDF a imágenes...")
            images = convert_from_path(input_path, dpi=300)
            logger.info(f"[OCR-PDF] 📄 {len(images)} páginas detectadas")

            # OCR de cada página
            texto_completo = []
            for i, image in enumerate(images, 1):
                logger.info(f"[OCR-PDF] 2.{i}. Procesando página {i}/{len(images)}...")
                texto = pytesseract.image_to_string(image, lang='spa+eng')
                texto_completo.append(f"=== PÁGINA {i} ===\n{texto}")

            texto_final = "\n\n".join(texto_completo)

            # Guardar resultado
            if output_path:
                txt_path = str(Path(output_path).with_suffix('.txt'))
            else:
                txt_path = str(Path(input_path).with_suffix('.txt'))

            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(texto_final)

            logger.info(f"[OCR-PDF] ✅ Texto extraído: {len(texto_final)} caracteres")

            AutomationAuditor.log_action(session_id, "COMPLETE", "SUCCESS", txt_path)

            return ActionResult(
                session_id,
                True,
                f"OCR de PDF completado. {len(images)} páginas procesadas.",
                output_data={"output_path": txt_path, "text": texto_final}
            )

        except Exception as e:
            logger.error(f"[OCR-PDF] ❌ Error: {e}", exc_info=True)
            return ActionResult(session_id, False, "Error durante OCR de PDF", str(e))

    def cleanup(self, backend):
        pass