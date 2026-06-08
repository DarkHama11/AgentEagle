import os
import re
import shutil
import logging
import subprocess
import platform
import time
import uuid
from typing import Dict, Any

logger = logging.getLogger("AgentEagle.ConversionService")


class ConversionService:
    """
    Servicio de conversión de documentos con múltiples motores:
    1. Stirling-PDF (prioridad 1) - Calidad premium, local
    2. MS Word COM (prioridad 2) - Buena calidad, local
    3. Layout Reconstruction (prioridad 3 para CVs) - Reconstrucción lógica
    4. pdf2docx (fallback) - Calidad básica, local
    """

    def __init__(self, output_dir: str = "data/conversions"):
        self.output_dir = output_dir
        self.temp_dir = os.path.join(output_dir, "_temp")
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)

        # Intentar desactivar el diálogo de conversión PDF en Word
        if platform.system() == "Windows":
            self._disable_pdf_conversion_dialog()

        logger.info(f"ConversionService inicializado. Output: {output_dir}")

    def _disable_pdf_conversion_dialog(self) -> None:
        """Modifica el registro de Windows para evitar el diálogo de Word."""
        try:
            import winreg
            office_versions = ['16.0', '15.0', '14.0']

            for version in office_versions:
                try:
                    key_path = f"Software\\Microsoft\\Office\\{version}\\Word\\Options"
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ)
                    winreg.SetValueEx(key, "DisableConvertPdfWarning", 0, winreg.REG_DWORD, 1)
                    winreg.CloseKey(key)
                    logger.info(f"✅ Diálogo de conversión PDF desactivado (Office {version})")
                    return
                except FileNotFoundError:
                    continue
                except Exception as e:
                    logger.debug(f"No se pudo modificar registro para Office {version}: {e}")
                    continue
        except Exception:
            pass

    # ============================================================
    # UTILIDADES DE ARCHIVOS
    # ============================================================

    def _sanitize_filename(self, filename: str) -> str:
        """Limpia el nombre del archivo."""
        filename = re.sub(r'\s+', ' ', filename).strip()
        problematic_chars = ['"', '*', '?', '<', '>', '|', ':']
        for char in problematic_chars:
            filename = filename.replace(char, '_')

        name, ext = os.path.splitext(filename)
        if len(name) > 90:
            name = name[:90]
        return name + ext

    def _create_temp_copy(self, source_path: str) -> str:
        """Crea una copia temporal del archivo."""
        original_name = os.path.basename(source_path)
        clean_name = self._sanitize_filename(original_name)

        unique_id = uuid.uuid4().hex[:8]
        name, ext = os.path.splitext(clean_name)
        temp_filename = f"{name}_{unique_id}{ext}"
        temp_path = os.path.join(self.temp_dir, temp_filename)

        shutil.copy2(source_path, temp_path)
        logger.info(f" Copia temporal creada: {temp_filename}")
        return temp_path

    def _cleanup_temp(self, temp_path: str) -> None:
        """Elimina archivo temporal."""
        try:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception as e:
            logger.warning(f"No se pudo eliminar temporal: {e}")

    # ============================================================
    # PDF → WORD
    # ============================================================

    def pdf_to_word(self, pdf_path: str, job_id: str, use_smart_reconstruct: bool = False) -> Dict[str, Any]:
        """
        Convierte PDF a Word.
        Si use_smart_reconstruct=True, usa el Layout Reconstruction Agent.
        """
        if not os.path.exists(pdf_path):
            return {"status": "error", "error": f"Archivo no encontrado: {pdf_path}"}
        if not pdf_path.lower().endswith('.pdf'):
            return {"status": "error", "error": "El archivo no es un PDF"}

        # 🆕 Si el usuario pidió Smart Convert (reconstrucción lógica)
        if use_smart_reconstruct:
            return self._pdf_to_word_smart_reconstruct(pdf_path, job_id)

        # Flujo normal: Word COM -> pdf2docx
        if platform.system() == "Windows":
            try:
                return self._pdf_to_word_com(pdf_path, job_id)
            except Exception as e:
                logger.warning(f"Conversión con MS Word falló ({e}), usando fallback...")

        return self._pdf_to_word_fallback(pdf_path, job_id)

    def _pdf_to_word_smart_reconstruct(self, pdf_path: str, job_id: str) -> Dict[str, Any]:
        """ Conversión usando el Agente de Reconstrucción de Diseño (Ideal para CVs)."""
        from services.layout_reconstruction_service import LayoutReconstructionService

        original_name = os.path.basename(pdf_path)
        clean_name = self._sanitize_filename(original_name)
        base_name = os.path.splitext(clean_name)[0]
        output_filename = f"{job_id}_{base_name}_RECONSTRUIDO.docx"
        output_path = os.path.join(self.output_dir, output_filename)

        logger.info(f"🧠 Usando Layout Reconstruction para: {os.path.basename(pdf_path)}")
        reconstructor = LayoutReconstructionService()
        result = reconstructor.reconstruct_pdf_to_word(pdf_path, output_path)

        if result.get('status') == 'success':
            result['filename'] = output_filename
            result['file_size'] = os.path.getsize(output_path)
            result['conversion_type'] = 'pdf_to_word_smart'

        return result

    def _pdf_to_word_com(self, pdf_path: str, job_id: str) -> Dict[str, Any]:
        """Conversión usando Microsoft Word COM."""
        import win32com.client
        import pythoncom

        word = None
        temp_pdf_path = None

        try:
            logger.info(f"🔄 Convirtiendo con MS Word COM: {os.path.basename(pdf_path)}")

            temp_pdf_path = self._create_temp_copy(pdf_path)
            pythoncom.CoInitialize()

            word = win32com.client.Dispatch("Word.Application")
            word.Visible = True
            word.DisplayAlerts = 1
            word.Activate()

            abs_pdf_path = os.path.abspath(temp_pdf_path)
            doc = word.Documents.Open(abs_pdf_path)
            time.sleep(3)

            original_name = os.path.basename(pdf_path)
            clean_name = self._sanitize_filename(original_name)
            base_name = os.path.splitext(clean_name)[0]
            output_filename = f"{job_id}_{base_name}.docx"
            output_path = os.path.join(self.output_dir, output_filename)
            abs_output_path = os.path.abspath(output_path)

            doc.SaveAs2(abs_output_path, FileFormat=12)
            doc.Close(False)
            word.Visible = False
            word.Quit()
            word = None

            if not os.path.exists(output_path):
                return {"status": "error", "error": "Word no generó el archivo"}

            return {
                "status": "success",
                "output_path": output_path,
                "filename": output_filename,
                "file_size": os.path.getsize(output_path),
                "conversion_type": "pdf_to_word",
                "engine": "microsoft_word_com"
            }

        except Exception as e:
            logger.error(f"Error en Word COM: {e}")
            raise Exception(f"Error: {str(e)}")
        finally:
            if word is not None:
                try:
                    word.Quit()
                except:
                    pass
            self._cleanup_temp(temp_pdf_path)
            try:
                pythoncom.CoUninitialize()
            except:
                pass

    def _pdf_to_word_fallback(self, pdf_path: str, job_id: str) -> Dict[str, Any]:
        """Fallback usando pdf2docx."""
        try:
            from pdf2docx import Converter
            original_name = os.path.basename(pdf_path)
            clean_name = self._sanitize_filename(original_name)
            base_name = os.path.splitext(clean_name)[0]
            output_filename = f"{job_id}_{base_name}.docx"
            output_path = os.path.join(self.output_dir, output_filename)

            cv = Converter(pdf_path)
            cv.convert(output_path)
            cv.close()

            if not os.path.exists(output_path):
                return {"status": "error", "error": "pdf2docx no generó el archivo"}

            return {
                "status": "success",
                "output_path": output_path,
                "filename": output_filename,
                "file_size": os.path.getsize(output_path),
                "conversion_type": "pdf_to_word",
                "engine": "pdf2docx"
            }
        except Exception as e:
            return {"status": "error", "error": f"Error en fallback: {str(e)}"}

    # ============================================================
    # WORD → PDF
    # ============================================================

    def word_to_pdf(self, docx_path: str, job_id: str) -> Dict[str, Any]:
        """Convierte Word a PDF."""
        if not os.path.exists(docx_path):
            return {"status": "error", "error": f"Archivo no encontrado: {docx_path}"}
        if not docx_path.lower().endswith('.docx'):
            return {"status": "error", "error": "El archivo no es un DOCX"}

        try:
            original_name = os.path.basename(docx_path)
            clean_name = self._sanitize_filename(original_name)
            base_name = os.path.splitext(clean_name)[0]
            output_filename = f"{job_id}_{base_name}.pdf"
            output_path = os.path.join(self.output_dir, output_filename)

            if platform.system() == "Windows":
                temp_docx_path = self._create_temp_copy(docx_path)
                try:
                    from docx2pdf import convert
                    convert(temp_docx_path, output_path)
                except ImportError:
                    return self._word_to_pdf_libreoffice(docx_path, output_path)
                finally:
                    self._cleanup_temp(temp_docx_path)
            else:
                return self._word_to_pdf_libreoffice(docx_path, output_path)

            if not os.path.exists(output_path):
                return {"status": "error", "error": "La conversión no generó archivo"}

            return {
                "status": "success",
                "output_path": output_path,
                "filename": output_filename,
                "file_size": os.path.getsize(output_path),
                "conversion_type": "word_to_pdf",
                "engine": "docx2pdf"
            }
        except Exception as e:
            return {"status": "error", "error": f"Error en conversión: {str(e)}"}

    def _word_to_pdf_libreoffice(self, docx_path: str, output_path: str) -> Dict[str, Any]:
        """Fallback usando LibreOffice."""
        lo_cmd = None
        for cmd in ['libreoffice', 'soffice']:
            if shutil.which(cmd):
                lo_cmd = cmd
                break

        if not lo_cmd:
            return {"status": "error", "error": "LibreOffice no está instalado."}

        output_dir = os.path.dirname(output_path)
        cmd = [lo_cmd, '--headless', '--convert-to', 'pdf', '--outdir', output_dir, docx_path]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                return {"status": "error", "error": f"Error LibreOffice: {result.stderr}"}

            expected_pdf = os.path.join(output_dir, os.path.splitext(os.path.basename(docx_path))[0] + '.pdf')
            if os.path.exists(expected_pdf) and expected_pdf != output_path:
                os.rename(expected_pdf, output_path)

            if not os.path.exists(output_path):
                return {"status": "error", "error": "LibreOffice no generó el PDF"}

            return {
                "status": "success",
                "output_path": output_path,
                "filename": os.path.basename(output_path),
                "file_size": os.path.getsize(output_path),
                "conversion_type": "word_to_pdf",
                "engine": "libreoffice"
            }
        except Exception as e:
            return {"status": "error", "error": f"Error ejecutando LibreOffice: {str(e)}"}