# services/layout_reconstruction_service.py
class LayoutReconstructionService:
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "llama3.2"

    def reconstruct_pdf_to_word(self, pdf_path: str) -> dict:
        """Reconstruye el diseño lógico del PDF usando IA"""
        # 1. Extraer bloques de texto con coordenadas
        bloques = self._extraer_bloques(pdf_path)

        # 2. Usar Ollama para ordenar los bloques lógicamente
        prompt = f"""
        Estos son bloques de texto de un PDF con sus coordenadas (x, y).
        Ordena los bloques en el orden de lectura lógico (izquierda-derecha, arriba-abajo).
        Considera que puede haber columnas.

        Bloques: {bloques}

        Devuelve solo los IDs de los bloques en orden, separados por comas.
        """

        orden = self._ask_ollama(prompt)

        # 3. Generar Word con el orden correcto
        return self._generar_word_ordenado(pdf_path, orden)