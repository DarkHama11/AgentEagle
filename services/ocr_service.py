# services/ocr_service.py
class OCRService:
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "llama3.2"

    def ocr_y_analizar(self, imagen_path: str) -> dict:
        """OCR + análisis con Ollama"""
        # 1. OCR tradicional
        texto_crudo = self._ejecutar_ocr(imagen_path)

        # 2. Ollama limpia y estructura el texto
        prompt = f"""
        Este texto fue extraído por OCR de una imagen.
        Puede tener errores. Corrige y estructura el texto:

        {texto_crudo}

        Devuelve el texto limpio y estructurado.
        """

        texto_limpio = self._ask_ollama(prompt)
        return {"crudo": texto_crudo, "limpio": texto_limpio}