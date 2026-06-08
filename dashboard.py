# -*- coding: utf-8 -*-
# dashboard.py
"""AgentEagle - Dashboard Interactivo con Streamlit y Enrutamiento Inteligente."""

import streamlit as st
import requests
import time
import json
from datetime import datetime

# ============================================================================
# CONFIGURACIÓN DE PÁGINA
# ============================================================================

st.set_page_config(
    page_title="🦅 AgentEagle",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/DarkHama11/AgentEagle',
        'Report a bug': 'https://github.com/DarkHama11/AgentEagle/issues',
        'About': "🦅 AgentEagle v2.1 - Motor de búsqueda de ciberseguridad cloud"
    }
)

# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================

API_URL = "http://localhost:8000"
TIMEOUT_SECONDS = 120

# Estilos personalizados CSS
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1f77b4; text-align: center; }
    .sub-header { font-size: 1.2rem; color: #666; text-align: center; margin-bottom: 2rem; }
    .agent-badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 1rem; 
                   font-size: 0.85rem; font-weight: 600; margin: 0.25rem; }
    .badge-seguridad { background: #dc3545; color: white; }
    .badge-oficina { background: #28a745; color: white; }
    .badge-general { background: #007bff; color: white; }
    .badge-auto { background: #6f42c1; color: white; }
    .chat-user { text-align: right; background: #e3f2fd; padding: 0.75rem 1rem; 
                 border-radius: 1rem 1rem 0 1rem; margin: 0.5rem 0; }
    .chat-assistant { text-align: left; background: #f5f5f5; padding: 0.75rem 1rem; 
                      border-radius: 1rem 1rem 1rem 0; margin: 0.5rem 0; }
    .status-ok { color: #28a745; font-weight: bold; }
    .status-error { color: #dc3545; font-weight: bold; }
    .footer { text-align: center; padding: 1rem; color: #666; font-size: 0.85rem; 
              border-top: 1px solid #eee; margin-top: 2rem; }
    .stTextInput > div > div > input { font-size: 1.1rem; }
    .stButton > button { width: 100%; font-size: 1rem; padding: 0.75rem; }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# FUNCIONES DE API
# ============================================================================

def check_server_health() -> bool:
    """Verifica si el servidor API está disponible."""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        return response.status_code == 200 and response.json().get("status") == "healthy"
    except requests.exceptions.RequestException:
        return False


def get_available_agents() -> dict:
    """Obtiene información de los agentes disponibles."""
    try:
        response = requests.get(f"{API_URL}/agents", timeout=5)
        if response.ok:
            return response.json()
    except requests.exceptions.RequestException:
        pass
    return {}


def send_query(user_input: str, agent: str) -> dict:
    """
    Envía consulta al endpoint /chat y retorna respuesta estructurada.

    Args:
        user_input: Consulta del usuario
        agent: Agente a usar (auto, seguridad, oficina, general)

    Returns:
        dict: Respuesta de la API o dict de error
    """
    try:
        start = time.time()

        # ✅ FIX: Usar "user_input" (no "prompt") para coincidir con ChatRequest de api.py
        payload = {
            "user_input": user_input,  # ✅ Campo correcto
            "agent": agent,
            "user_id": "streamlit_user"
        }

        response = requests.post(
            f"{API_URL}/chat",
            json=payload,
            timeout=TIMEOUT_SECONDS,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )

        elapsed = time.time() - start

        if response.ok:
            result = response.json()
            result["execution_time_ms"] = round(elapsed * 1000, 2)
            return result
        else:
            error_detail = response.json().get("detail", "Error desconocido")
            return {
                "error": True,
                "status_code": response.status_code,
                "detail": error_detail,
                "response": f"⚠️ Error HTTP {response.status_code}: {error_detail}"
            }

    except requests.exceptions.Timeout:
        return {
            "error": True,
            "detail": "Timeout: El servidor tardó demasiado en responder",
            "response": "⏱️ Timeout: La consulta excedió el tiempo límite. Intenta nuevamente."
        }
    except requests.exceptions.ConnectionError:
        return {
            "error": True,
            "detail": "No se pudo conectar al servidor",
            "response": "🔌 Error de conexión: Verifica que el servidor API esté corriendo en localhost:8000"
        }
    except Exception as e:
        return {
            "error": True,
            "detail": str(e),
            "response": f"❌ Error inesperado: {type(e).__name__}"
        }


def format_response(response_data: dict) -> str:
    """Formatea la respuesta para mostrar en el chat."""
    if response_data.get("error"):
        return f"<span class='status-error'>{response_data.get('response', 'Error desconocido')}</span>"

    parts = []

    # Agente e intención
    agent = response_data.get("agent", "unknown")
    intent = response_data.get("intent", "unknown")
    agent_emoji = {"seguridad": "🔐", "oficina": "📊", "general": "🦅", "auto": "🤖"}.get(agent, "🤖")
    parts.append(f"<small>{agent_emoji} <strong>{agent.title()}</strong> • Intent: {intent}</small>")

    # Respuesta principal
    response = response_data.get("response", "")
    parts.append(f"<div style='margin: 0.5rem 0'>{response}</div>")

    # Metadata opcional
    metadata = response_data.get("metadata", {})
    if metadata:
        meta_parts = []
        if "model" in metadata:
            meta_parts.append(f"🤖 {metadata['model']}")
        if "web_search_used" in metadata and metadata["web_search_used"]:
            meta_parts.append("🔍 Web search")
        if "skills_used" in metadata:
            meta_parts.append("🔧 Skills")
        if meta_parts:
            parts.append(f"<small style='color: #666'>{' • '.join(meta_parts)}</small>")

    # Tiempo de ejecución
    exec_time = response_data.get("execution_time_ms", 0)
    if exec_time > 0:
        parts.append(f"<small style='color: #999'>⚡ {exec_time:.0f}ms</small>")

    return "\n".join(parts)


# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================

def main():
    """Función principal del dashboard."""

    # Header
    st.markdown("<h1 class='main-header'>🦅 AgentEagle++</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p class='sub-header'>☁️ Cloud Security + General Assistant<br>🔐 AWS/Azure/GCP • 📊 Office • 🦅 Cultura General • 🤖 Auto-Routing</p>",
        unsafe_allow_html=True)

    # Sidebar: Estado del sistema
    with st.sidebar:
        st.subheader("📡 Estado del Sistema")

        # Health check
        if check_server_health():
            st.success("✅ Servidor disponible")
            st.caption(f"🌐 {API_URL}")
        else:
            st.error("❌ Servidor no disponible")
            st.caption("Ejecuta: python main.py")
            st.info("💡 El servidor debe estar corriendo en localhost:8000")

        st.divider()

        # Selección de agente
        st.subheader("🤖 Seleccionar Agente")
        agent_options = {
            "🤖 Auto (Recomendado)": "auto",
            "🔐 Seguridad (Cloud)": "seguridad",
            "📊 Oficina (Office)": "oficina",
            "🦅 General (Cultura)": "general"
        }
        selected_label = st.selectbox("Elige un modo de asistencia:", list(agent_options.keys()))
        selected_agent = agent_options[selected_label]

        # Descripción del agente seleccionado
        agent_descriptions = {
            "auto": "💡 AgentEagle detectará automáticamente si tu pregunta es sobre cloud security, office o cultura general.",
            "seguridad": "🔐 Especialista en: AWS, Azure, GCP, CVE, MITRE ATT&CK, compliance (CIS/NIST), hardening.",
            "oficina": "📊 Experto en: Excel (fórmulas, VBA), Word, PowerPoint, Outlook, Office 365.",
            "general": "🦅 Asistente para: cultura general, historia, ciencia, deportes, actualidad, preguntas varias."
        }
        st.info(agent_descriptions.get(selected_agent, ""))

        st.divider()

        # Estadísticas rápidas (simuladas, se podrían obtener de la API)
        st.subheader("📈 Estadísticas")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Consultas", "0", delta=None)
        with col2:
            st.metric("Prom. tiempo", "—", delta=None)

        st.divider()

        # Preguntas rápidas
        st.subheader("⚡ Preguntas Rápidas")
        quick_questions = [
            ("¿Qué es un CVE?", "general"),
            ("Último CVE crítico de AWS", "seguridad"),
            ("Fórmula VLOOKUP en Excel", "oficina"),
            ("¿Cuándo juega el Barcelona?", "general"),
            ("Mejores prácticas para S3", "seguridad"),
            ("Crear tabla dinámica", "oficina"),
        ]
        for question, agent_hint in quick_questions:
            if st.button(f"💬 {question}", key=f"qq_{question}", use_container_width=True):
                st.session_state["quick_question"] = (question,
                                                      agent_hint if selected_agent == "auto" else selected_agent)

        st.divider()

        # Información adicional
        with st.expander("ℹ️ Acerca de AgentEagle"):
            st.markdown("""
            **🦅 AgentEagle v2.1**

            Motor de búsqueda especializado en ciberseguridad cloud con fine-tuning de LLMs.

            **Características:**
            - 🔍 SecuritySearch con cache determinista
            - 🤖 3 agentes especializados con enrutamiento inteligente
            - 🔧 Sistema de skills: aws_cli, cve_lookup, mitre_mapping, etc.
            - 📊 Dashboard interactivo con Streamlit
            - 🔄 Fine-tuning QLoRA para modelos locales

            **Requisitos:**
            - Python 3.12+
            - Ollama corriendo en localhost:11434
            - Modelo: llama3.2:3b (recomendado)

            [🔗 GitHub Repository](https://github.com/DarkHama11/AgentEagle)
            """)

    # Área principal: Chat
    st.markdown("### 💬 Chat con AgentEagle")

    # Inicializar estado del chat en session_state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "quick_question" not in st.session_state:
        st.session_state.quick_question = None

    # Procesar pregunta rápida si existe
    if st.session_state.quick_question:
        question, agent = st.session_state.quick_question
        st.session_state.quick_question = None  # Limpiar para no repetir
        st.session_state.messages.append({"role": "user", "content": question})

        with st.spinner("🤖 AgentEagle analizando..."):
            result = send_query(question, agent)
            st.session_state.messages.append({
                "role": "assistant",
                "content": format_response(result),
                "raw": result
            })
        st.rerun()

    # Mostrar historial de mensajes
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"<div class='chat-user'><strong>Tú:</strong><br>{msg['content']}</div>",
                        unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='chat-assistant'><strong>AgentEagle:</strong><br>{msg['content']}</div>",
                        unsafe_allow_html=True)

    # Input de usuario
    user_input = st.chat_input("Pregunta lo que quieras... AgentEagle elegirá el mejor agente 🤖")

    if user_input:
        # Agregar mensaje del usuario al historial
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.rerun()

    # Procesar respuesta del asistente (después de rerun)
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        with st.spinner("🤖 AgentEagle pensando..."):
            last_user_msg = st.session_state.messages[-1]["content"]
            result = send_query(last_user_msg, selected_agent)

            # Agregar respuesta al historial
            st.session_state.messages.append({
                "role": "assistant",
                "content": format_response(result),
                "raw": result
            })
            st.rerun()

    # Footer
    st.markdown("""
    <div class='footer'>
        © 2026 AgentEagle++ v2.1 • 🦅 Local + Web Search 🔐<br>
        <small>RTX 3050 (4GB VRAM) • Ollama • FastAPI • Streamlit</small>
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()