import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.windows_print_service import WindowsPrintService

print("=" * 60)
print("🖨️ Prueba de Impresión en Windows (Modo Forzado)")
print("=" * 60)

# 🎯 FORZAR la impresora física real
target_printer = "HP LaserJet Professional M1212nf MFP"
print_service = WindowsPrintService(default_printer=target_printer)

# Listar impresoras disponibles
print("\n📋 Impresoras disponibles:")
printers = print_service.list_printers()
for i, printer in enumerate(printers, 1):
    marker = " <-- 🎯 OBJETIVO" if printer == target_printer else ""
    print(f"  {i}. {printer}{marker}")

# Probar impresión
test_file = "test_invoice.pdf"
if not os.path.exists(test_file):
    print(f"\n⚠️ No se encontró {test_file}")
    sys.exit(1)

print(f"\n📄 Imprimiendo: {test_file}")
print(f"🖨️  Usando impresora: {target_printer}")

result = print_service.print_file(
    file_path=test_file,
    job_id="TEST-001",
    printer=target_printer,  # Forzamos la impresora aquí
    copies=1
)

if result['status'] == 'success':
    print(f"✅ ¡ÉXITO! Trabajo enviado a la cola de impresión.")
    print(f"🆔 Job ID: {result['cups_job_id']}")
else:
    print(f"❌ Error: {result['error']}")
    print("\n💡 SOLUCIÓN AL ERROR 31:")
    print("Windows está intentando usar Microsoft Edge (u otra app UWP) para imprimir.")
    print("Estas apps no soportan impresión silenciosa desde scripts.")
    print("\n👉 PASOS PARA SOLUCIONARLO:")
    print("1. Descarga e instala 'SumatraPDF' (gratuito y ligero) o 'Adobe Acrobat Reader'.")
    print("2. Click derecho en 'test_invoice.pdf' > Propiedades.")
    print("3. En 'Se abre con:', haz clic en 'Cambiar' y selecciona SumatraPDF o Adobe.")
    print("4. Vuelve a ejecutar este script.")

print("\n" + "=" * 60)