import unittest
from unittest.mock import Mock, patch, MagicMock
from agents.functional.notification_agent import NotificationAgent
from services.telegram_service import TelegramService
from services.message_template_service import MessageTemplateService
from event_bus.event import Event
from event_bus.in_memory_event_bus import InMemoryEventBus


class TestNotificationAgent(unittest.TestCase):

    def setUp(self):
        """Configuración inicial para cada test."""
        self.event_bus = InMemoryEventBus()
        self.event_bus.start()

        # Mock de configuración
        self.mock_config = {
            'telegram': {
                'enabled': True,
                'bot_token': 'test_token',
                'chat_id': '123456',
                'parse_mode': 'HTML'
            }
        }

    def tearDown(self):
        """Limpieza después de cada test."""
        self.event_bus.stop()

    @patch('agents.functional.notification_agent.NotificationAgent._load_config')
    def test_telegram_send(self, mock_load_config):
        """Test: Envío de mensaje por Telegram."""
        mock_load_config.return_value = self.mock_config

        agent = NotificationAgent(event_bus=None)

        # Mock del servicio Telegram
        with patch.object(agent.notification_services[0], 'send') as mock_send:
            mock_send.return_value = {
                "status": "success",
                "message_id": 123,
                "channel": "telegram"
            }

            result = agent.send_telegram("Mensaje de prueba")

            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['message_id'], 123)
            mock_send.assert_called_once()

    @patch('agents.functional.notification_agent.NotificationAgent._load_config')
    def test_event_subscription(self, mock_load_config):
        """Test: Suscripción automática a eventos."""
        mock_load_config.return_value = self.mock_config

        agent = NotificationAgent(event_bus=self.event_bus)

        # Verificar que se suscribió a los eventos correctos
        for event_type in NotificationAgent.SUBSCRIBED_EVENTS:
            self.assertIn(event_type, self.event_bus._subscribers)

    @patch('agents.functional.notification_agent.NotificationAgent._load_config')
    def test_document_processed_notification(self, mock_load_config):
        """Test: Notificación de documento procesado."""
        mock_load_config.return_value = self.mock_config

        agent = NotificationAgent(event_bus=self.event_bus)

        # Crear evento de documento procesado
        event = Event(
            event_type="document.processed",
            source="document_agent",
            payload={
                "job_id": "JOB-TEST123",
                "document_type": "invoice",
                "confidence": 0.95,
                "fields": {
                    "invoice_number": "INV-001",
                    "supplier": "Empresa XYZ",
                    "amount": "$1,000"
                },
                "processing_time": 12.5
            }
        )

        # Mock del envío
        with patch.object(agent, 'send_notification') as mock_send:
            mock_send.return_value = {"telegram": {"status": "success"}}

            agent.handle_event(event)

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            message = call_args[0][0]

            # Verificar que el mensaje contiene información clave
            self.assertIn("invoice", message.lower())
            self.assertIn("JOB-TEST123", message)

    @patch('agents.functional.notification_agent.NotificationAgent._load_config')
    def test_pipeline_failed_notification(self, mock_load_config):
        """Test: Notificación de pipeline fallido."""
        mock_load_config.return_value = self.mock_config

        agent = NotificationAgent(event_bus=self.event_bus)

        # Crear evento de pipeline fallido
        event = Event(
            event_type="pipeline.failed",
            source="orchestrator",
            payload={
                "job_id": "JOB-FAIL456",
                "pipeline": "document_processing",
                "error": "Error de conexión con Ollama"
            }
        )

        # Mock del envío
        with patch.object(agent, 'send_notification') as mock_send:
            mock_send.return_value = {"telegram": {"status": "success"}}

            agent.handle_event(event)

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            message = call_args[0][0]

            # Verificar que el mensaje contiene información de error
            self.assertIn("fallido", message.lower())
            self.assertIn("JOB-FAIL456", message)
            self.assertIn("Ollama", message)

    def test_message_templates(self):
        """Test: Plantillas de mensajes."""
        template_service = MessageTemplateService()

        # Test template document.processed
        payload = {
            "document_type": "invoice",
            "confidence": 0.95,
            "job_id": "JOB-123",
            "fields": {"amount": "$100"},
            "processing_time": 10.5
        }
        message = template_service.format_document_processed(payload)
        self.assertIn("Documento Procesado", message)
        self.assertIn("invoice", message)
        self.assertIn("JOB-123", message)

        # Test template pipeline.failed
        payload = {
            "pipeline": "test_pipeline",
            "job_id": "JOB-456",
            "error": "Test error"
        }
        message = template_service.format_pipeline_failed(payload)
        self.assertIn("Pipeline Fallido", message)
        self.assertIn("test_pipeline", message)
        self.assertIn("Test error", message)


if __name__ == '__main__':
    unittest.main()