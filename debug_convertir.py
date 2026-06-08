import time
from pywinauto import Application
from pywinauto import findwindows

print("🔍 Buscando ventanas visibles de PDFgear...")

# Filtramos para encontrar solo ventanas principales visibles
elements = findwindows.find_elements(title_re=".*PDFgear.*", control_type="Window", visible_only=True)

if not elements:
    print("❌ No se encontró ninguna ventana visible de PDFgear.")
    print("💡 Asegúrate de que PDFgear esté abierto y mostrando la pantalla de 'De PDF a Word' con un archivo cargado.")
else:
    print(f"✅ Se encontraron {len(elements)} ventanas candidatas. Usando la principal...")

    # Tomamos el primer elemento visible (usualmente es la ventana principal)
    target_element = elements[0]
    print(f"   -> Título: '{target_element.name}'")
    print(f"   -> Handle (ID único): {target_element.handle}")

    # Nos conectamos usando el handle específico para evitar la ambigüedad
    app = Application(backend="uia").connect(handle=target_element.handle)

    print("⏳ Analizando la estructura de la ventana...")
    time.sleep(2)

    try:
        window = app.window(handle=target_element.handle)
        window.wait('ready', timeout=10)

        print("\n" + "=" * 80)
        print("🔍 ESTRUCTURA DE CONTROLES (Busca la palabra 'Convertir' en la salida):")
        print("=" * 80)

        # Esta es la función mágica que imprime todo
        window.print_control_identifiers()

        print("=" * 80)
        print("✅ Diagnóstico completado.")

    except Exception as e:
        print(f"❌ Error al analizar la ventana: {e}")