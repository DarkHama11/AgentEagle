import json
import re
import logging
from typing import Dict, Any, List
from datetime import datetime
from services.llm_service import LLMService
from services.model_manager import ModelManager

logger = logging.getLogger("AgentEagle.MessageTemplateService")


class MessageTemplateService:
    """Servicio de plantillas de mensajes para notificaciones."""

    def __init__(self, format_type: str = "HTML"):
        self.format_type = format_type
        logger.info(f"MessageTemplateService inicializado con formato: {format_type}")

    def format_document_processed(self, payload: Dict[str, Any]) -> str:
        """Plantilla para documento procesado exitosamente."""
        doc_type = payload.get('document_type', 'desconocido')
        confidence = payload.get('confidence', 0)
        job_id = payload.get('job_id', 'N/A')
        fields = payload.get('fields', {})
        processing_time = payload.get('processing_time', 0)

        type_icons = {
            'invoice': '🧾', 'receipt': '🧾', 'contract': '📜',
            'report': '📊', 'manual': '📖'
        }
        icon = type_icons.get(doc_type, '📄')

        message = f"""
{icon} <b>Documento Procesado Exitosamente</b>

📋 <b>Tipo:</b> {doc_type.upper()}
🎯 <b>Confianza:</b> {confidence:.1%}
⏱️ <b>Tiempo:</b> {processing_time:.2f}s
🆔 <b>Job ID:</b> <code>{job_id}</code>
"""

        if fields:
            message += "\n📦 <b>Campos Extraídos:</b>\n"
            for key, value in list(fields.items())[:5]:
                formatted_key = key.replace('_', ' ').title()
                message += f"  • <b>{formatted_key}:</b> {value}\n"

            if len(fields) > 5:
                message += f"  <i>... y {len(fields) - 5} campos más</i>\n"

        message += f"\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return message.strip()

    def format_document_failed(self, payload: Dict[str, Any]) -> str:
        """Plantilla para documento que falló en procesamiento."""
        job_id = payload.get('job_id', 'N/A')
        error = payload.get('error', 'Error desconocido')
        file_path = payload.get('file_path', 'N/A')
        step = payload.get('step', 'desconocido')

        message = f"""
❌ <b>Error en Procesamiento de Documento</b>

🆔 <b>Job ID:</b> <code>{job_id}</code>
📁 <b>Archivo:</b> {file_path}
⚠️ <b>Paso Fallido:</b> {step}
🔴 <b>Error:</b> {error}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return message.strip()

    def format_pipeline_completed(self, payload: Dict[str, Any]) -> str:
        """Plantilla para pipeline completado."""
        pipeline = payload.get('pipeline', 'desconocido')
        job_id = payload.get('job_id', 'N/A')

        message = f"""
✅ <b>Pipeline Completado</b>

🔄 <b>Pipeline:</b> {pipeline}
🆔 <b>Job ID:</b> <code>{job_id}</code>
📊 <b>Estado:</b> COMPLETADO

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return message.strip()

    def format_pipeline_failed(self, payload: Dict[str, Any]) -> str:
        """Plantilla para pipeline fallido."""
        pipeline = payload.get('pipeline', 'desconocido')
        job_id = payload.get('job_id', 'N/A')
        error = payload.get('error', 'Error desconocido')

        message = f"""
🚨 <b>Pipeline Fallido</b>

🔄 <b>Pipeline:</b> {pipeline}
🆔 <b>Job ID:</b> <code>{job_id}</code>
🔴 <b>Error:</b> {error}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return message.strip()

    def format_payment_completed(self, payload: Dict[str, Any]) -> str:
        """Plantilla para pago completado."""
        invoice_id = payload.get('invoice_id', 'N/A')
        amount = payload.get('amount', 0)
        status = payload.get('status', 'desconocido')

        message = f"""
💰 <b>Pago Completado</b>

