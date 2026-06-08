"""
Módulo de endpoints para la API de aprobaciones.
Preparado para integrarse con FastAPI en la Fase 6.

Endpoints:
  GET  /approvals                      → Lista todas las solicitudes
  GET  /approvals/pending              → Lista solo las pendientes
  GET  /approvals/{approval_id}        → Detalle de una solicitud
  POST /approvals/{approval_id}/approve → Aprobar solicitud
  POST /approvals/{approval_id}/reject  → Rechazar solicitud
"""

from typing import Dict, Any, List, Optional
from .approval_manager import ApprovalManager
from .approval_request import ApprovalRequest, ApprovalStatus


class ApprovalAPI:
    """
    Capa de API para operaciones de aprobación.
    Diseñada para ser envuelta por FastAPI routers.
    """

    def __init__(self, approval_manager: ApprovalManager):
        self.manager = approval_manager

    def list_approvals(self, status: Optional[str] = None) -> Dict[str, Any]:
        """GET /approvals"""
        try:
            requests = self.manager.list_all(status_filter=status)
            return {
                "status": "success",
                "count": len(requests),
                "approvals": [r.to_dict() for r in requests]
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def list_pending(self) -> Dict[str, Any]:
        """GET /approvals/pending"""
        try:
            requests = self.manager.list_pending()
            return {
                "status": "success",
                "count": len(requests),
                "approvals": [r.to_dict() for r in requests]
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_approval(self, approval_id: str) -> Dict[str, Any]:
        """GET /approvals/{approval_id}"""
        request = self.manager.get_request(approval_id)
        if not request:
            return {"status": "error", "error": f"Solicitud no encontrada: {approval_id}"}
        return {"status": "success", "approval": request.to_dict()}

    def approve(self, approval_id: str, resolved_by: str = "user", notes: str = "") -> Dict[str, Any]:
        """POST /approvals/{approval_id}/approve"""
        try:
            request = self.manager.approve(approval_id, resolved_by=resolved_by, notes=notes)
            return {
                "status": "success",
                "message": "Solicitud aprobada exitosamente",
                "approval": request.to_dict()
            }
        except ValueError as e:
            return {"status": "error", "error": str(e)}
        except Exception as e:
            return {"status": "error", "error": f"Error inesperado: {str(e)}"}

    def reject(self, approval_id: str, resolved_by: str = "user", notes: str = "") -> Dict[str, Any]:
        """POST /approvals/{approval_id}/reject"""
        try:
            request = self.manager.reject(approval_id, resolved_by=resolved_by, notes=notes)
            return {
                "status": "success",
                "message": "Solicitud rechazada exitosamente",
                "approval": request.to_dict()
            }
        except ValueError as e:
            return {"status": "error", "error": str(e)}
        except Exception as e:
            return {"status": "error", "error": f"Error inesperado: {str(e)}"}