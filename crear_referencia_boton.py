import time
import os
import pyautogui
import pygetwindow as gw
from pywinauto import Application

print("🤖 Script automático para crear referencia del botón '+ Añadir archivo'")
print("=" * 70)

# Ruta donde se guardará la imagen
output_path = r"F:\proyectosPer\AgentEagle\services\desktop_automation\plugins\boton_anadir.png"

# Asegurar que la carpeta exista
os.makedirs(os.path.dirname(output_path), exist_ok=True)

print("\n1️⃣  Abriendo PDFgear...")
app = Application(backend="uia").start(r"C:\Program Files\PDFgear\PDFLauncher.exe")
time.sleep(4)

print("2️⃣  Navegando a 'De PDF a Word'...")
# Usar pywinauto para hacer clic en el botón de navegación
wins = gw.getWindowsWithTitle('PDFgear')
if wins:
    win = wins[0]
    win.activate()
    time.sleep(1)

    # Buscar el botón por auto_id (ya sabemos que funciona)
    window = app.window(title_re=".*PDFgear.*")
    try:
        btn = window.child_window(auto_id="lbtnHotToolPDF2Word", control_type="Button")
        btn.wait('ready', timeout=5)
        btn.click_input()
        print("   ✅ Clic en 'De PDF a Word' exitoso")
    except Exception as e:
        print(f"   ️ No se pudo hacer clic automático: {e}")
        print("   💡 Haz clic manualmente en 'De PDF a Word' ahora...")
        time.sleep(5)

time.sleep(3)

print("\n3️  Tomando captura de pantalla...")
# Tomar captura completa
screenshot = pyautogui.screenshot()
screenshot.save("captura_completa.png")
print(f"   ✅ Captura completa guardada como 'captura_completa.png'")

print("\n4️⃣  Recortando el botón '+ Añadir archivo'...")
# Basado en la estructura de PDFgear, el botón está aproximadamente en:
# - Centro horizontal de la ventana
# - Parte superior de la zona roja (aprox 15-20% desde el top de la ventana)

wins = gw.getWindowsWithTitle('PDFgear')
if wins:
    win = wins[0]

    # Coordenadas del botón (ajustadas según la captura anterior)
    # El botón blanco "+ Añadir archivo" está centrado en la zona roja superior
    btn_left = win.left + int(win.width * 0.40)
    btn_top = win.top + int(win.height * 0.10)
    btn_width = int(win.width * 0.20)
    btn_height = int(win.height * 0.08)

    print(f"   📍 Región del botón: X={btn_left}, Y={btn_top}, W={btn_width}, H={btn_height}")

    # Recortar la imagen
    btn_image = screenshot.crop((btn_left, btn_top, btn_left + btn_width, btn_top + btn_height))
    btn_image.save(output_path)

    print(f"\n✅ ¡Imagen de referencia creada exitosamente!")
    print(f"   📁 Ruta: {output_path}")
    print(f"    Tamaño: {btn_width}x{btn_height} píxeles")
else:
    print("   ❌ No se encontró la ventana de PDFgear")

print("\n" + "=" * 70)
print("🎉 ¡Listo! Ahora puedes ejecutar 'python main.py'")
print("💡 Si el botón no se detecta bien, ajusta manualmente la imagen en Paint")