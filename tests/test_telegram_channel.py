import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from approval_channels.telegram_channel import TelegramApprovalChannel
from approval.approval_manager import ApprovalManager
from approval.approval_request import ApprovalRequest


class TestTelegramApprovalChannel(unittest.TestCase):

    def setUp(self):
        self.mock_approval_manager = Mock(spec=ApprovalManager)
        self.bot_token = "test_token"
        self.chat_id = "1193717225"

        self.channel = TelegramApprovalChannel(
            approval_manager=self.mock_approval_manager,
            bot_token=self.bot_token,
            default_chat_id=self.chat_id
        )

    def test_send_approval_buttons(self):
        """Test: Envío de solicitud con botones inline."""
        with patch('approval_channels.telegram_channel.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "ok": True,
                "result": {"message_id": 123}
            }
            mock_post.return_value = mock_response

            result = self.channel.send_approval_request(
                approval_id="APR-TEST001",
                job_id="JOB-TEST",
                pipeline_name="invoice_payment",
                title="Aprobar pago",
                description="Verifica la factura",
                payload={"amount": 1000, "supplier": "Test"}
            )

            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['message_id'], 123)

            # Verificar que se envió con inline_keyboard
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            self.assertIn('reply_markup', payload)
            self.assertIn('inline_keyboard', payload['reply_markup'])

    def test_telegram_callback_approve(self):
        """Test: Callback de aprobación."""
        callback_query = {
            "id": "cb_123",
            "data": "approve:APR-TEST001",
            "from": {"id": 1193717225, "username": "testuser", "first_name": "Test"},
            "message": {"chat": {"id": 1193717225}, "message_id": 123}
        }

        with patch.object(self.channel, '_answer_callback') as mock_answer, \
                patch.object(self.channel, 'update_message_approved') as mock_update:
            self.channel._handle_callback_query(callback_query)

            # Verificar que se llamó a approval_manager.approve
            self.mock_approval_manager.approve.assert_called_once()
            call_args = self.mock_approval_manager.approve.call_args
            self.assertEqual(call_args[1]['approval_id'], 'APR-TEST001')
            self.assertIn('telegram:', call_args[1]['resolved_by'])

    def test_telegram_callback_reject(self):
        """Test: Callback de rechazo."""
        callback_query = {
            "id": "cb_456",
            "data": "reject:APR-TEST002",
            "from": {"id": 1193717225, "username": "testuser", "first_name": "Test"},
            "message": {"chat": {"id": 1193717225}, "message_id": 456}
        }

        with patch.object(self.channel, '_answer_callback'), \
                patch.object(self.channel, 'update_message_rejected'):
            self.channel._handle_callback_query(callback_query)

            self.mock_approval_manager.reject.assert_called_once()
            call_args = self.mock_approval_manager.reject.call_args
            self.assertEqual(call_args[1]['approval_id'], 'APR-TEST002')

    def test_unauthorized_user(self):
        """Test: Usuario no autorizado."""
        callback_query = {
            "id": "cb_789",
            "data": "approve:APR-TEST003",
            "from": {"id": 999999999, "username": "hacker", "first_name": "Hacker"},
            "message": {"chat": {"id": 999999999}, "message_id": 789}
        }

        with patch.object(self.channel, '_answer_callback') as mock_answer:
            self.channel._handle_callback_query(callback_query)

            # NO debe llamar a approve/reject
            self.mock_approval_manager.approve.assert_not_called()
            self.mock_approval_manager.reject.assert_not_called()

            # Debe responder con alerta de no autorizado
            mock_answer.assert_called()
            call_args = mock_answer.call_args
            self.assertIn("autorizado", call_args[0][1].lower())

    def test_pipeline_resume_after_approve(self):
        """Test: Pipeline se reanuda después de aprobar."""
        # Simular un callback de aprobación
        callback_query = {
            "id": "cb_resume",
            "data": "approve:APR-RESUME",
            "from": {"id": 1193717225, "username": "user", "first_name": "User"},
            "message": {"chat": {"id": 1193717225}, "message_id": 100}
        }

        with patch.object(self.channel, '_answer_callback'), \
                patch.object(self.channel, 'update_message_approved'):
            self.channel._handle_callback_query(callback_query)

            # Verificar que approval_manager.approve fue llamado
            # Esto disparará el callback registrado que reanuda el pipeline
            self.mock_approval_manager.approve.assert_called_once()

    def test_pipeline_stop_after_reject(self):
        """Test: Pipeline se detiene después de rechazar."""
        callback_query = {
            "id": "cb_stop",
            "data": "reject:APR-STOP",
            "from": {"id": 1193717225, "username": "user", "first_name": "User"},
            "message": {"chat": {"id": 1193717225}, "message_id": 200}
        }

        with patch.object(self.channel, '_answer_callback'), \
                patch.object(self.channel, 'update_message_rejected'):
            self.channel._handle_callback_query(callback_query)

            self.mock_approval_manager.reject.assert_called_once()

    def test_audit_log(self):
        """Test: Registro de auditoría."""
        callback_query = {
            "id": "cb_audit",
            "data": "approve:APR-AUDIT",
            "from": {"id": 1193717225, "username": "auditor", "first_name": "Auditor"},
            "message": {"chat": {"id": 1193717225}, "message_id": 300}
        }

        with patch.object(self.channel, '_answer_callback'), \
                patch.object(self.channel, 'update_message_approved'), \
                patch.object(self.channel.audit_logger, 'info') as mock_log:
            self.channel._handle_callback_query(callback_query)

            # Verificar que se registró en auditoría
            mock_log.assert_called()
            log_entry = json.loads(mock_log.call_args[0][0])
            self.assertEqual(log_entry['approval_id'], 'APR-AUDIT')
            self.assertEqual(log_entry['action'], 'approved')
            self.assertEqual(log_entry['telegram_user'], '@auditor')

    def test_message_update_after_approval(self):
        """Test: Mensaje se actualiza después de aprobar."""
        with patch('approval_channels.telegram_channel.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True}
            mock_post.return_value = mock_response

            result = self.channel.update_message_approved(
                chat_id=1193717225,
                message_id=123,
                approval_id="APR-UPDATE",
                resolved_by="@testuser"
            )

            self.assertTrue(result)

            # Verificar que se llamó a editMessageText
            call_args = mock_post.call_args
            self.assertIn("editMessageText", call_args[0][0])
            payload = call_args[1]['json']
            self.assertIn("APROBADO", payload['text'])


if __name__ == '__main__':
    unittest.main()