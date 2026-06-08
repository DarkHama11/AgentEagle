import os
import logging
import fitz  # PyMuPDF
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("AgentEagle.LayoutReconstructionService")


class LayoutReconstructionService:
    """
    Servicio que reconstruye documentos PDF de dos columnas (como Hojas de Vida)
    a un Word lineal y lógicamente ordenado, separando la barra lateral del contenido principal.

    Usa PyMuPDF para leer coordenadas de bloques de texto y python-docx para generar
    un Word limpio con el orden lógico correcto.
    """

    def __init__(self):
        logger.info("LayoutReconstructionService inicializado")

    def reconstruct_pdf_to_word(self, pdf_path: str, output_docx_path: str) -> Dict[str, Any]:
        """
        Convierte un PDF a Word reconstruyendo su diseño lógico.
        Detecta automáticamente si hay columnas y separa sidebar del contenido principal.
        """
        try:
            doc = fitz.open(pdf_path)
            new_doc = Document()

            # Configurar estilos básicos
            style = new_doc.styles['Normal']
            font = style.font
            font.name = 'Calibri'
            font.size = Pt(11)

            logger.info(f"🧠 Analizando estructura lógica de: {pdf_path}")

            for page_num in range(len(doc)):
                page = doc[page_num]
                blocks = page.get_text("dict")["blocks"]

                # Separar bloques en Columna Izquierda (Sidebar) y Derecha (Main)
                sidebar_blocks = []
                main_blocks = []

                # Calcular el ancho de la página para detectar columnas dinámicamente
                page_width = page.rect.width
                # Umbral: si un bloque empieza antes del 45% del ancho, es sidebar
                sidebar_threshold = page_width * 0.45

                for block in blocks:
                    if "lines" in block:
                        # Unir todo el texto del bloque
                        text = " ".join([line["spans"][0]["text"] for line in block["lines"]]).strip()
                        if text:
                            x0 = block["bbox"][0]  # Coordenada X inicial

                            # 🧠 Lógica dinámica de detección de columnas
                            if x0 < sidebar_threshold:
                                sidebar_blocks.append(text)
                            else:
                                main_blocks.append(text)

                # 📝 1. Escribir el Contenido Principal (Experiencia, Estudios, etc.)
                if main_blocks:
                    self._add_section(new_doc, "📄 CONTENIDO PRINCIPAL", main_blocks)

                # 📝 2. Escribir la Barra Lateral (Referencias, Programas, Idiomas)
                if sidebar_blocks:
                    new_doc.add_page_break()  # Nueva página para que quede ordenado
                    self._add_section(new_doc, "📑 INFORMACIÓN ADICIONAL (Barra Lateral)", sidebar_blocks)

            new_doc.save(output_docx_path)
            doc.close()

            logger.info(f"✅ Word reconstruido lógicamente guardado en: {output_docx_path}")
            return {
                "status": "success",
                "output_path": output_docx_path,
                "engine": "layout_reconstruction"
            }

        except Exception as e:
            logger.error(f"❌ Error en LayoutReconstructionService: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def _add_section(self, doc: Document, title: str, blocks: List[str]):
        """Agrega una sección al documento Word con títulos y párrafos."""
        doc.add_heading(title, level=2)
        for text in blocks:
            # Detectar si es un título (texto en mayúsculas y corto)
            if text.isupper() and len(text) < 50 and not text.startswith("•"):
                doc.add_heading(text, level=3)
            else:
                doc.add_paragraph(text)