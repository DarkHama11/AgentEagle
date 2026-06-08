import os
import time
import glob
import logging
import pyperclip
import pyautogui
import pygetwindow as gw
import ctypes
import shutil
from pathlib import Path

from ..base_plugin import BaseAutomationPlugin
from ..plugin_registry import PluginRegistry
from dto.desktop_automation.action_dto import ActionRequest, ActionResult
from ..auditor import AutomationAuditor

# DPI awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

pyautogui.PAUSE = 0.5
pyautogui.FAILSAFE = True
logger = logging.getLogger(__name__)

IMG_DIR = Path(__file__).parent / 'img'

#  Rutas de carpetas del proyecto
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
UPLOAD_DIR = PROJECT_ROOT / "data" / "telegram_uploads"
OUTPUT_DIR = PROJECT_ROOT / "data" / "telegram_outputs"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logger.info(f"[PDFGear] 📁 Rutas configuradas: {OUTPUT_DIR}")


@PluginRegistry.register
class PDFGearPlugin(BaseAutomationPlugin):
    @property
    def action_type(self) -> str:
        return "PDF_TO_WORD"

    def _buscar_imagen(self, nombre_archivo, confidence=0.8, timeout=15):
        """Busca una imagen en pantalla con reintentos"""
        ruta = IMG_DIR / nombre_archivo
        if not ruta.exists():
            logger.error(f"[PDFGear] ❌ Imagen no existe: {ruta}")
            return None

        inicio = time.time()
        while time.time() - inicio < timeout:
            try:
                location = pyautogui.locateOnScreen(str(ruta), confidence=confidence)
                if location:
                    centro = pyautogui.center(location)
                    logger.info(f"[PDFGear] ✅ {nombre_archivo} encontrada en {centro} (conf={confidence})")
                    return centro
            except pyautogui.ImageNotFoundException:
                pass
            except Exception as e:
                logger.debug(f"[PDFGear] Error buscando {nombre_archivo}: {e}")
            time.sleep(0.5)

        logger.warning(f"[PDFGear] ⏰ Timeout buscando {nombre_archivo}")
        return None

    def _hacer_clic(self, ubicacion, delay=1):
        """Hace clic en una ubicación"""
        if ubicacion:
            pyautogui.click(ubicacion.x, ubicacion.y)
            time.sleep(delay)
            return True
        return False

    def _activar_ventana_pdfgear(self, backend):
        """Activa la ventana de PDFgear usando la conexión del backend"""
        logger.info("[PDFGear] Activando ventana de PDFgear...")

        # Método 1: Usar la conexión del backend
        try:
            if hasattr(backend, 'app') and backend.app:
                main_window = backend.app.top_window()

                if main_window.is_minimized():
                    main_window.restore()
                    time.sleep(0.5)

                main_window.set_focus()
                time.sleep(1)

                logger.info("[PDFGear] ✅ Ventana activada vía backend.app")
                return True
        except Exception as e:
            logger.warning(f"[PDFGear] backend.app falló: {e}")

        # Método 2: Buscar por handle
        try:
            wins = gw.getWindowsWithTitle('PDFgear')
            if wins:
                win = wins[0]
                from pywinauto import Application
                app_temp = Application(backend='uia').connect(handle=win._hWnd)
                app_temp.window(handle=win._hWnd).set_focus()
                time.sleep(1)
                logger.info("[PDFGear] ✅ Ventana activada vía handle")
                return True
        except Exception as e:
            logger.warning(f"[PDFGear] Fallback handle falló: {e}")

        # Método 3: Alt+Tab
        logger.info("[PDFGear] Intentando Alt+Tab...")
        pyautogui.hotkey('alt', 'tab')
        time.sleep(1)
        return True

    def _esperar_dialogo(self, texto_buscar, timeout=15):
        """Espera a que aparezca un diálogo de Windows"""
        inicio = time.time()
        while time.time() - inicio < timeout:
            for w in gw.getAllWindows():
                if w.visible and texto_buscar.lower() in w.title.lower():
                    logger.info(f"[PDFGear] ✅ Diálogo detectado: '{w.title}'")
                    return w
            time.sleep(0.5)
        return None

    def execute(self, request: ActionRequest, backend) -> ActionResult:
        session_id = request.session_id
        input_path = os.path.abspath(request.payload.get("input_path"))

        # Definir ruta de salida
        nombre_base = Path(input_path).stem
        output_path = str(OUTPUT_DIR / f"{nombre_base}.docx")

        logger.info(f"[PDFGear] 📥 Entrada: {input_path}")
        logger.info(f"[PDFGear] 📤 Salida: {output_path}")
        logger.info(f"[PDFGear] 📁 Output dir existe: {OUTPUT_DIR.exists()}")

        if not os.path.exists(input_path):
            return ActionResult(session_id, False, "Archivo de entrada no encontrado", "FileNotFound")

        # Limpiar archivo previo
        if os.path.exists(output_path):
            os.remove(output_path)
            logger.info(f"[PDFGear] 🗑️ Limpiado archivo previo: {output_path}")

        try:
            AutomationAuditor.log_action(session_id, "START", "INFO", input_path)

            # === PASO 0: Limpiar instancias previas ===
            logger.info("[PDFGear] 0. Limpiando instancias previas...")
            os.system('taskkill /F /IM PDFgear* 2>nul')
            time.sleep(2)

            # === PASO 1: Abrir PDFGear ===
            logger.info("[PDFGear] 1. Abriendo PDFGear...")
            backend.start(r"C:\Program Files\PDFgear\PDFLauncher.exe")
            time.sleep(6)

            # Activar ventana
            self._activar_ventana_pdfgear(backend)
            time.sleep(2)

            # === PASO 2: Click en "De PDF a Word" ===
            logger.info("[PDFGear] 2. Buscando 'De PDF a Word'...")
            ubicacion_pdf_word = self._buscar_imagen('02_pantalla_pdf_a_word.png', confidence=0.8, timeout=15)

            if not ubicacion_pdf_word:
                pyautogui.screenshot('debug_paso2.png')
                return ActionResult(session_id, False, "No se encontró 'De PDF a Word'", "Ver debug_paso2.png")

            self._hacer_clic(ubicacion_pdf_word, delay=3)

            # === PASO 3: Click en "+ Añadir archivo" ===
            logger.info("[PDFGear] 3. Buscando botón '+ Añadir archivo'...")
            time.sleep(2)

            ubicacion_anadir = self._buscar_imagen('03_boton_anadir.png', confidence=0.8, timeout=15)

            if not ubicacion_anadir:
                pyautogui.screenshot('debug_paso3.png')
                return ActionResult(session_id, False, "No se encontró botón '+ Añadir archivo'", "Ver debug_paso3.png")

            self._hacer_clic(ubicacion_anadir, delay=2)

            # === PASO 4: Inyectar ruta en diálogo "Abrir" ===
            logger.info("[PDFGear] 4. Esperando diálogo 'Abrir'...")
            dialogo = self._esperar_dialogo("abrir", timeout=10)

            if not dialogo:
                pyautogui.screenshot('debug_paso4.png')
                return ActionResult(session_id, False, "No se abrió el diálogo 'Abrir'", "Ver debug_paso4.png")

            logger.info("[PDFGear] 4. Inyectando ruta del archivo...")
            pyperclip.copy(input_path)
            time.sleep(0.5)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(3)

            logger.info("[PDFGear] ✅ Archivo cargado")
            time.sleep(3)

            # === PASO 5: Click en "..." para cambiar destino ===
            logger.info("[PDFGear] 5. Buscando botón '...' para cambiar destino...")
            ubicacion_puntos = self._buscar_imagen('05_boton_tres_puntos.png', confidence=0.7, timeout=15)

            if ubicacion_puntos:
                self._hacer_clic(ubicacion_puntos, delay=2)

                logger.info("[PDFGear] 5. Esperando diálogo 'Seleccionar carpeta'...")
                dialogo_carpeta = self._esperar_dialogo("seleccionar carpeta", timeout=10)

                if dialogo_carpeta:
                    # Esperar a que el diálogo se estabilice
                    time.sleep(2)

                    # === MÉTODO CORREGIDO: Usar pywinauto para escribir la ruta ===
                    logger.info(f"[PDFGear] Escribiendo ruta en diálogo: {OUTPUT_DIR}")

                    try:
                        from pywinauto import Application
                        from pywinauto.keyboard import send_keys

                        # Conectar al diálogo específico
                        app_select = Application(backend='uia').connect(title_re=".*Seleccionar carpeta.*")
                        window_select = app_select.window(title_re=".*Seleccionar carpeta.*")

                        # Buscar el campo de texto "Carpeta:" (Edit control)
                        edit_carpeta = None

                        # Intentar por auto_id
                        try:
                            edit_carpeta = window_select.child_window(auto_id="1152", control_type="Edit")
                            if not edit_carpeta.exists(timeout=3):
                                edit_carpeta = None
                        except:
                            pass

                        # Intentar por título
                        if not edit_carpeta:
                            try:
                                edit_carpeta = window_select.child_window(title="Carpeta:", control_type="Edit")
                                if not edit_carpeta.exists(timeout=3):
                                    edit_carpeta = None
                            except:
                                pass

                        if edit_carpeta:
                            # Hacer clic en el campo para darle foco
                            edit_carpeta.click_input()
                            time.sleep(0.5)

                            # Seleccionar todo el texto existente
                            send_keys('^a')
                            time.sleep(0.3)

                            # Escribir la ruta completa directamente
                            ruta_str = str(OUTPUT_DIR)
                            edit_carpeta.set_edit_text(ruta_str)
                            time.sleep(1)

                            logger.info(f"[PDFGear] ✅ Ruta escrita en campo: {ruta_str}")

                            # Verificar que se escribió correctamente
                            try:
                                texto_actual = edit_carpeta.get_value()
                                logger.info(f"[PDFGear] Texto actual en campo: {texto_actual}")
                            except:
                                pass

                            # Hacer clic en el botón "Seleccionar carpeta"
                            btn_select = window_select.child_window(title="Seleccionar carpeta", control_type="Button")
                            if btn_select.exists(timeout=5):
                                btn_select.click_input()
                                logger.info("[PDFGear] ✅ Clic en 'Seleccionar carpeta'")
                                time.sleep(2)
                            else:
                                # Fallback: Enter
                                send_keys('{ENTER}')
                                logger.info("[PDFGear] Enter como fallback")
                                time.sleep(2)
                        else:
                            # Si no encuentra el campo, usar método alternativo
                            logger.warning("[PDFGear] No se encontró campo de texto, usando método alternativo...")

                            # Hacer clic en el diálogo para activarlo
                            dialogo_carpeta.activate()
                            time.sleep(0.5)

                            # Navegar al campo de texto con Tab
                            send_keys('{TAB}{TAB}{TAB}{TAB}')
                            time.sleep(0.5)

                            # Seleccionar todo y escribir
                            send_keys('^a')
                            time.sleep(0.3)
                            send_keys(str(OUTPUT_DIR))
                            time.sleep(1)
                            send_keys('{ENTER}')
                            time.sleep(2)

                    except Exception as e:
                        logger.error(f"[PDFGear] Error escribiendo ruta: {e}", exc_info=True)
                        # Fallback final: Alt+D para ir a la barra de dirección y escribir
                        try:
                            send_keys('%d')  # Alt+D activa la barra de dirección
                            time.sleep(0.5)
                            send_keys('^a')
                            time.sleep(0.3)
                            send_keys(str(OUTPUT_DIR))
                            time.sleep(0.5)
                            send_keys('{ENTER}')
                            time.sleep(2)
                        except:
                            pass

                    logger.info(f"[PDFGear] ✅ Destino configurado: {OUTPUT_DIR}")
                else:
                    logger.warning("[PDFGear] ⚠️ No se abrió diálogo de carpeta")
            else:
                logger.warning("[PDFGear] ⚠️ Botón '...' no encontrado")

            # === PASO 6: Click en "Convertir" ===
            logger.info("[PDFGear] 6. Buscando botón 'Convertir'...")

            # Esperar a que la interfaz se estabilice
            time.sleep(3)

            # Método 1: Buscar por imagen
            ubicacion_convertir = self._buscar_imagen('07_boton_convertir.png', confidence=0.8, timeout=15)

            # Método 2: Si no se encuentra, intentar con pywinauto
            if not ubicacion_convertir:
                logger.info("[PDFGear] Intentando buscar 'Convertir' con pywinauto...")
                try:
                    from pywinauto import Application
                    app = Application(backend='uia').connect(title_re=".*PDFgear.*")
                    window = app.window(title_re=".*PDFgear.*")

                    # Buscar botón por texto
                    btn_convert = window.child_window(title_re=".*[Cc]onvertir.*|[Cc]onvert.*", control_type="Button")
                    if btn_convert.exists(timeout=5):
                        rect = btn_convert.rectangle()
                        centro_x = rect.left + (rect.right - rect.left) // 2
                        centro_y = rect.top + (rect.bottom - rect.top) // 2
                        ubicacion_convertir = type('obj', (), {'x': centro_x, 'y': centro_y})()
                        logger.info(f"[PDFGear] ✅ Botón encontrado con pywinauto en {centro_x}, {centro_y}")
                except Exception as e:
                    logger.warning(f"[PDFGear] Pywinauto falló: {e}")

            # Método 3: Fallback con coordenadas relativas
            if not ubicacion_convertir:
                logger.warning("[PDFGear] ️ Usando coordenadas relativas para 'Convertir'...")
                wins = gw.getWindowsWithTitle('PDFgear')
                if wins:
                    win = wins[0]
                    ubicacion_convertir = type('obj', (), {
                        'x': win.left + int(win.width * 0.90),
                        'y': win.top + int(win.height * 0.90)
                    })()
                    logger.info(f"[PDFGear] Coordenadas fallback: {ubicacion_convertir.x}, {ubicacion_convertir.y}")

            if not ubicacion_convertir:
                pyautogui.screenshot('debug_paso6.png')
                return ActionResult(session_id, False, "No se encontró botón 'Convertir'", "Ver debug_paso6.png")

            self._hacer_clic(ubicacion_convertir, delay=3)

            # === PASO 7: Esperar conversión ===
            logger.info("[PDFGear] 7. Esperando conversión (30 segundos)...")
            time.sleep(30)

            # === PASO 8: Buscar archivo de salida ===
            logger.info("[PDFGear] 8. Buscando archivo convertido...")

            # Buscar por nombre exacto o patrón
            patrones = [
                str(OUTPUT_DIR / f"{nombre_base}.docx"),
                str(OUTPUT_DIR / f"{nombre_base}*.docx"),
            ]

            archivo_salida = None
            for patron in patrones:
                archivos = glob.glob(patron)
                if archivos:
                    archivo_salida = archivos[0]
                    logger.info(f"[PDFGear] ✅ Archivo encontrado: {archivo_salida}")
                    break

            # Si no se encontró, buscar el más reciente
            if not archivo_salida:
                archivos_recientes = sorted(OUTPUT_DIR.glob("*.docx"), key=os.path.getmtime, reverse=True)
                if archivos_recientes:
                    archivo_salida = str(archivos_recientes[0])
                    logger.info(f"[PDFGear] ✅ Archivo reciente encontrado: {archivo_salida}")

            if not archivo_salida or not os.path.exists(archivo_salida):
                pyautogui.screenshot('debug_paso8.png')
                return ActionResult(session_id, False, f"Archivo no encontrado en {OUTPUT_DIR}", "Ver debug_paso8.png")

            # Copiar/Renombrar si es necesario
            if archivo_salida != output_path:
                try:
                    shutil.copy2(archivo_salida, output_path)
                    logger.info(f"[PDFGear] 📝 Copiado a: {output_path}")
                except Exception as e:
                    logger.warning(f"[PDFGear] ⚠️ No se pudo copiar: {e}")
                    output_path = archivo_salida

            logger.info(f"[PDFGear] ✅ Conversión completada: {output_path}")
            AutomationAuditor.log_action(session_id, "COMPLETE", "SUCCESS", output_path)

            return ActionResult(session_id, True, "Conversión completada", output_data={"output_path": output_path})

        except Exception as e:
            logger.error(f"[PDFGear] ❌ Error: {e}", exc_info=True)
            pyautogui.screenshot('debug_error.png')
            return ActionResult(session_id, False, "Error durante la conversión", str(e))

        finally:
            try:
                backend.kill()
            except Exception:
                pass