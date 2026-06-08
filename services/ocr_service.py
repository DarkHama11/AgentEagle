import os
import platform
import logging
from abc import ABC, abstractmethod
from typing import Optional
from pypdf import PdfReader
from PIL import Image
import pytesseract

logger = logging.getLogger("AgentEagle.OCRService")


class BaseOCRService(ABC):
    """Interfaz abstracta para servicios OCR."""

    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        """Extrae texto de un documento (PDF o imagen)."""
        pass


class TesseractOCRService(BaseOCRService):
    """
    Implementación de OCR usando Tesseract.
    Soporta PDFs con texto nativo, PDFs escaneados e imágenes.
    """

    def __init__(self, tesseract_cmd: Optional[str] = None, poppler_path: Optional[str] = None, lang: str = "spa+eng"):
        """
        :param tesseract_cmd: Ruta al ejecutable de Tesseract
        :param poppler_path: Ruta a la carpeta bin de Poppler
        :param lang: Idiomas para OCR
        """
        # Configurar Tesseract
        if tesseract_cmd is None and platform.system() == "Windows":
            default_windows_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(default_windows_path):
                tesseract_cmd = default_windows_path
                logger.info(f"Ruta de Tesseract detectada: {tesseract_cmd}")

        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        # Configurar Poppler con tu ruta específica
        self.poppler_path = poppler_path
        if poppler_path is None and platform.system() == "Windows":
            # Tu ruta específica de Poppler
            custom_poppler_path = r"D:\programa\Release-26.02.0-0\poppler-26.02.0\Library\bin"
            if os.path.exists(custom_poppler_path):
                self.poppler_path = custom_poppler_path
                logger.info(f"Ruta de Poppler detectada: {self.poppler_path}")
            else:
                logger.warning(f"Poppler no encontrado en: {custom_poppler_path}")

        self.lang = lang
        logger.info(f"TesseractOCRService inicializado con idiomas: {lang}")

    def extract_text(self, file_path: str) -> str:
        """Extrae texto de PDF o imagen."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        file_ext = os.path.splitext(file_path)[1].lower()

        try:
            if file_ext == ".pdf":
                return self._extract_from_pdf(file_path)
            elif file_ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
                return self._extract_from_image(file_path)
            else:
                raise ValueError(f"Formato no soportado: {file_ext}")
        except Exception as e:
            logger.error(f"Error en OCR para {file_path}: {e}", exc_info=True)
            raise

    def _extract_from_pdf(self, file_path: str) -> str:
        """Extrae texto de PDF (nativo o escaneado)."""
        logger.info(f"Extrayendo texto de PDF: {file_path}")

        try:
            reader = PdfReader(file_path)
            text_parts = []
            has_text = False

            # Intento 1: Extracción directa
            for page_num, page in enumerate(reader.pages, 1):
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text_parts.append(page_text)
                    has_text = True
                    logger.debug(f"Página {page_num}: {len(page_text)} caracteres (texto nativo)")
                else:
                    logger.warning(f"Página {page_num} no tiene texto extraíble")

            if has_text:
                full_text = "\n\n".join(text_parts)
                logger.info(f"Texto extraído (nativo): {len(full_text)} caracteres")
                return full_text

            # Intento 2: OCR para PDFs escaneados
            logger.info("Intentando OCR para PDF escaneado...")
            return self._extract_from_pdf_scanned(file_path, len(reader.pages))

        except Exception as e:
            logger.error(f"Error extrayendo texto de PDF: {e}", exc_info=True)
            raise

    def _extract_from_pdf_scanned(self, file_path: str, num_pages: int) -> str:
        """Extrae texto de PDF escaneado usando OCR."""
        try:
            from pdf2image import convert_from_path

            logger.info(f"Convirtiendo {num_pages} páginas a imágenes...")

            kwargs = {}
            if self.poppler_path:
                kwargs['poppler_path'] = self.poppler_path
                logger.info(f"Usando Poppler desde: {self.poppler_path}")

            # Convertir PDF a imágenes
            images = convert_from_path(file_path, **kwargs)

            text_parts = []
            for page_num, image in enumerate(images, 1):
                logger.info(f"Aplicando OCR a página {page_num}/{len(images)}...")
                page_text = pytesseract.image_to_string(image, lang=self.lang)

                if page_text and page_text.strip():
                    text_parts.append(page_text)
                    logger.info(f"Página {page_num}: {len(page_text)} caracteres (OCR)")
                else:
                    logger.warning(f"Página {page_num}: No se pudo extraer texto")

            full_text = "\n\n".join(text_parts)
            logger.info(f"Texto extraído (OCR): {len(full_text)} caracteres")

            return full_text

        except ImportError:
            error_msg = "pdf2image no está instalado. Ejecuta: pip install pdf2image"
            logger.error(error_msg)
            raise ImportError(error_msg)
        except Exception as e:
            error_msg = f"Error en OCR de PDF escaneado: {e}"
            logger.error(error_msg, exc_info=True)

            if "poppler" in str(e).lower() or "pdftoppm" in str(e).lower():
                error_msg += f"\n\n💡 Verifica que Poppler esté en: {self.poppler_path}"

            raise RuntimeError(error_msg)

    def _extract_from_image(self, file_path: str) -> str:
        """Extrae texto de imagen usando Tesseract."""
        logger.info(f"Extrayendo texto de imagen: {file_path}")

        try:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image, lang=self.lang)
            logger.info(f"Texto extraído: {len(text)} caracteres")
            return text
        except Exception as e:
            logger.error(f"Error extrayendo texto de imagen: {e}", exc_info=True)
            raise