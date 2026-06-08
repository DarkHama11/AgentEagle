import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.cups_service import CupsService, SimulationPrintService
from services.telegram_file_service import TelegramFileService


class TestCupsService(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_simulation_mode_creation(self):
        """Test: Creación en modo simulación."""
        service = CupsService.create(mode="simulation", simulation_dir=self.temp_dir)
        self.assertIsInstance(service, SimulationPrintService)

    def test_simulation_print(self):
        """Test: Impresión simulada."""
        service = CupsService.create(mode="simulation", simulation_dir=self.temp_dir)

        # Crear archivo de prueba
        test_file = os.path.join(self.temp_dir, "test.pdf")
        with open(test_file, 'w') as f:
            f.write("Test content")

        result = service.print_file(test_file, job_id="PRT-TEST001")

        self.assertEqual(result['status'], 'success')
        self.assertTrue(result['simulated'])
        self.assertIn('cups_job_id', result)

    def test_list_printers_simulation(self):
        """Test: Listar impresoras en simulación."""
        service = CupsService.create(mode="simulation")
        printers = service.list_printers()

        self.assertIsInstance(printers, list)
        self.assertGreater(len(printers), 0)
        self.assertIn("SIMULATED_PRINTER", printers)

    def test_print_nonexistent_file(self):
        """Test: Intentar imprimir archivo inexistente."""
        service = CupsService.create(mode="simulation", simulation_dir=self.temp_dir)
        result = service.print_file("/no/existe.pdf", job_id="PRT-TEST002")

        self.assertEqual(result['status'], 'error')
        self.assertIn("no encontrado", result['error'])


class TestTelegramFileService(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.service = TelegramFileService(bot_token="test_token", uploads_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sanitize_filename(self):
        """Test: Limpieza de nombres de archivo."""
        self.assertEqual(
            self.service._sanitize_filename("file/name:test.pdf"),
            "file_name_test.pdf"
        )
        self.assertEqual(
            self.service._sanitize_filename("normal.pdf"),
            "normal.pdf"
        )

    @patch('services.telegram_file_service.requests.post')
    def test_get_file_info_error(self, mock_post):
        """Test: Error al obtener info del archivo."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"ok": False, "description": "File not found"}

        result = self.service._get_file_info("invalid_file_id")
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()