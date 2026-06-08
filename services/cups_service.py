import os
import uuid
import logging
import subprocess
import platform
import shutil
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger("AgentEagle.CupsService")


class BasePrintService(ABC):
    """Interfaz abstracta para servicios de impresión."""

    @abstractmethod
    def print_file(self, file_path: str, job_id: str, printer: Optional[str] = None,
                   copies: int = 1, options: Optional[Dict] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def list_printers(self) -> List[str]:
        pass

    @abstractmethod
    def get_job_status(self, cups_job_id: str) -> Dict[str, Any]:
        pass


class SimulationPrintService(BasePrintService):
    """
    Servicio de impresión simulado para pruebas sin impresora real.
    Crea un archivo de log en lugar de imprimir.
    """

    def __init__(self, simulation_dir: str = "data/simulation_prints"):
        self.simulation_dir = simulation_dir
        os.makedirs(simulation_dir, exist_ok=True)
        logger.info(f"SimulationPrintService inicializado en: {simulation_dir}")

    def print_file(self, file_path: str, job_id: str, printer: Optional[str] = None,
                   copies: int = 1, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Simula la impresión creando un log detallado."""
        if not os.path.exists(file_path):
            return {"status": "error", "error": f"Archivo no encontrado: {file_path}"}

        # Crear archivo de "impresión simulada"
        sim_filename = f"{job_id}_{os.path.basename(file_path)}.simulated"
        sim_path = os.path.join(self.simulation_dir, sim_filename)

        file_size = os.path.getsize(file_path)

        # Copiar el archivo como "prueba de impresión"
        try:
            shutil.copy2(file_path, sim_path)
        except Exception as e:
            logger.error(f"Error copiando archivo para simulación: {e}")

        # Crear log de la "impresión"
        log_content = f"""
============================================================
🖨️  IMPRESIÓN SIMULADA - AgentEagle 2.0
============================================================
Job ID        : {job_id}
Archivo       : {os.path.basename(file_path)}
Tamaño        : {file_size} bytes
Impresora     : {printer or 'SIMULATED_PRINTER'}
Copias        : {copies}
Opciones      : {options or {} }
Fecha         : {datetime.now(timezone.utc).isoformat()}
Plataforma    : {platform.system()} {platform.release()}
============================================================
ESTADO: ✅ IMPRESIÓN SIMULADA EXITOSA
============================================================
"""

        log_path = os.path.join(self.simulation_dir, f"{job_id}.log")
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(log_content)

        simulated_cups_id = f"SIM-{uuid.uuid4().hex[:8].upper()}"

        logger.info(f"🖨️  [SIMULACIÓN] Impresión completada: {job_id} → {sim_path}")

        return {
            "status": "success",
            "cups_job_id": simulated_cups_id,
            "simulated": True,
            "file_path": sim_path,
            "log_path": log_path,
            "printer": printer or "SIMULATED_PRINTER",
            "copies": copies
        }

    def list_printers(self) -> List[str]:
        return ["SIMULATED_PRINTER", "SIMULATED_PRINTER_COLOR", "SIMULATED_PRINTER_DUPLEX"]

    def get_job_status(self, cups_job_id: str) -> Dict[str, Any]:
        return {
            "job_id": cups_job_id,
            "status": "completed",
            "simulated": True
        }


class CupsPrintService(BasePrintService):
    """
    Servicio de impresión real usando CUPS (Common UNIX Printing System).
    Solo funciona en Linux/macOS con CUPS instalado.
    """

    def __init__(self, default_printer: Optional[str] = None):
        self.default_printer = default_printer
        self._check_cups_available()
        logger.info(f"CupsPrintService inicializado. Impresora por defecto: {default_printer or 'sistema'}")

    def _check_cups_available(self) -> None:
        """Verifica que CUPS esté disponible en el sistema."""
        if platform.system() == "Windows":
            logger.warning("⚠️ CUPS no está disponible en Windows. Usa WindowsPrintService.")
            return

        # Verificar que el comando 'lp' esté disponible
        if not shutil.which('lp'):
            logger.warning("⚠️ Comando 'lp' no encontrado. Instala CUPS: sudo apt install cups")

    def print_file(self, file_path: str, job_id: str, printer: Optional[str] = None,
                   copies: int = 1, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Envía un archivo a la impresora usando CUPS (comando lp)."""
        if not os.path.exists(file_path):
            return {"status": "error", "error": f"Archivo no encontrado: {file_path}"}

        # Convertir DOCX a PDF si es necesario
        actual_file = self._prepare_file(file_path, job_id)
        if actual_file['status'] != 'success':
            return actual_file

        file_to_print = actual_file.get('prepared_path', file_path)

        # Construir comando lp
        target_printer = printer or self.default_printer
        cmd = ['lp']

        if target_printer:
            cmd.extend(['-d', target_printer])

        cmd.extend(['-n', str(copies)])
        cmd.extend(['-t', f'AgentEagle-{job_id}'])  # Título del job

        # Agregar opciones adicionales
        if options:
            for key, value in options.items():
                cmd.extend(['-o', f'{key}={value}'])

        cmd.append(file_to_print)

        try:
            logger.info(f"🖨️  Ejecutando comando: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Extraer el ID del job de CUPS de la salida
                # Formato típico: "request id is PRINTER-123 (1 file(s))"
                cups_job_id = self._extract_cups_job_id(result.stdout)

                logger.info(f"✅ Archivo enviado a CUPS. Job ID: {cups_job_id}")

                return {
                    "status": "success",
                    "cups_job_id": cups_job_id,
                    "simulated": False,
                    "file_path": file_to_print,
                    "printer": target_printer or "default",
                    "copies": copies,
                    "stdout": result.stdout.strip()
                }
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error(f"Error en CUPS: {error_msg}")
                return {"status": "error", "error": error_msg}

        except subprocess.TimeoutExpired:
            logger.error("Timeout enviando archivo a CUPS")
            return {"status": "error", "error": "Timeout en CUPS"}
        except Exception as e:
            logger.error(f"Error inesperado en CUPS: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def _prepare_file(self, file_path: str, job_id: str) -> Dict[str, Any]:
        """
        Prepara el archivo para impresión.
        Convierte DOCX a PDF si es necesario.
        """
        extension = os.path.splitext(file_path)[1].lower()

        # PDF, PNG, JPG: no requieren conversión
        if extension in ['.pdf', '.png', '.jpg', '.jpeg']:
            return {"status": "success", "prepared_path": file_path}

        # DOCX: convertir a PDF usando LibreOffice
        if extension == '.docx':
            return self._convert_docx_to_pdf(file_path, job_id)

        return {"status": "error", "error": f"Formato no soportado: {extension}"}

    def _convert_docx_to_pdf(self, docx_path: str, job_id: str) -> Dict[str, Any]:
        """Convierte DOCX a PDF usando LibreOffice headless."""
        if not shutil.which('libreoffice') and not shutil.which('soffice'):
            return {
                "status": "error",
                "error": "LibreOffice no está instalado. Instálalo con: sudo apt install libreoffice"
            }

        output_dir = os.path.dirname(docx_path)
        lo_cmd = 'libreoffice' if shutil.which('libreoffice') else 'soffice'

        cmd = [
            lo_cmd,
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', output_dir,
            docx_path
        ]

        try:
            logger.info(f"Convirtiendo DOCX a PDF: {docx_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                pdf_path = os.path.splitext(docx_path)[0] + '.pdf'
                if os.path.exists(pdf_path):
                    logger.info(f"✅ DOCX convertido a PDF: {pdf_path}")
                    return {"status": "success", "prepared_path": pdf_path}

            logger.error(f"Error convirtiendo DOCX: {result.stderr}")
            return {"status": "error", "error": f"Error en conversión: {result.stderr}"}

        except Exception as e:
            logger.error(f"Error en conversión DOCX: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def _extract_cups_job_id(self, output: str) -> str:
        """Extrae el ID del job de CUPS de la salida del comando lp."""
        import re
        match = re.search(r'request id is (\S+)', output)
        if match:
            return match.group(1)
        return f"CUPS-{uuid.uuid4().hex[:8].upper()}"

    def list_printers(self) -> List[str]:
        """Lista las impresoras disponibles en CUPS."""
        try:
            result = subprocess.run(['lpstat', '-p'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                printers = []
                for line in result.stdout.split('\n'):
                    if line.startswith('printer'):
                        parts = line.split()
                        if len(parts) >= 2:
                            printers.append(parts[1])
                return printers
        except Exception as e:
            logger.error(f"Error listando impresoras: {e}")
        return []

    def get_job_status(self, cups_job_id: str) -> Dict[str, Any]:
        """Consulta el estado de un job en CUPS."""
        try:
            result = subprocess.run(
                ['lpstat', '-l', '-o', cups_job_id],
                capture_output=True, text=True, timeout=10
            )
            return {
                "job_id": cups_job_id,
                "status": "completed" if result.returncode != 0 else "processing",
                "output": result.stdout
            }
        except Exception as e:
            return {"job_id": cups_job_id, "status": "unknown", "error": str(e)}


class CupsService:
    """
    Factory que crea el servicio de impresión apropiado según el sistema operativo.
    """

    @staticmethod
    def create(mode: str = "simulation", default_printer: Optional[str] = None,
               simulation_dir: str = "data/simulation_prints"):
        """
        Crea el servicio de impresión según el modo y sistema operativo.

        :param mode: "simulation", "cups" (Linux) o "windows" (Windows)
        :param default_printer: Impresora por defecto
        :param simulation_dir: Directorio para archivos simulados
        """
        # Si es modo simulación, usar SimulationPrintService
        if mode.lower() == "simulation":
            return SimulationPrintService(simulation_dir=simulation_dir)

        # Detectar sistema operativo
        system = platform.system()

        if system == "Windows":
            # En Windows, usar WindowsPrintService
            if mode.lower() in ["windows", "cups", "real"]:
                try:
                    from services.windows_print_service import WindowsPrintService
                    return WindowsPrintService(default_printer=default_printer)
                except Exception as e:
                    logger.error(f"Error creando WindowsPrintService: {e}")
                    logger.warning("Cayendo a modo simulación")
                    return SimulationPrintService(simulation_dir=simulation_dir)
            else:
                logger.warning(f"Modo '{mode}' no reconocido en Windows. Usando simulación.")
                return SimulationPrintService(simulation_dir=simulation_dir)

        elif system in ["Linux", "Darwin"]:  # Linux o macOS
            if mode.lower() in ["cups", "real"]:
                return CupsPrintService(default_printer=default_printer)
            else:
                logger.warning(f"Modo '{mode}' no reconocido. Usando simulación.")
                return SimulationPrintService(simulation_dir=simulation_dir)

        else:
            logger.warning(f"Sistema operativo no soportado: {system}. Usando simulación.")
            return SimulationPrintService(simulation_dir=simulation_dir)