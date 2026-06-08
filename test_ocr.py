import os
import platform
import subprocess
import pytesseract

# 1. Forzar la ruta de Windows por defecto si no está en el PATH
if platform.system() == "Windows":
    default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(default_path):
        pytesseract.pytesseract.tesseract_cmd = default_path
        print(f"✅ Ruta de Tesseract establecida manualmente: {default_path}")
    else:
        print("❌ No se encontró Tesseract en la ruta por defecto. Por favor, instálalo.")
        exit(1)
else:
    print("✅ Ruta de Tesseract:", pytesseract.pytesseract.tesseract_cmd)

# 2. Verificar versión usando la ruta explícita
try:
    cmd = [pytesseract.pytesseract.tesseract_cmd, '--version']
    result = subprocess.run(cmd, capture_output=True, text=True)
    print("\n📄 Versión instalada:")
    print(result.stdout.split('\n')[0])
    print("\n🎉 ¡Tesseract está listo para ser usado por AgentEagle!")
except Exception as e:
    print(f"\n❌ Error al ejecutar Tesseract: {e}")