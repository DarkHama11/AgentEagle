import unittest
import os
import tempfile
import yaml
from services.model_manager import ModelManager


class TestModelManager(unittest.TestCase):
    def setUp(self):
        """Configuración inicial para cada test."""
        # Resetear singleton
        ModelManager.reset_instance()

        # Crear archivo de configuración temporal
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "models.yaml")

        self.test_config = {
            "classification_model": "llama3.2:3b",
            "extraction_model": "llama3.2:3b",
            "summary_model": "llama3.2:3b",
            "routing_model": "llama3.2:3b",
            "chat_model": "llama3.2:3b",
            "reasoning_model": "llama3.2:3b",
            "default_model": "llama3.2:3b"
        }

        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(self.test_config, f)

    def tearDown(self):
        """Limpieza después de cada test."""
        ModelManager.reset_instance()
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)

    def test_load_models(self):
        """Test: Cargar configuración desde YAML."""
        manager = ModelManager(config_path=self.config_file)

        self.assertIsNotNone(manager)
        self.assertEqual(manager.config_path, self.config_file)

        all_models = manager.get_all_models()
        self.assertEqual(all_models["classification_model"], "llama3.2:3b")
        self.assertEqual(all_models["extraction_model"], "llama3.2:3b")

    def test_reload_models(self):
        """Test: Recargar configuración."""
        manager = ModelManager(config_path=self.config_file)

        # Modificar archivo
        new_config = self.test_config.copy()
        new_config["classification_model"] = "gemma2:2b"

        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(new_config, f)

        # Recargar
        manager.reload()

        # Verificar cambio
        self.assertEqual(manager.get_model("classification"), "gemma2:2b")

    def test_get_model(self):
        """Test: Obtener modelo por tipo de tarea."""
        manager = ModelManager(config_path=self.config_file)

        model = manager.get_model("classification")
        self.assertEqual(model, "llama3.2:3b")

        model = manager.get_model("extraction")
        self.assertEqual(model, "llama3.2:3b")

        model = manager.get_model("summary")
        self.assertEqual(model, "llama3.2:3b")

    def test_get_model_fallback(self):
        """Test: Fallback a modelo por defecto."""
        manager = ModelManager(config_path=self.config_file)

        # Tarea no configurada debe usar default
        model = manager.get_model("unknown_task")
        self.assertEqual(model, "llama3.2:3b")

    def test_validate(self):
        """Test: Validar configuración."""
        manager = ModelManager(config_path=self.config_file)

        # No debe lanzar excepción
        try:
            manager._validate_config()
            validation_passed = True
        except ValueError:
            validation_passed = False

        self.assertTrue(validation_passed)

    def test_missing_model(self):
        """Test: Configuración con claves faltantes."""
        # Crear configuración incompleta
        incomplete_config = {
            "classification_model": "llama3.2:3b",
            # Faltan otras claves
        }

        incomplete_file = os.path.join(self.temp_dir, "incomplete.yaml")
        with open(incomplete_file, 'w', encoding='utf-8') as f:
            yaml.dump(incomplete_config, f)

        # Debe lanzar excepción
        with self.assertRaises(ValueError):
            ModelManager(config_path=incomplete_file)

        os.remove(incomplete_file)

    def test_singleton_pattern(self):
        """Test: Verificar patrón Singleton."""
        manager1 = ModelManager(config_path=self.config_file)
        manager2 = ModelManager(config_path=self.config_file)

        # Deben ser la misma instancia
        self.assertIs(manager1, manager2)

    def test_update_model(self):
        """Test: Actualizar modelo en memoria."""
        manager = ModelManager(config_path=self.config_file)

        manager.update_model("classification", "gemma2:2b", save_to_file=False)

        model = manager.get_model("classification")
        self.assertEqual(model, "gemma2:2b")

    def test_health_check(self):
        """Test: Verificar disponibilidad de modelos."""
        manager = ModelManager(config_path=self.config_file)

        # Sin Ollama corriendo, debe retornar False
        availability = manager.validate_models()

        # Debe retornar un diccionario
        self.assertIsInstance(availability, dict)

        # Todos los modelos deben estar en el resultado
        self.assertIn("llama3.2:3b", availability)


if __name__ == '__main__':
    unittest.main()