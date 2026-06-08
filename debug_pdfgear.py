import time
from pywinauto import Application

print("🚀 Iniciando PDFgear para diagnóstico...")
app = Application(backend="uia").start(r"C:\Program Files\PDFgear\PDFLauncher.exe")

print("⏳ Esperando 5 segundos a que cargue la ventana principal...")
time.sleep(5)

try:
    # Buscamos la ventana principal
    window = app.window(title_re=".*PDFgear.*")
    window.wait('ready', timeout=10)

    print("\n" + "=" * 80)
    print("🔍 ESTRUCTURA DE CONTROLES DE LA VENTANA PRINCIPAL:")
    print("=" * 80)

    # Esta es la función mágica que imprime todo lo que pywinauto puede ver
    window.print_control_identifiers()

    print("=" * 80)
    print("✅ Diagnóstico completado. Puedes cerrar PDFgear manualmente.")

except Exception as e:
    print(f"❌ Error al analizar la ventana: {e}")