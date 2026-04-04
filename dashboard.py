# dashboard.py
"""AgentEagle++ - Dashboard Interactivo con Streamlit y Enrutamiento Inteligente."""
import streamlit as st
import requests
import time
from datetime import datetime

# ==================== CONFIGURACIÓN ====================
st.set_page_config(
    page_title="🦞 AgentEagle++",
    page_icon="🦞",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_URL = "http://127.0.0.1:8000"

# ==================== ESTILOS CSS ====================
st.markdown("""
<style>
    .stChatMessage { padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.5rem; }
    .agent-badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.85rem; font-weight: 500; margin-bottom: 0.5rem; }
    .agent-seguridad { background: #dbeafe; color: #1e40af; }
    .agent-oficina { background: #dcfce7; color: #166534; }
    .agent-general { background: #fef3c7; color: #92400e; }
    .agent-auto { background: #e0e7ff; color: #3730a3; }
    .thinking-box { background: #f0f4f8; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #0366d6; }
    .web-search-badge { background: #fef3c7; color: #92400e; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; font-weight: 600; display: inline-block; margin: 0.25rem 0; }
    .category-badge-cve { background: #fee2e2; color: #991b1b; }
    .category-badge-mitre { background: #ede9fe; color: #5b21b6; }
    .category-badge-aws { background: #ffedd5; color: #9a3412; }
    .category-badge-azure { background: #dbeafe; color: #1e40af; }
    .category-badge-gcp { background: #d1fae5; color: #065f46; }
    .category-badge-compliance { background: #f3e8ff; color: #6b21a8; }
    .category-badge-news { background: #fef9c3; color: #854d0e; }
    .category-badge-zero_day { background: #fecaca; color: #b91c1c; }
    .AgentEagle-brand { font-size: 1.2rem; font-weight: bold; color: #0366d6; }
    .router-badge { background: #e0f2fe; color: #0369a1; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ==================== INICIALIZACIÓN DE SESSION STATE ====================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "total_queries" not in st.session_state:
    st.session_state.total_queries = 0
if "total_time" not in st.session_state:
    st.session_state.total_time = 0
if "current_agent" not in st.session_state:
    st.session_state.current_agent = "auto"  # Default: modo auto
if "last_agent_used" not in st.session_state:
    st.session_state.last_agent_used = None


# ==================== FUNCIONES ====================
def check_server():
    """Verifica conexión con el servidor AgentEagle++"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=3)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def get_available_agents():
    """Obtiene lista de agentes disponibles desde la API"""
    try:
        response = requests.get(f"{API_URL}/agents", timeout=3)
        if response.status_code == 200:
            data = response.json()
            return data.get("agents", {})
    except:
        pass
    return {"seguridad": {"ready": True}, "oficina": {"ready": True}, "general": {"ready": True}}


def send_query(prompt: str, agent: str):
    """Envía consulta al endpoint /chat y retorna respuesta estructurada"""
    try:
        start = time.time()
        payload = {"prompt": prompt, "agent": agent, "user_id": "streamlit_user"}
        response = requests.post(
            f"{API_URL}/chat",
            json=payload,
            timeout=120,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        elapsed = time.time() - start

        if response.status_code == 200:
            data = response.json()
            return {
                "success": data.get("success", False),
                "response": data.get("response", ""),
                "time": elapsed,
                "model": data.get("model_name", "desconocido"),
                "tokens": data.get("tokens_used", 0),
                "agent": data.get("agent", agent),
                "web_search_used": data.get("web_search_used", False),
                "web_results_count": data.get("web_results_count", 0),
                "web_search_category": data.get("web_search_category"),
                "intent_detected": data.get("intent_detected", "question"),
                "routed_agent": data.get("routed_agent")  # Agente real usado si fue "auto"
            }
        else:
            error_detail = response.json().get("detail", "Error desconocido") if response.content else "Sin respuesta"
            return {"success": False, "error": f"HTTP {response.status_code}: {error_detail}"}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "⏱️ Timeout: excedió 120 segundos"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "🔌 No se pudo conectar. ¿Está corriendo `python main.py`?"}
    except Exception as e:
        return {"success": False, "error": f"❌ Error: {str(e)}"}


def get_agent_display_info(agent_key: str) -> dict:
    """Retorna información de visualización para un agente."""
    info = {
        "seguridad": {"icon": "🔐", "label": "Seguridad Cloud", "class": "agent-seguridad",
                      "desc": "AWS • Azure • GCP • CVEs • MITRE"},
        "oficina": {"icon": "📊", "label": "Oficina", "class": "agent-oficina",
                    "desc": "Excel • Word • PowerPoint • Atajos"},
        "general": {"icon": "🦞", "label": "Preguntas Generales", "class": "agent-general",
                    "desc": "Cultura • Historia • Ciencia • Tecnología"},
        "auto": {"icon": "🤖", "label": "Auto (Recomendado)", "class": "agent-auto",
                 "desc": "AgentEagle elige el agente más adecuado"},
    }
    return info.get(agent_key, {"icon": "❓", "label": agent_key, "class": "", "desc": ""})


# ==================== SIDEBAR ====================
with st.sidebar:
    st.markdown('<p class="AgentEagle-brand">🦞 AgentEagle++</p>', unsafe_allow_html=True)
    st.subheader("☁️ Cloud Security + General Assistant")
    st.caption("🔐 AWS/Azure/GCP • 📊 Office • 🦞 Cultura General • 🤖 Auto-Routing")
    st.markdown("---")

    # 🔍 Estado del servidor
    st.subheader("📡 Estado del Sistema")
    server_info = check_server()

    if server_info and server_info.get("status") == "ok":
        st.success("✅ Servidor conectado")
        st.info(f"🤖 Modelo: **{server_info.get('version', '1.0.0')}**")

        agents_status = server_info.get("agents", {})
        for agent_name, is_ready in agents_status.items():
            agent_info = get_agent_display_info(agent_name)
            status = "✅" if is_ready else "⏳"
            st.caption(f"{agent_info['icon']} {agent_info['label']}: {status}")
    else:
        st.error("❌ Servidor no disponible")
        st.code("python main.py", language="bash")

    st.markdown("---")

    # 🎛️ Selector de agente con modo Auto
    st.subheader("🤖 Seleccionar Agente")
    available_agents = get_available_agents()

    agent_options = {
        "🤖 Auto (Recomendado)": "auto",
        "🔐 Seguridad Cloud": "seguridad",
        "📊 Oficina (Excel/Word)": "oficina",
        "🦞 Preguntas Generales": "general",
    }

    # Filtrar opciones por agentes disponibles
    valid_options = {label: key for label, key in agent_options.items() if key in available_agents or key == "auto"}

    selected_label = st.selectbox(
        "Elige un modo de asistencia:",
        options=list(valid_options.keys()),
        index=0,  # Default: Auto
        key="agent_selector"
    )
    st.session_state.current_agent = valid_options[selected_label]

    # Mostrar badge del agente seleccionado
    agent_info = get_agent_display_info(st.session_state.current_agent)
    st.markdown(f'<span class="agent-badge {agent_info["class"]}">{agent_info["icon"]} {agent_info["label"]}</span>',
                unsafe_allow_html=True)

    # Descripción contextual
    if st.session_state.current_agent == "auto":
        st.caption(
            "💡 AgentEagle detectará automáticamente si tu pregunta es sobre cloud security, office o cultura general.")
    else:
        st.caption(f"📌 {agent_info['desc']}")

    st.markdown("---")

    # 📊 Estadísticas de sesión
    st.subheader("📈 Estadísticas")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Consultas", st.session_state.total_queries)
    with col2:
        if st.session_state.total_queries > 0:
            avg = st.session_state.total_time / st.session_state.total_queries
            st.metric("Prom. tiempo", f"{avg:.1f}s")
        else:
            st.metric("Prom. tiempo", "—")

    # Mostrar último agente usado si fue modo auto
    if st.session_state.last_agent_used and st.session_state.current_agent == "auto":
        last_info = get_agent_display_info(st.session_state.last_agent_used)
        st.caption(f"🧭 Último: {last_info['icon']} {last_info['label']}")

    st.markdown("---")

    # ⚡ Preguntas rápidas (context-aware)
    st.subheader("⚡ Preguntas Rápidas")

    # Definir preguntas según agente seleccionado
    if st.session_state.current_agent == "seguridad":
        preguntas = [
            "¿Cuál es el último CVE crítico?",
            "CVE-2024-6387",
            "¿Qué es la técnica T1059 de MITRE?",
            "¿Cómo proteger un bucket S3 en AWS?",
            "¿Qué es AWS EKS?",
            "Diferencia entre EKS y ECS",
            "¿Cómo configurar MFA en IAM?"
        ]
    elif st.session_state.current_agent == "oficina":
        preguntas = [
            "¿Cómo hacer una suma en Excel?",
            "¿Cómo crear una tabla dinámica?",
            "Atajos de teclado en Word",
            "¿Cómo proteger una hoja en Excel?",
            "¿Cómo insertar un gráfico en PowerPoint?"
        ]
    elif st.session_state.current_agent == "general":
        preguntas = [
            "¿Qué es Microsoft Word?",
            "¿Quién inventó la bombilla?",
            "¿Cuál es la capital de Francia?",
            "¿Qué es Kubernetes?",
            "¿Cómo funciona la inteligencia artificial?"
        ]
    else:  # auto
        preguntas = [
            "¿Qué es AWS EKS?",
            "¿Qué es Word?",
            "¿Quién inventó la bombilla?",
            "¿Cómo proteger un bucket S3?",
            "¿Cuál es la capital de Japón?"
        ]

    for pregunta in preguntas:
        if st.button(pregunta, use_container_width=True, key=f"q_{pregunta[:20]}"):
            st.session_state.messages.append({"role": "user", "content": pregunta})
            st.rerun()

    st.markdown("---")

    if st.button("🗑️ Limpiar historial", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.session_state.total_queries = 0
        st.session_state.total_time = 0
        st.session_state.last_agent_used = None
        st.rerun()

    st.caption("© 2026 AgentEagle++ v2.1 • 🦞 Local + Web Search 🔐")

# ==================== ÁREA PRINCIPAL ====================
st.title("🦞 AgentEagle++")

# Header dinámico según agente
agent_info = get_agent_display_info(st.session_state.current_agent)
st.markdown(f"### {agent_info['icon']} {agent_info['label']}")

# Subheader contextual
if st.session_state.current_agent == "auto":
    st.caption("Asistente inteligente • Cloud Security • Office • Cultura General • Enrutamiento automático 🤖")
elif st.session_state.current_agent == "seguridad":
    st.caption("Especialista en seguridad cloud • AWS • Azure • GCP • CVEs • MITRE • Respuestas locales 🔐")
elif st.session_state.current_agent == "oficina":
    st.caption("Especialista en Microsoft Office • Excel • Word • PowerPoint • Atajos • Fórmulas 📊")
else:  # general
    st.caption("Asistente de cultura general • Historia • Ciencia • Tecnología • Explicaciones claras 🦞")

st.markdown("---")

# 🗨️ Contenedor de chat
with st.container():
    # Mostrar historial de mensajes
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and "agent" in message:
                agent_key = message.get("agent", "general")
                agent_info_msg = get_agent_display_info(agent_key)
                # Si fue enrutado automáticamente, mostrar ambos
                routed = message.get("routed_agent")
                if routed and routed != agent_key:
                    routed_info = get_agent_display_info(routed)
                    st.markdown(
                        f"<span style='font-size:0.85rem; color:#666'>{agent_info_msg['icon']} {agent_key.title()} → {routed_info['icon']} {routed.title()} (auto)</span>",
                        unsafe_allow_html=True)
                else:
                    st.markdown(
                        f"<span style='font-size:0.9rem; color:#666'>{agent_info_msg['icon']} {agent_key.title()}</span>",
                        unsafe_allow_html=True)
            st.markdown(message["content"])

    # 📝 Input del usuario
    placeholder_text = {
        "auto": "Pregunta lo que quieras... AgentEagle elegirá el mejor agente 🤖",
        "seguridad": "Pregunta sobre AWS, Azure, GCP, seguridad cloud, CVEs, MITRE... 🔐",
        "oficina": "Pregunta sobre Excel, Word, PowerPoint, atajos, fórmulas... 📊",
        "general": "Pregunta sobre cualquier tema: historia, ciencia, tecnología, cultura... 🦞",
    }

    if prompt := st.chat_input(placeholder_text.get(st.session_state.current_agent, "Pregunta...")):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.total_queries += 1

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            # === INDICADOR DE "PENSANDO" ===
            thinking_placeholder = st.empty()
            with thinking_placeholder:
                if st.session_state.current_agent == "auto":
                    st.markdown("""
                    <div class="thinking-box">
                        <strong>🤖 AgentEagle analizando tu consulta...</strong><br>
                        <small>🧭 Detectando tema • 🦞 Preparando respuesta (5-20s)</small>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    agent_icon = get_agent_display_info(st.session_state.current_agent)["icon"]
                    st.markdown(f"""
                    <div class="thinking-box">
                        <strong>{agent_icon} {get_agent_display_info(st.session_state.current_agent)['label']} pensando...</strong><br>
                        <small>⏱️ llama3.2:3b procesando (5-20s en hardware local)</small>
                    </div>
                    """, unsafe_allow_html=True)

            # Ejecutar consulta
            result = send_query(prompt, st.session_state.current_agent)
            thinking_placeholder.empty()

            if result.get("success"):
                respuesta = result["response"]
                tiempo = result["time"]
                modelo = result.get("model", "desconocido")
                tokens = result.get("tokens", 0)
                agent_used = result.get("agent")
                routed_agent = result.get("routed_agent")

                # Actualizar último agente usado si fue modo auto
                if st.session_state.current_agent == "auto" and routed_agent:
                    st.session_state.last_agent_used = routed_agent

                # Mostrar respuesta
                st.markdown(respuesta)

                # === INDICADOR DE ENRUTAMIENTO (si fue modo auto) ===
                if st.session_state.current_agent == "auto" and routed_agent and routed_agent != agent_used:
                    routed_info = get_agent_display_info(routed_agent)
                    st.markdown(
                        f'<span class="router-badge">🧭 Enrutado a: {routed_info["icon"]} {routed_info["label"]}</span>',
                        unsafe_allow_html=True)

                # === INDICADOR DE BÚSQUEDA WEB ===
                if result.get("web_search_used"):
                    category = result.get("web_search_category", "security")
                    category_badges = {
                        "cve": ("🔐 CVE", "category-badge-cve"),
                        "cve_recent": ("🔐 CVEs Recientes", "category-badge-cve"),
                        "mitre": ("🎯 MITRE ATT&CK", "category-badge-mitre"),
                        "aws": ("☁️ AWS Security", "category-badge-aws"),
                        "azure": ("☁️ Azure Security", "category-badge-azure"),
                        "gcp": ("☁️ GCP Security", "category-badge-gcp"),
                        "compliance_cis": ("📋 CIS Benchmark", "category-badge-compliance"),
                        "compliance_nist": ("📋 NIST Framework", "category-badge-compliance"),
                        "compliance_iso": ("📋 ISO 27001", "category-badge-compliance"),
                        "news": ("📰 Noticias Seguridad", "category-badge-news"),
                        "zero_day": ("🚨 Zero-Day", "category-badge-zero_day"),
                        "general_security": ("🔍 Seguridad General", ""),
                        "general": ("🦞 Información General", ""),
                    }
                    badge_text, badge_class = category_badges.get(category, ("🔍 Web Search", ""))
                    st.success(
                        f"🔍 **Búsqueda activada**: {badge_text} ({result.get('web_results_count', 0)} resultados)")
                    st.caption("ℹ️ La respuesta incluye información actualizada de fuentes oficiales")
                    if badge_class:
                        st.markdown(f'<span class="web-search-badge {badge_class}">{badge_text}</span>',
                                    unsafe_allow_html=True)
                elif result.get("fast_response"):
                    st.info("⚡ **Respuesta rápida** (sin búsqueda web)")

                # === DETALLES TÉCNICOS ===
                with st.expander("📊 Detalles técnicos", expanded=False):
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("⏱️ Tiempo", f"{tiempo:.2f}s")
                    col_b.metric("🪙 Tokens", tokens)
                    col_c.metric("🤖 Modelo", modelo.split(":")[0] if ":" in modelo else modelo)

                    # Mostrar intención detectada
                    if "intent_detected" in result:
                        intent_emoji = {
                            "greeting": "👋", "goodbye": "👋", "thanks": "😊",
                            "question": "🔍", "date": "📅", "out_of_scope": "🦞"
                        }.get(result["intent_detected"], "❓")
                        st.caption(f"{intent_emoji} Intención: {result['intent_detected']}")

                    # Mostrar agente usado (especialmente útil en modo auto)
                    if agent_used:
                        agent_used_info = get_agent_display_info(agent_used)
                        st.caption(f"🤖 Agente: {agent_used_info['icon']} {agent_used_info['label']}")

                    # Mostrar categoría de búsqueda si aplica
                    if result.get("web_search_category"):
                        category = result["web_search_category"]
                        category_names = {
                            "cve": "CVE específico", "cve_recent": "CVEs recientes",
                            "mitre": "MITRE ATT&CK", "aws": "AWS Security",
                            "azure": "Azure Security", "gcp": "GCP Security",
                            "compliance_cis": "CIS Benchmark", "compliance_nist": "NIST",
                            "compliance_iso": "ISO 27001", "news": "Noticias",
                            "zero_day": "Zero-Day", "general_security": "Seguridad General",
                            "general": "Búsqueda General"
                        }
                        st.caption(f"🔍 Categoría: {category_names.get(category, category)}")

                # Actualizar estadísticas y guardar en historial
                st.session_state.total_time += tiempo
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": respuesta,
                    "agent": agent_used,
                    "routed_agent": routed_agent,
                    "metadata": result
                })

            else:
                error_msg = result.get("error", "Error desconocido")
                st.error(f"🦞 {error_msg}")

                if "Timeout" in error_msg:
                    st.info("💡 Tip: Intenta con preguntas más específicas o reduce la complejidad.")
                elif "conectar" in error_msg:
                    st.info("💡 Tip: Verifica que `python main.py` esté corriendo en otra terminal.")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"⚠️ {error_msg}"
                })

# ==================== FOOTER ====================
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    if st.session_state.current_agent == "auto":
        st.caption("🤖 **AgentEagle Auto** • Enrutamiento inteligente + Local 🔐")
    else:
        st.caption(f"{agent_info['icon']} **AgentEagle {agent_info['label']}** • Local + Web Search 🔐")
with col2:
    st.caption(f"🕒 {datetime.now().strftime('%H:%M:%S')}")
with col3:
    if st.session_state.current_agent == "auto" and st.session_state.last_agent_used:
        last_info = get_agent_display_info(st.session_state.last_agent_used)
        st.caption(f"🧭 Activo: {last_info['icon']} {last_info['label']}")
    else:
        st.caption(f"{agent_info['icon']} **{agent_info['label']}**")