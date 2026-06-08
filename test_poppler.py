import subprocess
import sys

print("=" * 60)
print("🔍 Verificación de dependencias para OCR de PDFs escaneados")
print("=" * 60)

# 1. Verificar Tesseract
print("\n1️⃣  Verificando Tesseract OCR...")
try:
    result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True)
    if result.returncode == 0:
        version = result.stdout.split('\n')[0]
        print(f"   ✅ Tesseract instalado: {version}")
    else:
        print("   ❌ Tesseract no responde correctamente")
except FileNotFoundError:
    print("   ❌ Tesseract no está en el PATH")
    print("   💡 Descarga desde: https://github.com/UB-Mannheim/tesseract/wiki")

# 2. Verificar Poppler
print("\n2️⃣  Verificando Poppler...")
try:
    result = subprocess.run(['pdftoppm', '-v'], capture_output=True, text=True)
    if result.returncode == 0 or "pdftoppm" in result.stderr:
        version = result.stderr.split('\n')[0] if result.stderr else result.stdout.split('\n')[0]
        print(f"   ✅ Poppler instalado: {version}")
    else:
        print("   ❌ Poppler no responde correctamente")
except FileNotFoundError:
    print("   ❌ Poppler no está en el PATH")
    print("   💡 Descarga desde: https://github.com/oschwartz10612/poppler-windows/releases/")
    print("   💡 Agrega la carpeta 'bin' al PATH de Windows")

# 3. Verificar librerías Python
print("\n3️⃣  Verificando librerías Python...")
try:
    import pytesseract
    print(f"   ✅ pytesseract: {pytesseract.__version__}")
except ImportError:
    print("   ❌ pytesseract no instalado")
    print("   💡 Ejecuta: pip install pytesseract")

try:
    import pdf2image
    print(f"   ✅ pdf2image instalado")
except ImportError:
    print("   ❌ pdf2image no instalado")
    print("   💡 Ejecuta: pip install pdf2image")

try:
    from PIL import Image
    import PIL
    print(f"   ✅ Pillow: {PIL.__version__}")
except ImportError:
    print("   ❌ Pillow no instalado")
    print("   💡 Ejecuta: pip install Pillow")

try:
    from pypdf import PdfReader
    import pypdf
    print(f"   ✅ pypdf: {pypdf.__version__}")
except ImportError:
    print("   ❌ pypdf no instalado")
    print("   💡 Ejecuta: pip install pypdf")

print("\n" + "=" * 60)
print("✅ Verificación completada")
print("=" * 60)