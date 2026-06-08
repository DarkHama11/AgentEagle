import requests
import time

OLLAMA_URL = "http://localhost:11434"
MODEL = "llama3.2:3b"


def test_ollama():
    print("=" * 60)
    print("🧠 Probando Ollama con modelo: " + MODEL)
    print("=" * 60)

    # 1. Verificar conexión
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        modelos = r.json().get('models', [])
        print(f"\n✅ Ollama corriendo. Modelos: {[m['name'] for m in modelos]}")
    except Exception as e:
        print(f"\n❌ Error conectando a Ollama: {e}")
        print("   Asegúrate de que Ollama esté corriendo")
        return False

    # 2. Prueba 1: Clasificación de intención
    print("\n📝 Prueba 1: Clasificación de intención")
    print("-" * 60)

    mensajes_prueba = [
        "convierte este PDF a Word",
        "necesito imprimir mi documento",
        "extrae el texto de esta imagen",
        "ayuda",
    ]

    for mensaje in mensajes_prueba:
        print(f"\nUsuario: '{mensaje}'")
        intent = clasificar_intencion(mensaje)
        print(f"🤖 Intención detectada: {intent}")

    # 3. Prueba 2: Análisis de texto
    print("\n\n📝 Prueba 2: Análisis de documento")
    print("-" * 60)

    texto_prueba = """
    Harold Alberto García
    Ingeniero de Software
    Teléfono: 3001234567
    Email: harold@email.com

    Experiencia: 5 años en desarrollo Python
    Habilidades: Django, Flask, Automatización
    """

    analisis = analizar_documento(texto_prueba)
    print(f"\n🤖 Análisis:\n{analisis}")

    return True


def clasificar_intencion(mensaje: str) -> str:
    """Usa Ollama para clasificar la intención del usuario"""
    prompt = f"""Clasifica este mensaje del usuario en UNA de estas categorías:
- pdf2word (si quiere convertir PDF a Word)
- word2pdf (si quiere convertir Word a PDF)
- print (si quiere imprimir)
- ocr (si quiere extraer texto de imagen/PDF)
- analyze (si quiere analizar el documento)
- help (si pide ayuda)

Responde SOLO con la categoría, sin explicaciones.

Mensaje: "{mensaje}"
Categoría:"""

    return consultar_ollama(prompt).strip().lower()


def analizar_documento(texto: str) -> str:
    """Usa Ollama para analizar un documento"""
    prompt = f"""Analiza este documento y genera un resumen breve (máximo 3 líneas)
identificando el tipo de documento y datos clave.

Documento:
{texto}

Análisis:"""

    return consultar_ollama(prompt).strip()


def consultar_ollama(prompt: str) -> str:
    """Consulta el modelo de Ollama"""
    try:
        inicio = time.time()
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Respuestas más deterministas
                    "num_predict": 100  # Limitar longitud
                }
            },
            timeout=60
        )

        if response.status_code == 200:
            tiempo = time.time() - inicio
            respuesta = response.json().get("response", "")
            print(f"   ⏱️ Tiempo: {tiempo:.2f}s")
            return respuesta
        else:
            print(f"   ❌ Error HTTP: {response.status_code}")
            return ""
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return ""


if __name__ == "__main__":
    test_ollama()