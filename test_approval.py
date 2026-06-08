"""
Script de prueba interactiva para el sistema de aprobación humana.
Ejecuta el pipeline invoice_payment y permite aprobar/rechazar desde la terminal.
"""
import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator.orchestrator import Orchestrator
from orchestrator.dispatcher import Dispatcher
from orchestrator.state_manager import StateManager
from event_bus.in_memory_event_bus import InMemoryEventBus
from agents.registry import AgentRegistry
from agents.functional.document_agent import DocumentAgent
from agents.functional.notification_agent import NotificationAgent
from approval.approval_manager import ApprovalManager
from approval.approval_api import ApprovalAPI


def main():
    print("=" * 70)
    print("🧪 PRUEBA INTERACTIVA: Sistema de Aprobación Humana")
    print("=" * 70)

    # Inicializar componentes
    event_bus = InMemoryEventBus(max_workers=4)
    event_bus.start()

    state_manager = StateManager(state_dir="state")
    approval_manager = ApprovalManager(store_dir="approvals", event_bus=event_bus)
    approval_api = ApprovalAPI(approval_manager)

    registry = AgentRegistry(package_names=["agents.domain", "agents.functional"])
    registry.discover_agents()

    # Configurar agentes
    doc_agent = DocumentAgent(event_bus=event_bus, state_manager=state_manager)
    registry.set_agent_instance("document_agent", doc_agent)

    notification_agent = NotificationAgent(event_bus=event_bus, state_manager=state_manager)
    registry.set_agent_instance("notification_agent", notification_agent)

    dispatcher = Dispatcher(registry=registry)
    orchestrator = Orchestrator(
        pipelines_dir="pipelines",
        state_dir="state",
        logs_dir="logs",
        event_bus=event_bus,
        dispatcher=dispatcher,
        approval_manager=approval_manager
    )

    print("\n📋 Ejecutando pipeline 'invoice_payment'...")
    print("   El pipeline se PAUSARÁ en el paso de aprobación humana.\n")

    # Ejecutar pipeline en un hilo separado
    pipeline_result = {"state": None, "error": None}

    def run_pipeline():
        try:
            result = orchestrator.run_pipeline(
                pipeline_name="invoice_payment",
                payload={"file_path": "test_invoice.pdf"}
            )
            pipeline_result["state"] = result
        except Exception as e:
            pipeline_result["error"] = str(e)

    pipeline_thread = threading.Thread(target=run_pipeline)
    pipeline_thread.start()

    # Esperar a que el pipeline llegue al paso de aprobación
    print("⏳ Esperando a que el pipeline llegue al paso de aprobación...")
    time.sleep(20)  # Tiempo suficiente para OCR + clasificación + extracción

    # Listar aprobaciones pendientes
    pending = approval_manager.list_pending()

    if not pending:
        print("❌ No se encontraron aprobaciones pendientes.")
        if pipeline_result["error"]:
            print(f"   Error: {pipeline_result['error']}")
        event_bus.stop()
        return

    approval = pending[0]
    print("\n" + "=" * 70)
    print("🔔 APROBACIÓN REQUERIDA")
    print("=" * 70)
    print(f"Approval ID : {approval.approval_id}")
    print(f"Job ID      : {approval.job_id}")
    print(f"Pipeline    : {approval.pipeline_name}")
    print(f"Paso        : {approval.step_id}")
    print(f"Título      : {approval.title}")
    print(f"Descripción : {approval.description}")
    print(f"Expira      : {approval.expires_at}")
    print("=" * 70)

    # Revisar Telegram
    print("\n📱 Revisa tu Telegram. Deberías haber recibido una notificación.")

    # Menú interactivo
    while True:
        print("\n¿Qué deseas hacer?")
        print("  1. Aprobar la solicitud")
        print("  2. Rechazar la solicitud")
        print("  3. Ver detalles de la solicitud")
        print("  4. Salir sin decidir")

        choice = input("\nOpción (1-4): ").strip()

        if choice == "1":
            notes = input("Notas (opcional): ").strip()
            result = approval_api.approve(approval.approval_id, resolved_by="user_test", notes=notes)
            print(f"\n✅ Resultado: {result['message']}")
            break

        elif choice == "2":
            notes = input("Razón del rechazo (opcional): ").strip()
            result = approval_api.reject(approval.approval_id, resolved_by="user_test", notes=notes)
            print(f"\n❌ Resultado: {result['message']}")
            break

        elif choice == "3":
            details = approval_api.get_approval(approval.approval_id)
            print("\n" + "-" * 70)
            import json
            print(json.dumps(details, indent=2, ensure_ascii=False))
            print("-" * 70)

        elif choice == "4":
            print("\n⚠️ Saliendo sin decidir. El pipeline sigue pausado.")
            break

        else:
            print("❌ Opción inválida")

    # Esperar a que el pipeline termine
    print("\n⏳ Esperando a que el pipeline termine...")
    pipeline_thread.join(timeout=30)

    # Mostrar resultado final
    print("\n" + "=" * 70)
    print("📊 RESULTADO FINAL DEL PIPELINE")
    print("=" * 70)

    if pipeline_result["state"]:
        state = pipeline_result["state"]
        print(f"Job ID  : {state['job_id']}")
        print(f"Estado  : {state['status']}")
        print(f"Pasos   : {', '.join(state['completed_steps'])}")
    elif pipeline_result["error"]:
        print(f"❌ Error: {pipeline_result['error']}")

    print("=" * 70)

    event_bus.stop()
    print("\n✅ Prueba completada")


if __name__ == "__main__":
    main()