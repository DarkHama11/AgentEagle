import os
from pdf2image import convert_from_path
import pytesseract

# Tu configuración específica
POPPLER_PATH = r"D:\programa\Release-26.02.0-0\poppler-26.02.0\Library\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

pdf_file = "test_invoice.pdf"

if not os.path.exists(pdf_file):
    print(f"❌ No se encontró {pdf_file}")
    exit(1)

print(f"📄 Procesando: {pdf_file}")
print(f"📂 Poppler: {POPPLER_PATH}")
print("🔄 Convirtiendo PDF a imágenes...")

try:
    images = convert_from_path(pdf_file, poppler_path=POPPLER_PATH)
    print(f"✅ {len(images)} páginas convertidas")

    full_text = ""
    for i, image in enumerate(images, 1):
        print(f"🔍 Aplicando OCR a página {i}...")
        text = pytesseract.image_to_string(image, lang="spa+eng")
        full_text += text + "\n\n"

    print("\n" + "=" * 60)
    print("📝 TEXTO EXTRAÍDO:")
    print("=" * 60)
    print(full_text[:1000])
    print("=" * 60)
    print(f"\n✅ Total: {len(full_text)} caracteres extraídos")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()