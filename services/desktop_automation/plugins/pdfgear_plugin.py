import os
import logging
import time
import glob
import pyperclip
import pyautogui
import pygetwindow as gw
from pywinauto import Application as PywinautoApp
import ctypes

from ..base_plugin import BaseAutomationPlugin
from ..plugin_registry import PluginRegistry
from dto.desktop_automation.action_dto import ActionRequest, ActionResult
from ..auditor import AutomationAuditor

# Configuración de DPI para soporte multi-pantalla
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

pyautogui.PAUSE = 0.3
pyautogui.FAILSAFE = True
logger = logging.getLogger(__name__)


@PluginRegistry.register
class PDFGearPlugin(BaseAutomationPlugin):
    @property
    def action_type(self) -> str:
        return "PDF_TO_WORD"

    def execute(self, request: ActionRequest, backend) -> ActionResult:
        session_id = request.session_id
        input_path = request.payload.get("input_path")
        output_path = request.payload.get("output_path")
        debug_img = "debug_dialogo_abrir.png"

        if not os.path.exists(input_path):
            return ActionResult(session_id, False, "Archivo de entrada no encontrado", "FileNotFound")

        # PASO 0: LIMPIEZA
        if os.path.exists(output_path):
            logger.info(f"[PDFGear] Eliminando archivo .docx previo: {output_path}")
            os.remove(output_path)

        exe_path = r"C:\Program Files\PDFgear\PDFLauncher.exe"

        try:
            AutomationAuditor.log_action(session_id, "START", "INFO", input_path)
            logger.info(f"[PDFGear] Iniciando aplicación...")

            backend.start(exe_path)
            time.sleep(4)

            # PASO 1: Navegar a la herramienta
            logger.info("[PDFGear] 1. Navegando a 'De PDF a Word'...")
            backend.click_button(".*PDFgear.*", "lbtnHotToolPDF2Word")
            time.sleep(3)

            # PASO 2: Buscar botón '+ Añadir archivo' con Computer Vision
            logger.info("[PDFGear] 2. Buscando botón '+ Añadir archivo'...")

            wins = gw.getWindowsWithTitle('PDFgear')
            if not wins:
                raise Exception("No se encontró la ventana de PDFgear")

            win = wins[0]
            win.activate()
            time.sleep(1)

            button_clicked = False

            # MÉTODO A: Visión por computadora
            btn_images = [
                os.path.join(os.path.dirname(__file__), "boton_anadir_limpio.png"),
                os.path.join(os.path.dirname(__file__), "boton_anadir.png")
            ]

            for btn_image_path in btn_images:
                if os.path.exists(btn_image_path):
                    logger.info(f"[PDFGear] Intentando con imagen: {os.path.basename(btn_image_path)}")

                    search_region = (win.left, win.top, win.width, win.height)

                    for confidence in [0.9, 0.8, 0.7, 0.6, 0.5]:
                        try:
                            button_location = pyautogui.locateOnScreen(
                                btn_image_path,
                                region=search_region,
                                confidence=confidence
                            )
                            if button_location:
                                btn_center = pyautogui.center(button_location)
                                btn_x, btn_y = btn_center

                                logger.info(f"[PDFGear] Botón encontrado con confianza {confidence} en X={btn_x}, Y={btn_y}")
                                pyautogui.click(btn_x, btn_y)
                                button_clicked = True
                                break
                        except Exception:
                            continue

                    if button_clicked:
                        break

            # MÉTODO B: Fallback con coordenadas relativas
            if not button_clicked:
                logger.warning("[PDFGear] Visión por computadora falló. Usando coordenadas relativas...")

                btn_x = win.left + int(win.width * 0.50)
                btn_y = win.top + int(win.height * 0.15)

                logger.info(f"[PDFGear] Clic con coordenadas relativas: X={btn_x}, Y={btn_y}")
                pyautogui.click(btn_x, btn_y)
                button_clicked = True

            time.sleep(3)

            # PASO 3: Verificar que se abrió el diálogo de Windows
            logger.info("[PDFGear] 3. Verificando que se abrió el diálogo 'Abrir'...")
            dialog_found = False
            dialog_window = None

            for attempt in range(5):
                all_wins = gw.getAllWindows()
                for w in all_wins:
                    if w.visible and not w.isMinimized:
                        title_lower = w.title.lower()
                        if ('abrir' in title_lower or 'open' in title_lower) and 'pdfgear' not in title_lower:
                            logger.info(f"[PDFGear] Diálogo detectado: '{w.title}'")
                            dialog_window = w
                            dialog_found = True
                            break
                if dialog_found:
                    break
                time.sleep(1)

            if not dialog_found:
                logger.error("[PDFGear] No se abrió el diálogo 'Abrir'")
                pyautogui.screenshot(debug_img)
                raise Exception(f"No se abrió el diálogo de Windows. Revisa '{debug_img}'")

            # PASO 4: Inyectar ruta usando pywinauto
            logger.info("[PDFGear] 4. Inyectando ruta en el diálogo...")

            try:
                app_open = PywinautoApp(backend="uia").connect(handle=dialog_window._hWnd)
                dlg = app_open.window(handle=dialog_window._hWnd)
                dlg.wait('ready', timeout=5)

                edit_control = dlg.child_window(auto_id="1148", control_type="Edit")
                edit_control.wait('ready', timeout=3)
                edit_control.set_focus()
                time.sleep(0.3)

                edit_control.set_text("")
                time.sleep(0.2)
                edit_control.set_text(input_path)
                time.sleep(0.5)

                logger.info(f"[PDFGear] Ruta escrita: {input_path}")

                btn_open = dlg.child_window(auto_id="1", control_type="Button")
                btn_open.click_input()

                logger.info("[PDFGear] Ruta inyectada y diálogo cerrado")

            except Exception as e:
                logger.error(f"[PDFGear] Error con pywinauto: {e}", exc_info=True)
                raise

            # PASO 5: Esperar a que PDFgear cargue el archivo
            logger.info("[PDFGear] 5. Esperando a que PDFgear cargue el archivo en la cola...")
            time.sleep(8)

            pyautogui.screenshot(debug_img)
            logger.info(f"[PDFGear] Captura guardada como '{debug_img}'")

            # PASO 6: Cambiar ruta de salida
            logger.info("[PDFGear] 6. Cambiando ruta de salida...")

            output_folder = os.path.dirname(input_path)
            logger.info(f"[PDFGear] Ruta de salida deseada: {output_folder}")

            # Buscar el botón "..." con computer vision
            btn_dots_img = os.path.join(os.path.dirname(__file__), "boton_ruta_salida.png")
            btn_dots_clicked = False

            if os.path.exists(btn_dots_img):
                logger.info("[PDFGear] Buscando botón '...' con computer vision...")

                try:
                    btn_dots_location = pyautogui.locateOnScreen(btn_dots_img, confidence=0.8)
                    if btn_dots_location:
                        btn_dots_center = pyautogui.center(btn_dots_location)
                        pyautogui.click(btn_dots_center)
                        btn_dots_clicked = True
                        logger.info(f"[PDFGear] Botón '...' encontrado y clickeado")
                except Exception as e:
                    logger.warning(f"[PDFGear] No se encontró botón '...' con computer vision: {e}")

            if not btn_dots_clicked:
                logger.warning("[PDFGear] Usando coordenadas para botón '...'")
                btn_dots_x = win.left + int(win.width * 0.95)
                btn_dots_y = win.top + int(win.height * 0.85)
                pyautogui.click(btn_dots_x, btn_dots_y)

            # Esperar a que se abra el diálogo "Seleccionar carpeta"
            logger.info("[PDFGear] Esperando a que se abra el diálogo 'Seleccionar carpeta'...")
            time.sleep(4)

            folder_dialog_found = False
            folder_dialog = None

            for attempt in range(10):
                all_wins = gw.getAllWindows()
                for w in all_wins:
                    if w.visible and not w.isMinimized:
                        title_lower = w.title.lower()
                        if 'seleccionar carpeta' in title_lower:
                            logger.info(f"[PDFGear] Diálogo 'Seleccionar carpeta' detectado: '{w.title}'")
                            folder_dialog = w
                            folder_dialog_found = True
                            break
                if folder_dialog_found:
                    break
                logger.info(f"[PDFGear] Intento {attempt + 1}/10...")
                time.sleep(1)

            if folder_dialog_found and folder_dialog:
                logger.info("[PDFGear] Conectando al diálogo con pywinauto...")

                try:
                    app_folder = PywinautoApp(backend="uia").connect(handle=folder_dialog._hWnd)
                    dlg_folder = app_folder.window(handle=folder_dialog._hWnd)
                    dlg_folder.wait('ready', timeout=5)

                    # Buscar el campo "Carpeta:"
                    folder_edit = None

                    # Método 1: Buscar por título
                    try:
                        folder_edit = dlg_folder.child_window(title="Carpeta:", control_type="Edit")
                        folder_edit.wait('ready', timeout=3)
                        logger.info("[PDFGear] Campo 'Carpeta:' encontrado por título")
                    except:
                        pass

                    # Método 2: Buscar por auto_id
                    if not folder_edit:
                        try:
                            folder_edit = dlg_folder.child_window(auto_id="1152", control_type="Edit")
                            folder_edit.wait('ready', timeout=3)
                            logger.info("[PDFGear] Campo 'Carpeta:' encontrado por auto_id")
                        except:
                            pass

                    # Método 3: Buscar el último Edit control
                    if not folder_edit:
                        try:
                            all_edits = dlg_folder.descendants(control_type="Edit")
                            if all_edits:
                                folder_edit = all_edits[-1]
                                logger.info(f"[PDFGear] Usando último Edit control: {folder_edit}")
                        except:
                            pass

                    if folder_edit:
                        folder_edit.set_focus()
                        time.sleep(0.5)

                        folder_edit.set_text("")
                        time.sleep(0.3)
                        folder_edit.set_text(output_folder)
                        time.sleep(0.5)

                        logger.info(f"[PDFGear] Ruta escrita en campo 'Carpeta:': {output_folder}")

                        # Hacer clic en "Seleccionar carpeta"
                        try:
                            btn_select = dlg_folder.child_window(title="Seleccionar carpeta", control_type="Button")
                            btn_select.click_input()
                            logger.info("[PDFGear] Clic en 'Seleccionar carpeta'")
                        except:
                            try:
                                btn_select = dlg_folder.child_window(auto_id="1", control_type="Button")
                                btn_select.click_input()
                                logger.info("[PDFGear] Clic en botón por auto_id")
                            except Exception as e:
                                logger.warning(f"[PDFGear] No se pudo hacer clic en 'Seleccionar carpeta': {e}")

                        time.sleep(2)
                        logger.info("[PDFGear] Ruta de salida cambiada exitosamente")
                    else:
                        logger.warning("[PDFGear] No se encontró el campo 'Carpeta:'")

                except Exception as e:
                    logger.error(f"[PDFGear] Error con pywinauto: {e}", exc_info=True)
            else:
                logger.warning("[PDFGear] No se encontró diálogo 'Seleccionar carpeta'. Continuando con ruta por defecto...")

            # PASO 7: Hacer clic en "Convertir"
            logger.info("[PDFGear] 7. Haciendo clic en 'Convertir'...")
            wins = gw.getWindowsWithTitle('PDFgear')
            if wins:
                win = wins[0]
                win.activate()
                time.sleep(1)

                click_x = win.left + int(win.width * 0.88)
                click_y = win.top + int(win.height * 0.88)

                logger.info(f"[PDFGear] Clic en 'Convertir': X={click_x}, Y={click_y}")
                pyautogui.click(click_x, click_y)
                logger.info("[PDFGear] Clic en 'Convertir' ejecutado")

            # PASO 8: Esperar a que finalice la conversión
            logger.info("[PDFGear] 8. Esperando a que finalice la conversión...")
            time.sleep(20)

            # PASO 9: Verificación real
            logger.info("[PDFGear] 9. Buscando archivo de salida...")

            base_name = os.path.splitext(os.path.basename(input_path))[0]
            found_output = None

            # Buscar en la carpeta de entrada
            dir_name = os.path.dirname(input_path)
            matches = glob.glob(os.path.join(dir_name, f"{base_name}*.docx"))
            if matches:
                found_output = matches[0]
                logger.info(f"[PDFGear] Archivo encontrado en carpeta de entrada: {found_output}")

            # Si no se encontró, buscar en OneDrive
            if not found_output:
                onedrive_path = r"C:\Users\harol\OneDrive\Documentos"
                if os.path.exists(onedrive_path):
                    matches = glob.glob(os.path.join(onedrive_path, f"{base_name}*.docx"))
                    if matches:
                        found_output = matches[0]
                        logger.info(f"[PDFGear] Archivo encontrado en OneDrive: {found_output}")

            if found_output:
                output_path = found_output
                AutomationAuditor.log_action(session_id, "COMPLETE", "SUCCESS", output_path)
                return ActionResult(session_id, True, "Conversión completada exitosamente", {"output_path": output_path})
            else:
                raise Exception(f"El archivo de salida NO se encontró. Buscado: {base_name}*.docx")

        except Exception as e:
            logger.error(f"[PDFGear] Error durante la automatización: {e}", exc_info=True)
            return ActionResult(session_id, False, "Fallo en automatización", str(e))

        finally:
            self.cleanup(backend)

    def cleanup(self, backend):
        try:
            backend.kill()
        except Exception as e:
            logger.warning(f"[PDFGear] Error al limpiar backend: {e}")