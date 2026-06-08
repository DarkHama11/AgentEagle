import os
import logging
import subprocess
import platform
import shutil
import uuid
import time
import glob
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger("AgentEagle.WindowsPrintService")


class WindowsPrintService:
    """Servicio de impresión robusto para Windows con soporte para impresión silenciosa."""

    def __init__(self, default_printer: Optional[str] = None):
        self.default_printer = default_printer
        if platform.system() != "Windows":
            raise RuntimeError("WindowsPrintService solo funciona en Windows")
        logger.info(f"WindowsPrintService inicializado. Impresora: {default_printer or 'predeterminada'}")

    def print_file(self, file_path: str, job_id: str, printer: Optional[str] = None,
                   copies: int = 1, options: Optional[Dict] = None) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            return {"status": "error", "error": f"Archivo no encontrado: {file_path}"}

        abs_file_path = os.path.abspath(file_path)
        extension = os.path.splitext(abs_file_path)[1].lower()
        target_printer = printer or self.default_printer

        try:
            if extension == '.pdf':
                result = self._print_pdf(abs_file_path, target_printer, copies)
            elif extension in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']:
                result = self._print_image(abs_file_path, target_printer, copies)
            elif extension == '.docx':
                result = self._print_docx_with_word(abs_file_path, target_printer)
            else:
                return {"status": "error", "error": f"Formato no soportado: {extension}"}

            if result['status'] == 'success':
                windows_job_id = f"WIN-{uuid.uuid4().hex[:8].upper()}"
                logger.info(f"✅ Archivo enviado a impresora: {abs_file_path}")
                return {
                    "status": "success",
                    "cups_job_id": windows_job_id,
                    "simulated": False,
                    "file_path": abs_file_path,
                    "printer": target_printer or "Predeterminada",
                    "copies": copies
                }
            return result
        except Exception as e:
            logger.error(f"Error inesperado imprimiendo: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def _print_pdf(self, file_path: str, printer: Optional[str], copies: int) -> Dict[str, Any]:
        """Imprime PDF usando métodos de impresión silenciosa."""

        # Buscar SumatraPDF en múltiples ubicaciones
        sumatra_paths = self._find_sumatrapdf()

        for sumatra_path in sumatra_paths:
            logger.info(f"🔍 SumatraPDF encontrado: {sumatra_path}")
            printer_name = printer or self.get_default_printer()

            # Construir comando base de SumatraPDF
            cmd = [sumatra_path, "-print-to", printer_name]

            # 🆕 CORRECCIÓN: Agregar configuraciones de impresión (número de copias)
            # Formato de SumatraPDF para copias: "Nx" (ej: "2x" para 2 copias, "5x" para 5)
            if copies and copies > 1:
                cmd.extend(["-print-settings", f"{copies}x"])
                logger.info(f"📋 Configuración de copias añadida: {copies}x")

            cmd.extend(["-silent", file_path])

            logger.info(f"🖨️ Ejecutando: {' '.join(cmd)}")

            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )

                # Aumentar timeout dinámicamente según el número de copias
                timeout = 10 + (copies * 3)
                stdout, stderr = process.communicate(timeout=timeout)

                if process.returncode == 0:
                    logger.info(f"✅ SumatraPDF envió trabajo a impresora: {printer_name} ({copies} copias)")
                    time.sleep(2)  # Dar tiempo al spooler
                    return {"status": "success", "method": "SumatraPDF"}
                else:
                    logger.warning(f"⚠️ SumatraPDF retornó código {process.returncode}")
                    if stderr:
                        logger.warning(f"stderr: {stderr.decode('utf-8', errors='ignore')}")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Timeout esperando SumatraPDF")
                process.kill()
            except Exception as e:
                logger.warning(f"⚠️ Error con SumatraPDF: {e}")

        # Buscar Adobe Reader (Fallback)
        adobe_paths = self._find_adobe_reader()

        for adobe_path in adobe_paths:
            logger.info(f"🔍 Adobe Reader encontrado: {adobe_path}")
            if copies > 1:
                logger.warning("⚠️ Adobe Reader no soporta múltiples copias en modo silencioso. Imprimiendo 1 copia.")

            cmd = [adobe_path, "/p", "/h", file_path]
            logger.info(f"🖨️ Ejecutando: {' '.join(cmd)}")

            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                time.sleep(5)
                process.terminate()
                logger.info(f"✅ Adobe Reader envió trabajo a impresora")
                return {"status": "success", "method": "Adobe Reader"}
            except Exception as e:
                logger.warning(f"⚠️ Error con Adobe Reader: {e}")

        # Último recurso: win32api
        logger.warning("⚠️ No se encontró SumatraPDF ni Adobe Reader")
        try:
            import win32api
            import win32print

            old_default = None
            if printer:
                old_default = win32print.GetDefaultPrinter()
                win32print.SetDefaultPrinter(printer)

            logger.info(f"Usando win32api.ShellExecute para: {file_path}")
            win32api.ShellExecute(0, "print", file_path, None, ".", 0)
            time.sleep(3)

            if old_default:
                win32print.SetDefaultPrinter(old_default)

            return {"status": "success", "method": "win32api"}
        except ImportError:
            logger.error("❌ pywin32 no está instalado")
            return {
                "status": "error",
                "error": "No se encontró SumatraPDF ni Adobe Reader. Instala uno de ellos o ejecuta: pip install pywin32"
            }
        except Exception as e:
            logger.error(f"❌ Error con win32api: {e}")
            return {"status": "error", "error": f"Error de impresión: {str(e)}"}

    def _find_sumatrapdf(self) -> List[str]:
        """Busca SumatraPDF en ubicaciones comunes."""
        search_paths = [
            r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
            r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",
            r"C:\Users\*\AppData\Local\SumatraPDF\SumatraPDF.exe",
            r"C:\Users\*\AppData\Roaming\SumatraPDF\SumatraPDF.exe",
        ]

        found = []
        for pattern in search_paths:
            matches = glob.glob(pattern)
            found.extend(matches)

        sumatra_in_path = shutil.which("SumatraPDF")
        if sumatra_in_path:
            found.append(sumatra_in_path)

        return list(set(found))

    def _find_adobe_reader(self) -> List[str]:
        """Busca Adobe Reader en ubicaciones comunes."""
        search_paths = [
            r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe",
            r"C:\Program Files (x86)\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
            r"C:\Program Files\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
            r"C:\Program Files (x86)\Adobe\Acrobat 20*\Reader\AcroRd32.exe",
            r"C:\Program Files\Adobe\Acrobat 20*\Reader\AcroRd32.exe",
        ]

        found = []
        for pattern in search_paths:
            matches = glob.glob(pattern)
            found.extend(matches)

        return list(set(found))

    def _print_image(self, file_path: str, printer: Optional[str], copies: int) -> Dict[str, Any]:
        """Imprime imágenes."""
        if copies > 1:
            logger.warning("⚠️ La impresión de imágenes con win32api no soporta múltiples copias fácilmente.")
        try:
            import win32api
            win32api.ShellExecute(0, "print", file_path, None, ".", 0)
            time.sleep(2)
            return {"status": "success"}
        except ImportError:
            return {"status": "error", "error": "pywin32 requerido para imprimir imágenes"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _print_docx_with_word(self, docx_path: str, printer: Optional[str]) -> Dict[str, Any]:
        """Imprime DOCX usando Word COM."""
        try:
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            try:
                doc = word.Documents.Open(docx_path)
                if printer:
                    word.ActivePrinter = printer
                doc.PrintOut()
                time.sleep(3)
                doc.Close(False)
                return {"status": "success"}
            finally:
                word.Quit()
        except ImportError:
            return {"status": "error", "error": "pywin32 requerido para DOCX"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def list_printers(self) -> List[str]:
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-Printer | Select-Object -ExpandProperty Name"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
        except Exception as e:
            logger.error(f"Error listando impresoras: {e}")
        return []

    def get_default_printer(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-WmiObject -Query 'SELECT * FROM Win32_Printer WHERE Default=True').Name"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception as e:
            logger.error(f"Error obteniendo impresora predeterminada: {e}")
        return None

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        return {"job_id": job_id, "status": "sent"}