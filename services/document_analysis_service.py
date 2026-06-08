# services/document_analysis_service.py
import requests
import PyPDF2
import logging

logger = logging.getLogger(__name__)


class DocumentAnalysisService:
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "llama3.2"

    def analyze_pdf(self, pdf_path: str) -> dict:
        """Analiza un PDF con Ollama"""
        # 1. Extraer texto del PDF
        texto = self._extraer_texto(pdf_path)

        # 2. Enviar a Ollama para análisis
        prompt = f"""
        Analiza este documento y devuelve un JSON con:
        - tipo: tipo de documento (CV, factura, contrato, etc)
        - resumen: resumen en 2-3 líneas
        - datos_clave: lista de datos importantes encontrados

        Documento:
        {texto[:3000]}
        """

        respuesta = self._ask_ollama(prompt)
        return {"texto": texto, "analisis": respuesta}

    def _extraer_texto(self, pdf_path: str) -> str:
        """Extrae texto de un PDF"""
        texto = ""
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                texto += page.extract_text() + "\n"
        return texto

    def _ask_ollama(self, prompt: str) -> str:
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60
            )
            return response.json().get("response", "")
        except Exception as e:
            logger.error(f"Error Ollama: {e}")
            return ""