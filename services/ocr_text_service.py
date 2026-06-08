import os
import logging
from typing import Dict, Any, Optional, List
from PIL import Image

logger = logging.getLogger("AgentEagle.OcrTextService")


class OcrTextService:
    """
    Servicio de OCR para extraer texto de imágenes.
    Usa Tesseract (ya instalado en el sistema).
    Soporta: PNG, JPG, JPEG, BMP, TIFF
    """

    SUPPORTED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif']

    def __init__(self, languages: str = "spa+eng"):
        self.languages = languages
        self._check_tesseract()
        logger.info(f"OcrTextService inicializado. Idiomas: {languages}")

    def _check_tesseract(self) -> None:
        """Verifica que Tesseract esté disponible."""
        try:
            import pytesseract
            # Intentar obtener versión para verificar que funciona
            pytesseract.get_tesseract_version()
            logger.info("✅ Tesseract disponible")
        except Exception as e:
            logger.warning(f"⚠️ Tesseract no está disponible: {e}")

    def extract_text_from_image(self, image_path: str, job_id: str) -> Dict[str, Any]:
        """
        Extrae texto de una imagen usando Tesseract OCR.

        :param image_path: Ruta a la imagen
        :param job_id: ID del job para tracking
        :return: Dict con status, text, confidence, etc.
        """
        if not os.path.exists(image_path):
            return {"status": "error", "error": f"Archivo no encontrado: {image_path}"}

        extension = os.path.splitext(image_path)[1].lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            return {
                "status": "error",
                "error": f"Formato no soportado: {extension}. Soportados: {', '.join(self.SUPPORTED_EXTENSIONS)}"
            }

        try:
            import pytesseract

            logger.info(f"🔍 Extrayendo texto de imagen: {image_path}")

            # Abrir imagen
            image = Image.open(image_path)

            # Preprocesamiento básico para mejorar OCR
            image = self._preprocess_image(image)

            # Extraer texto con Tesseract
            text = pytesseract.image_to_string(image, lang=self.languages)

            # Obtener datos detallados (confianza, boxes, etc.)
            data = pytesseract.image_to_data(image, lang=self.languages, output_type=pytesseract.Output.DICT)

            # Calcular confianza promedio
            confidences = [int(c) for c in data['conf'] if int(c) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            # Limpiar texto
            text = text.strip()

            if not text:
                return {
                    "status": "success",
                    "text": "",
                    "confidence": 0,
                    "word_count": 0,
                    "char_count": 0,
                    "message": "No se detectó texto en la imagen"
                }

            word_count = len(text.split())
            char_count = len(text)

            logger.info(
                f"✅ Texto extraído: {char_count} caracteres, {word_count} palabras, confianza: {avg_confidence:.1f}%")

            return {
                "status": "success",
                "text": text,
                "confidence": avg_confidence / 100,  # Normalizar a 0-1
                "word_count": word_count,
                "char_count": char_count,
                "languages": self.languages
            }

        except ImportError:
            logger.error("pytesseract no está instalado. Ejecuta: pip install pytesseract")
            return {"status": "error", "error": "pytesseract no instalado"}
        except Exception as e:
            logger.error(f"Error en OCR: {e}", exc_info=True)
            return {"status": "error", "error": f"Error en OCR: {str(e)}"}

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocesa la imagen para mejorar la precisión del OCR.
        - Convierte a escala de grises
        - Aumenta contraste si es necesario
        """
        try:
            # Convertir a escala de grises
            if image.mode != 'L':
                image = image.convert('L')

            # Aumentar tamaño si es muy pequeño (mejora OCR)
            width, height = image.size
            if width < 1000 or height < 1000:
                scale_factor = max(1000 / width, 1000 / height, 1.5)
                new_size = (int(width * scale_factor), int(height * scale_factor))
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            return image
        except Exception as e:
            logger.warning(f"Error en preprocesamiento de imagen: {e}")
            return image

    def extract_text_from_pdf(self, pdf_path: str, job_id: str) -> Dict[str, Any]:
        """
        Extrae texto de un PDF convirtiéndolo primero a imágenes.
        Útil para PDFs escaneados.
        """
        if not os.path.exists(pdf_path):
            return {"status": "error", "error": f"Archivo no encontrado: {pdf_path}"}

        try:
            import pytesseract
            from pdf2image import convert_from_path

            logger.info(f"🔍 Extrayendo texto de PDF: {pdf_path}")

            # Convertir PDF a imágenes
            images = convert_from_path(pdf_path)

            all_text = []
            total_confidence = 0

            for i, image in enumerate(images, 1):
                logger.info(f"  Procesando página {i}/{len(images)}")

                # Preprocesar
                image = self._preprocess_image(image)

                # OCR
                text = pytesseract.image_to_string(image, lang=self.languages)
                data = pytesseract.image_to_data(image, lang=self.languages, output_type=pytesseract.Output.DICT)

                confidences = [int(c) for c in data['conf'] if int(c) > 0]
                page_confidence = sum(confidences) / len(confidences) if confidences else 0
                total_confidence += page_confidence

                if text.strip():
                    all_text.append(f"--- Página {i} ---\n{text.strip()}")

            full_text = "\n\n".join(all_text)
            avg_confidence = total_confidence / len(images) if images else 0

            word_count = len(full_text.split())
            char_count = len(full_text)

            logger.info(f"✅ Texto extraído de PDF: {char_count} caracteres, {len(images)} páginas")

            return {
                "status": "success",
                "text": full_text,
                "confidence": avg_confidence / 100,
                "word_count": word_count,
                "char_count": char_count,
                "pages": len(images),
                "languages": self.languages
            }

        except ImportError as e:
            logger.error(f"Librería faltante: {e}. Instala: pip install pdf2image pytesseract")
            return {"status": "error", "error": f"Librería faltante: {str(e)}"}
        except Exception as e:
            logger.error(f"Error en OCR de PDF: {e}", exc_info=True)
            return {"status": "error", "error": f"Error en OCR: {str(e)}"}