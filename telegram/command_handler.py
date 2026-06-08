import logging
import requests
from typing import Dict, Any, Optional, Set
from datetime import datetime

logger = logging.getLogger("AgentEagle.TelegramCommandHandler")


class TelegramCommandHandler:
    """
    Maneja comandos de Telegram y recuerda la intención (modo) de cada chat.
    """

    def __init__(
            self,
            bot_token: str,
            allowed_chat_ids: Set[str],
            orchestrator=None,
            event_bus=None,
            approval_manager=None
    ):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.allowed_chat_ids = allowed_chat_ids
        self.orchestrator = orchestrator
        self.event_bus = event_bus
        self.approval_manager = approval_manager

        self.chat_modes: Dict[str, str] = {}

        self.commands = {
            # Comandos existentes
            "start": self._cmd_start,
            "menu": self._cmd_menu,
            "help": self._cmd_help,
            "doc": self._cmd_document_pipeline,
            "process": self._cmd_document_pipeline,
            "pay": self._cmd_payment_pipeline,
            "payment": self._cmd_payment_pipeline,
            "print": self._cmd_smart_print,
            "imprimir": self._cmd_smart_print,
            "status": self._cmd_status,
            "estado": self._cmd_status,
            "printers": self._cmd_printers,
            "impresoras": self._cmd_printers,
            # Comandos de conversión
            "pdf2word": self._cmd_pdf_to_word,
            "word2pdf": self._cmd_word_to_pdf,
            "ocr": self._cmd_ocr,
            "texto": self._cmd_ocr,
            #  Nuevo comando Smart Convert
            "smart_convert": self._cmd_smart_convert,
            "reconstruir": self._cmd_smart_convert,
        }

        logger.info(f"TelegramCommandHandler inicializado con {len(self.commands)} comandos")

    def set_chat_mode(self, chat_id: str, mode: str) -> None:
        self.chat_modes[chat_id] = mode
        logger.info(f"Modo de chat {chat_id} establecido a: {mode}")

    def get_chat_mode(self, chat_id: str) -> str:
        return self.chat_modes.get(chat_id, 'print')

    def handle_command(self, message: Dict[str, Any]) -> bool:
        text = message.get('text', '').strip()
        if not text.startswith('/'):
            return False

        chat = message.get('chat', {})
        chat_id = str(chat.get('id', ''))
        from_user = message.get('from', {})
        username = from_user.get('username', 'unknown')

        if chat_id not in self.allowed_chat_ids:
            logger.debug(f"Comando ignorado de chat no autorizado: {chat_id}")
            return True

        parts = text[1:].split(maxsplit=1)
        command = parts[0].lower().split('@')[0]
        args = parts[1] if len(parts) > 1 else ""

        logger.info(f"📨 Comando recibido: /{command} de @{username} | Args: '{args}'")

        handler = self.commands.get(command)
        if handler:
            try:
                handler(chat_id, args, message)
            except Exception as e:
                logger.error(f"Error ejecutando comando /{command}: {e}", exc_info=True)
                self._send_message(chat_id, f" Error ejecutando comando: {str(e)}")
        else:
            self._send_message(chat_id,
                               f"❓ Comando desconocido: <code>/{command}</code>\n\nUsa /menu para ver las opciones.")

        return True

    def _cmd_start(self, chat_id: str, args: str, message: Dict) -> None:
        self.set_chat_mode(chat_id, 'print')
        self._cmd_menu(chat_id, args, message)

    def _cmd_menu(self, chat_id: str, args: str, message: Dict) -> None:
        self.set_chat_mode(chat_id, 'print')
        text = (
            "🦅 <b>AgentEagle 2.0 - Menú Principal</b>\n\n"
            "📄 <b>ANÁLISIS</b>\n"
            "/doc - Solo análisis (OCR + IA, sin imprimir)\n\n"
            "🖨️ <b>IMPRESIÓN</b>\n"
            "/print - Smart Print (análisis + impresión)\n"
            "/pay - Pago con aprobación\n\n"
            "🔄 <b>CONVERSIONES</b>\n"
            "/pdf2word - Convertir PDF a Word\n"
            "/word2pdf - Convertir Word a PDF\n"
            "/smart_convert - Reconstruir diseño (CVs 2 columnas)\n"
            "/ocr - Extraer texto de imagen/PDF\n\n"
            "📊 <b>SISTEMA</b>\n"
            "/status - Estado del sistema\n"
            "/printers - Lista impresoras\n"
            "/help - Ayuda detallada\n\n"
            "💡 <i>Usa los botones de abajo:</i>"
        )

        inline_keyboard = {"inline_keyboard": [
            [{"text": "📄 Analizar", "callback_data": "cmd:doc"}, {"text": "🖨️ Imprimir", "callback_data": "cmd:print"}],
            [{"text": "📄→📝 PDF→Word", "callback_data": "cmd:pdf2word"},
             {"text": "📝→📄 Word→PDF", "callback_data": "cmd:word2pdf"}],
            [{"text": "🧠 Smart Convert", "callback_data": "cmd:smart_convert"},
             {"text": "🔍 OCR Texto", "callback_data": "cmd:ocr"}],
            [{"text": "📊 Estado", "callback_data": "cmd:status"}, {"text": "❓ Ayuda", "callback_data": "cmd:help"}]
        ]}
        self._send_message(chat_id, text, reply_markup=inline_keyboard)

    def _cmd_help(self, chat_id: str, args: str, message: Dict) -> None:
        text = (
            "❓ <b>Guía de Uso - AgentEagle 2.0</b>\n\n"
            "📄 <b>ANÁLISIS</b>\n"
            "<code>/doc</code> + archivo → OCR + IA (sin imprimir)\n\n"
            "🖨️ <b>IMPRESIÓN</b>\n"
            "<code>/print</code> + archivo → Imprime con IA\n"
            "  • Caption <code>2</code> → 2 copias\n"
            "  • Caption <code>3 finance</code> → 3 copias grupo finance\n\n"
            "🔄 <b>CONVERSIONES</b>\n"
            "<code>/pdf2word</code> + PDF → Convierte a Word\n"
            "<code>/word2pdf</code> + DOCX → Convierte a PDF\n"
            "<code>/smart_convert</code> + PDF → Reconstruye diseño (CVs)\n"
            "<code>/ocr</code> + imagen/PDF → Extrae texto\n\n"
            "📊 <b>SISTEMA</b>\n"
            "<code>/status</code> → Ver estado\n"
            "<code>/printers</code> → Lista impresoras"
        )
        self._send_message(chat_id, text)

    def _cmd_document_pipeline(self, chat_id: str, args: str, message: Dict) -> None:
        self.set_chat_mode(chat_id, 'analyze')
        text = (
            "🔍 <b>Modo Solo Análisis Activado</b>\n\n"
            "📥 Envía un archivo PDF/DOCX/PNG/JPG y el sistema:\n"
            "  1. Extraerá texto con OCR\n"
            "  2. Clasificará el documento con IA\n"
            "  3. Extraerá campos estructurados\n"
            "  4. Te enviará el análisis completo\n\n"
            "🚫 <i>Nota: No se realizará ninguna impresión.</i>\n"
            "💡 <i>Envía el archivo ahora...</i>"
        )
        self._send_message(chat_id, text)

    def _cmd_payment_pipeline(self, chat_id: str, args: str, message: Dict) -> None:
        self.set_chat_mode(chat_id, 'print')
        text = (
            "💰 <b>Modo Pago con Aprobación Activado</b>\n\n"
            "📥 Envía una factura y el sistema:\n"
            "  1. Procesará el documento\n"
            "  2. Te enviará botones para aprobar/rechazar el pago\n"
            "  3. Ejecutará el pago si apruebas\n\n"
            "💡 <i>Envía la factura ahora...</i>"
        )
        self._send_message(chat_id, text)

    def _cmd_smart_print(self, chat_id: str, args: str, message: Dict) -> None:
        self.set_chat_mode(chat_id, 'print')
        text = (
            "🖨️ <b>Modo Smart Print Activado</b>\n\n"
            "📥 Envía un archivo y el sistema:\n"
            "  1. Analizará el documento con IA\n"
            "  2. Decidirá si imprimir, cuántas copias, en qué impresora\n"
            "  3. Solicitará aprobación si es necesario\n"
            "  4. Imprimirá automáticamente\n\n"
            "📝 <b>Tip:</b> Puedes agregar instrucciones en el caption:\n"
            "  • <code>2</code> → 2 copias\n"
            "  • <code>3 finance</code> → 3 copias en grupo finance\n\n"
            "💡 <i>Envía el archivo ahora...</i>"
        )
        self._send_message(chat_id, text)

    def _cmd_status(self, chat_id: str, args: str, message: Dict) -> None:
        try:
            from services.llm_service import LLMService
            llm = LLMService()
            ollama_ok = llm.health_check()

            text = (
                "📊 <b>Estado del Sistema</b>\n\n"
                f"🤖 <b>Ollama:</b> {'✅ Disponible' if ollama_ok else ' No disponible'}\n"
                f" <b>Telegram:</b> ✅ Conectado\n"
                f"🖨️ <b>Impresión:</b> ✅ Activa\n"
                f"🧠 <b>IA:</b> ✅ Habilitada\n"
                f"🔄 <b>Conversiones:</b> ✅ PDF↔Word, OCR, Smart Layout\n"
                f"🔔 <b>Aprobaciones:</b> ✅ Interactivas\n\n"
                f"🕐 <b>Hora:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except Exception as e:
            text = f" Error obteniendo estado: {str(e)}"
        self._send_message(chat_id, text)

    def _cmd_printers(self, chat_id: str, args: str, message: Dict) -> None:
        try:
            from services.windows_print_service import WindowsPrintService
            from services.printer_manager import PrinterManager

            win_service = WindowsPrintService()
            printers = win_service.list_printers()
            default_printer = win_service.get_default_printer()

            manager = PrinterManager()
            groups = manager.get_all_groups()

            text = "🖨️ <b>Impresoras Disponibles</b>\n\n"
            text += "📋 <b>Impresoras del sistema:</b>\n"
            for p in printers:
                marker = " ⭐" if p == default_printer else ""
                text += f"  • {p}{marker}\n"
            text += f"\n🎯 <b>Predeterminada:</b> {default_printer or 'N/A'}\n"

            text += "\n🏷️ <b>Grupos configurados:</b>\n"
            for group in groups:
                printer = manager.get_printer_for_group(group)
                text += f"  • <b>{group}</b>: {printer}\n"
        except Exception as e:
            text = f"❌ Error listando impresoras: {str(e)}"
        self._send_message(chat_id, text)

    # ============================================================
    # COMANDOS DE CONVERSIÓN
    # ============================================================

    def _cmd_pdf_to_word(self, chat_id: str, args: str, message: Dict) -> None:
        self.set_chat_mode(chat_id, 'pdf2word')
        text = (
            "🔄 <b>Modo PDF → Word Activado</b>\n\n"
            "📥 Envía un archivo <b>PDF</b> y el sistema:\n"
            "  1. Convertirá el PDF a Word (DOCX)\n"
            "  2. Preservará formato, tablas e imágenes\n"
            "  3. Te enviará el archivo DOCX listo para editar\n\n"
            "💡 <i>Envía el PDF ahora...</i>"
        )
        self._send_message(chat_id, text)

    def _cmd_word_to_pdf(self, chat_id: str, args: str, message: Dict) -> None:
        self.set_chat_mode(chat_id, 'word2pdf')
        text = (
            "🔄 <b>Modo Word → PDF Activado</b>\n\n"
            "📥 Envía un archivo <b>Word (DOCX)</b> y el sistema:\n"
            "  1. Convertirá el DOCX a PDF\n"
            "  2. Preservará todo el formato original\n"
            "  3. Te enviará el archivo PDF listo para compartir\n\n"
            "💡 <i>Envía el DOCX ahora...</i>"
        )
        self._send_message(chat_id, text)

    def _cmd_ocr(self, chat_id: str, args: str, message: Dict) -> None:
        self.set_chat_mode(chat_id, 'ocr')
        text = (
            "🔍 <b>Modo OCR (Imagen → Texto) Activado</b>\n\n"
            "📥 Envía una <b>imagen</b> (PNG, JPG) o <b>PDF escaneado</b> y el sistema:\n"
            "  1. Extraerá todo el texto usando OCR\n"
            "  2. Soporta español e inglés\n"
            "  3. Te enviará el texto extraído\n\n"
            " <b>Formatos soportados:</b>\n"
            "  • Imágenes: PNG, JPG, JPEG, BMP, TIFF\n"
            "  • PDFs escaneados\n\n"
            "💡 <i>Envía la imagen o PDF ahora...</i>"
        )
        self._send_message(chat_id, text)

    def _cmd_smart_convert(self, chat_id: str, args: str, message: Dict) -> None:  # 🆕
        """Comando /smart_convert - Reconstruye el diseño lógico del PDF."""
        self.set_chat_mode(chat_id, 'smart_reconstruct')
        text = (
            "🧠 <b>Modo Smart Convert (Reconstrucción IA) Activado</b>\n\n"
            "📥 Envía un <b>PDF</b> (ideal para Hojas de Vida o documentos de 2 columnas) y el sistema:\n"
            "  1. Analizará las coordenadas de los bloques de texto\n"
            "  2. Separará la barra lateral del contenido principal\n"
            "  3. Generará un Word limpio, ordenado y sin texto mezclado\n\n"
            "💡 <i>Envía el PDF ahora...</i>"
        )
        self._send_message(chat_id, text)

    # ============================================================
    # UTILIDADES
    # ============================================================

    def _send_message(self, chat_id: str, text: str, reply_markup: Optional[Dict] = None) -> None:
        try:
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            if reply_markup:
                payload["reply_markup"] = reply_markup
            requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")