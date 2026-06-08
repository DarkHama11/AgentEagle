import unittest
import os
import tempfile
from unittest.mock import Mock, patch
from agents.functional.document_agent import DocumentAgent
from services.llm_service import LLMService
from services.model_manager import ModelManager
from event_bus.in_memory_event_bus import InMemoryEventBus


class TestDocumentAgent(unittest.TestCase):
    def setUp(self):
        self.event_bus = InMemoryEventBus()
        self.event_bus.start()
        self.agent = DocumentAgent(event_bus=self.event_bus)
        self.received_events = []

        def callback(event):
            self.received_events.append(event)

        self.event_bus.subscribe("document.processed", callback)
        self.event_bus.subscribe("document.ocr_completed", callback)
        self.event_bus.subscribe("document.classified", callback)

    def tearDown(self):
        self.event_bus.stop()
        self.received_events.clear()

    def test_ocr_action(self):
        """Test de acción OCR"""
        # Crear archivo de prueba
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Este es un documento de prueba con texto de ejemplo.")
            temp_file = f.name

        try:
            result = self.agent.execute("ocr", {"file_path": temp_file, "job_id": "TEST001"})
            self.assertEqual(result["status"], "success")
            self.assertIn("text", result)
            self.assertGreater(len(result["text"]), 0)
        finally:
            os.unlink(temp_file)

    def test_classification_action(self):
        """Test de acción de clasificación"""
        text = """
        FACTURA COMERCIAL
        Número: INV-2024-001
        Proveedor: Empresa XYZ S.A.
        Fecha: 2024-01-15
        Total: $1,250.00
        """

        result = self.agent.execute("classify", {"text": text, "job_id": "TEST002"})
        self.assertEqual(result["status"], "success")
        self.assertIn("document_type", result)
        self.assertIn("confidence", result)

    def test_extraction_action(self):
        """Test de acción de extracción"""
        text = """
        FACTURA
        Número: INV-001
        Proveedor: Empresa ABC
        Fecha: 2024-01-15
        Monto: 1500
        """

        result = self.agent.execute("extract", {
            "document_type": "invoice",
            "text": text,
            "job_id": "TEST003"
        })

        self.assertEqual(result["status"], "success")
        self.assertIn("fields", result)

    def test_full_process_pipeline(self):
        """Test del pipeline completo de procesamiento"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("""
            FACTURA COMERCIAL
            Número de Factura: INV-2024-001
            Proveedor: Empresa XYZ S.A.
            Cliente: Empresa ABC Ltda.
            Fecha: 2024-01-15
            Fecha de Vencimiento: 2024-02-15
            Total: $125,000
            Referencia: Proyecto Alpha
            """)
            temp_file = f.name

        try:
            result = self.agent.execute("process", {
                "file_path": temp_file,
                "job_id": "TEST004"
            })

            self.assertEqual(result["status"], "success")
            self.assertIn("document_type", result)
            self.assertIn("confidence", result)
            self.assertIn("fields", result)
            self.assertIn("processing_time", result)

            # Verificar que se publicaron eventos
            self.assertGreater(len(self.received_events), 0)

        finally:
            os.unlink(temp_file)

    def test_event_publication(self):
        """Test de publicación de eventos"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Documento de prueba para verificar eventos")
            temp_file = f.name

        try:
            self.agent.execute("process", {
                "file_path": temp_file,
                "job_id": "TEST005"
            })

            # Verificar que se publicaron eventos
            event_types = [e.event_type for e in self.received_events]
            self.assertIn("document.processed", event_types)

        finally:
            os.unlink(temp_file)


if __name__ == '__main__':
    unittest.main()