🧾 <b>Factura:</b> {invoice_id}
💵 <b>Monto:</b> ${amount:,.2f}
✅ <b>Estado:</b> {status}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return message.strip()

    def format_payment_waiting_human(self, payload: Dict[str, Any]) -> str:
        """Plantilla para pago esperando aprobación humana."""
        invoice_id = payload.get('invoice_id', 'N/A')
        amount = payload.get('amount', 0)
        reason = payload.get('reason', 'Requiere aprobación manual')

        message = f"""
⏸️ <b>Pago Esperando Aprobación</b>

🧾 <b>Factura:</b> {invoice_id}
💵 <b>Monto:</b> ${amount:,.2f}
📝 <b>Razón:</b> {reason}

⚠️ <b>Acción requerida:</b> Revisar y aprobar manualmente

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return message.strip()

    def format_payment_failed(self, payload: Dict[str, Any]) -> str:
        """Plantilla para pago fallido."""
        invoice_id = payload.get('invoice_id', 'N/A')
        amount = payload.get('amount', 0)
        error = payload.get('error', 'Error desconocido')

        message = f"""
❌ <b>Pago Fallido</b>

🧾 <b>Factura:</b> {invoice_id}
💵 <b>Monto:</b> ${amount:,.2f}
🔴 <b>Error:</b> {error}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return message.strip()

    def format_approval_required(self, payload: Dict[str, Any]) -> str:
        """Plantilla para solicitud de aprobación requerida."""
        approval_id = payload.get('approval_id', 'N/A')
        job_id = payload.get('job_id', 'N/A')
        pipeline = payload.get('pipeline_name', 'desconocido')
        title = payload.get('title', 'Aprobación requerida')
        description = payload.get('description', '')
        expires_at = payload.get('expires_at', 'N/A')
        approval_payload = payload.get('payload', {})

        doc_type = approval_payload.get('document_type', 'N/A')
        amount = approval_payload.get('amount', 'N/A')
        supplier = approval_payload.get('supplier', 'N/A')

        message = f"""
⚠️ <b>Aprobación Requerida</b>

📋 <b>Título:</b> {title}
📝 <b>Descripción:</b> {description}

🔄 <b>Pipeline:</b> {pipeline}
🆔 <b>Job ID:</b> <code>{job_id}</code>
🔑 <b>Approval ID:</b> <code>{approval_id}</code>

📦 <b>Detalles:</b>
  • Tipo de documento: {doc_type}
  • Proveedor: {supplier}
  • Monto: {amount}

⏰ <b>Expira:</b> {expires_at}

💡 <b>Acciones:</b>
  • Aprobar: <code>/approve {approval_id}</code>
  • Rechazar: <code>/reject {approval_id}</code>

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return message.strip()

    def format_approval_resolved(self, payload: Dict[str, Any], approved: bool) -> str:
        """Plantilla para aprobación resuelta."""
        approval_id = payload.get('approval_id', 'N/A')
        job_id = payload.get('job_id', 'N/A')
        resolved_by = payload.get('resolved_by', 'sistema')
        notes = payload.get('notes', '')

        status_icon = "✅" if approved else "❌"
        status_text = "APROBADA" if approved else "RECHAZADA"

        message = f"""
{status_icon} <b>Aprobación {status_text}</b>

🔑 <b>Approval ID:</b> <code>{approval_id}</code>
🆔 <b>Job ID:</b> <code>{job_id}</code>
👤 <b>Resuelto por:</b> {resolved_by}
📝 <b>Notas:</b> {notes or 'Sin notas'}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return message.strip()

    def get_template(self, event_type: str) -> callable:
        """Obtiene la función de plantilla para un tipo de evento."""
        templates = {
            'document.processed': self.format_document_processed,
            'document.failed': self.format_document_failed,
            'pipeline.completed': self.format_pipeline_completed,
            'pipeline.failed': self.format_pipeline_failed,
            'payment.completed': self.format_payment_completed,
            'payment.waiting_human': self.format_payment_waiting_human,
            'payment.failed': self.format_payment_failed,
            'approval.required': self.format_approval_required,
            'approval.approved': lambda p: self.format_approval_resolved(p, approved=True),
            'approval.rejected': lambda p: self.format_approval_resolved(p, approved=False),
        }
        return templates.get(event_type, self._default_template)

    def _default_template(self, payload: Dict[str, Any]) -> str:
        """Plantilla por defecto para eventos no mapeados."""
        return f"""
🔔 <b>Notificación del Sistema</b>

📦 <b>Payload:</b>
<pre>{payload}</pre>

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""".strip()