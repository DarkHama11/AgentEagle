import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.print_rules_service import PrintRulesService
from services.printer_manager import PrinterManager
from services.print_decision_service import PrintDecisionService


class TestPrintRulesService(unittest.TestCase):
    def setUp(self):
        PrintRulesService.reset_instance()

    def tearDown(self):
        PrintRulesService.reset_instance()

    def test_load_rules(self):
        service = PrintRulesService()
        self.assertIsNotNone(service.rules)
        self.assertIn('invoice', service.rules)
        self.assertIn('contract', service.rules)

    def test_get_rule(self):
        service = PrintRulesService()
        rule = service.get_rule('invoice')
        self.assertTrue(rule['should_print'])
        self.assertEqual(rule['copies'], 1)
        self.assertEqual(rule['printer_group'], 'finance')

    def test_get_rule_unknown(self):
        service = PrintRulesService()
        rule = service.get_rule('unknown_type')
        # Debe retornar regla 'other'
        self.assertIn('should_print', rule)


class TestPrinterManager(unittest.TestCase):
    def setUp(self):
        PrinterManager.reset_instance()

    def tearDown(self):
        PrinterManager.reset_instance()

    def test_get_printer_for_group(self):
        manager = PrinterManager()
        printer = manager.get_printer_for_group('finance')
        self.assertIsNotNone(printer)

    def test_get_all_groups(self):
        manager = PrinterManager()
        groups = manager.get_all_groups()
        self.assertIsInstance(groups, list)
        self.assertGreater(len(groups), 0)


class TestPrintDecisionService(unittest.TestCase):
    def setUp(self):
        PrintRulesService.reset_instance()
        self.mock_llm = Mock()
        self.mock_model_manager = Mock()
        self.mock_model_manager.get_model.return_value = "llama3.2:3b"

        self.service = PrintDecisionService(self.mock_llm, self.mock_model_manager)

    def tearDown(self):
        PrintRulesService.reset_instance()

    def test_decision_for_invoice(self):
        """Test: Decisión para factura."""
        # Mock respuesta del LLM
        self.mock_llm.generate.return_value = '''
        {
            "should_print": true,
            "copies": 1,
            "requires_approval": false,
            "printer_group": "finance",
            "priority": "normal",
            "reason": "Factura estándar"
        }
        '''

        decision = self.service.decide(
            document_type="invoice",
            confidence=0.95,
            fields={"supplier": "Test", "amount": "$100"},
            raw_text="Factura de prueba",
            file_name="test.pdf"
        )

        self.assertTrue(decision['should_print'])
        self.assertEqual(decision['copies'], 1)
        self.assertFalse(decision['requires_approval'])

    def test_decision_for_contract_requires_approval(self):
        """Test: Contrato requiere aprobación."""
        self.mock_llm.generate.return_value = '''
        {
            "should_print": true,
            "copies": 2,
            "requires_approval": true,
            "printer_group": "legal",
            "priority": "high",
            "reason": "Contrato legal"
        }
        '''

        decision = self.service.decide(
            document_type="contract",
            confidence=0.90,
            fields={"parties": "A y B"},
            raw_text="Contrato de prueba",
            file_name="contract.pdf"
        )

        self.assertTrue(decision['requires_approval'])
        self.assertEqual(decision['printer_group'], 'legal')

    def test_decision_for_manual_no_print(self):
        """Test: Manual no debe imprimirse."""
        self.mock_llm.generate.return_value = '''
        {
            "should_print": false,
            "copies": 0,
            "requires_approval": false,
            "printer_group": "general",
            "priority": "low",
            "reason": "Manual digital"
        }
        '''

        decision = self.service.decide(
            document_type="manual",
            confidence=0.85,
            fields={},
            raw_text="Manual de usuario",
            file_name="manual.pdf"
        )

        self.assertFalse(decision['should_print'])

    def test_fallback_to_rules_on_llm_error(self):
        """Test: Fallback a reglas estáticas si LLM falla."""
        self.mock_llm.generate.side_effect = Exception("LLM error")

        decision = self.service.decide(
            document_type="invoice",
            confidence=0.95,
            fields={"supplier": "Test", "amount": "$100"},
            raw_text="Factura",
            file_name="test.pdf"
        )

        # Debe usar regla estática
        self.assertEqual(decision['decision_source'], 'rules')
        self.assertTrue(decision['should_print'])


if __name__ == '__main__':
    unittest.main()