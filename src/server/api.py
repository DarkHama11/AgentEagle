# src/server/api.py
"""AgentEagle++ - API Server con FastAPI y Enrutamiento Inteligente de Agentes."""
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.core.config import Config
from src.core.model_wrapper import ModelWrapper
from src.agents.seguridad_agent import SeguridadAgent
from src.agents.oficina_agent import OficinaAgent
from src.agents.general_agent import GeneralAgent
from src.server.router import AgentRouter

# ==================== CONFIGURACIÓN DE LOGGING ====================
logger = logging.getLogger(__name__)


# ==================== MODELOS PYDANTIC ====================
class ChatRequest(BaseModel):
    """Solicitud de chat al agente."""
    prompt: str = Field(..., min_length=1, max_length=4000, description="Mensaje del usuario")
    agent: Optional[str] = Field(default="auto",
                                 description="Agente a usar: seguridad, oficina, general, o 'auto' para enrutamiento automático")
    user_id: Optional[str] = Field(default="anonymous", description="Identificador del usuario")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Contexto adicional para la conversación")


class ChatResponse(BaseModel):
    """Respuesta del agente."""

    # ✅ Fix para warning de Pydantic v2:
    model_config = {"protected_namespaces": ()}

    response: str = Field(..., description="Respuesta generada por el agente")
    agent: str = Field(..., description="Agente que procesó la solicitud")
    routed_agent: Optional[str] = Field(default=None, description="Agente real usado si fue enrutamiento automático")
    model_name: str = Field(..., description="Modelo utilizado para generar la respuesta")
    success: bool = Field(..., description="Indicador de éxito en el procesamiento")
    time_elapsed: Optional[float] = Field(default=None, description="Tiempo de procesamiento en segundos")
    tokens_used: Optional[int] = Field(default=None, description="Número aproximado de tokens usados")
    intent_detected: Optional[str] = Field(default=None, description="Intención detectada en el input del usuario")
    web_search_used: Optional[bool] = Field(default=False, description="Indicador si se usó búsqueda web")
    web_results_count: Optional[int] = Field(default=0, description="Número de resultados web obtenidos")
    web_search_category: Optional[str] = Field(default=None, description="Categoría de búsqueda web activada")
    error: Optional[str] = Field(default=None, description="Mensaje de error si success=False")


class HealthResponse(BaseModel):
    """Respuesta del endpoint de salud."""
    status: str = Field(..., description="Estado del servicio: 'ok' o 'error'")
    version: str = Field(..., description="Versión de AgentEagle++")
    model: str = Field(..., description="Modelo principal configurado")
    agents: Dict[str, bool] = Field(..., description="Estado de cada agente: True=ready, False=not ready")
    router_available: bool = Field(..., description="Indicador si el router está disponible")


class AgentsResponse(BaseModel):
    """Respuesta del endpoint de listagem de agentes."""
    agents: Dict[str, Dict[str, Any]] = Field(..., description="Lista de agentes disponibles con su estado")
    router_modes: list = Field(..., description="Modos de enrutamiento disponibles")


# ==================== ESTADO GLOBAL DE LA APLICACIÓN ====================
class AppState:
    """Contenedor para estado global de la aplicación."""

    def __init__(self):
        self.initialized: bool = False
        self.model_wrapper: Optional[ModelWrapper] = None
        self.agents: Dict[str, Any] = {}
        self.router: Optional[AgentRouter] = None


app_state = AppState()


# ==================== LIFESPAN MANAGER (Startup/Shutdown) ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación: startup y shutdown."""
    # === STARTUP ===
    logger.info("🚀 Iniciando AgentEagle++ API...")

    try:
        # 1. Inicializar model wrapper con el modelo por defecto
        logger.info(f"📦 Cargando modelo '{Config.DEFAULT_MODEL_KEY}'...")
        app_state.model_wrapper = ModelWrapper(model_key=Config.DEFAULT_MODEL_KEY).load()

        # 2. Inicializar agentes especializados
        logger.info("🤖 Inicializando agentes...")

        # Agente de Seguridad Cloud
        app_state.agents["seguridad"] = (
            SeguridadAgent(model_key=Config.DEFAULT_MODEL_KEY, enable_web_search=Config.ENABLE_WEB_SEARCH)
            .set_model(app_state.model_wrapper)
        )

        # Agente de Oficina
        app_state.agents["oficina"] = (
            OficinaAgent(model_key=Config.DEFAULT_MODEL_KEY)
            .set_model(app_state.model_wrapper)
        )

        # Agente Generalista
        app_state.agents["general"] = (
            GeneralAgent(model_key=Config.DEFAULT_MODEL_KEY)
            .set_model(app_state.model_wrapper)
        )

        # 3. Inicializar router inteligente
        logger.info("🧭 Inicializando AgentRouter...")
        app_state.router = AgentRouter(default_agent="general")

        # 4. Marcar como inicializado
        app_state.initialized = True
        logger.info("✅ AgentEagle++ API inicializado correctamente")

    except Exception as e:
        logger.error(f"❌ Error durante inicialización: {e}", exc_info=True)
        app_state.initialized = False
        raise

    yield  # ← La aplicación corre aquí

    # === SHUTDOWN ===
    logger.info("🔚 Cerrando AgentEagle++ API...")
    app_state.initialized = False
    logger.info("✅ AgentEagle++ API cerrado")


# ==================== INSTANCIAR FASTAPI ====================
app = FastAPI(
    title="AgentEagle++ API",
    description="API para asistentes de IA locales especializados en seguridad cloud, oficina y cultura general",
    version="2.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ==================== MIDDLEWARE ====================
# CORS: Permitir conexiones desde el dashboard Streamlit y otros orígenes
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== ENDPOINTS ====================

@app.get("/", tags=["Root"])
async def root():
    """Endpoint raíz con información básica del servicio."""
    return {
        "service": "AgentEagle++ API",
        "version": "2.1.0",
        "docs": "/docs",
        "health": "/health",
        "agents": "/agents",
        "chat": "/chat (POST)"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Verifica el estado de salud del servicio y sus componentes."""
    if not app_state.initialized:
        return HealthResponse(
            status="error",
            version="2.1.0",
            model=Config.MODELS.get(Config.DEFAULT_MODEL_KEY, {}).get("ollama_model", "unknown"),
            agents={},
            router_available=False
        )

    # Verificar estado de cada agente
    agents_status = {}
    for name, agent in app_state.agents.items():
        try:
            health = await agent.health_check()
            agents_status[name] = health.get("is_ready", False)
        except Exception as e:
            logger.warning(f"⚠️ Error verificando agente '{name}': {e}")
            agents_status[name] = False

    return HealthResponse(
        status="ok",
        version="2.1.0",
        model=Config.MODELS.get(Config.DEFAULT_MODEL_KEY, {}).get("ollama_model", "unknown"),
        agents=agents_status,
        router_available=app_state.router is not None
    )


@app.get("/agents", response_model=AgentsResponse, tags=["Agents"])
async def list_agents():
    """Lista los agentes disponibles y sus capacidades."""
    if not app_state.initialized:
        raise HTTPException(status_code=503, detail="Servicio no inicializado")

    agents_info = {}
    for name, agent in app_state.agents.items():
        try:
            health = await agent.health_check()
            agents_info[name] = {
                "name": agent.name,
                "ready": health.get("is_ready", False),
                "model": health.get("model_key", Config.DEFAULT_MODEL_KEY),
                "description": _get_agent_description(name)
            }
        except Exception as e:
            logger.warning(f"⚠️ Error obteniendo info de agente '{name}': {e}")
            agents_info[name] = {"name": name, "ready": False, "error": str(e)}

    return AgentsResponse(
        agents=agents_info,
        router_modes=["auto", "seguridad", "oficina", "general"]
    )


def _get_agent_description(agent_name: str) -> str:
    """Retorna descripción humana de cada agente."""
    descriptions = {
        "seguridad": "Especialista en seguridad cloud: AWS, Azure, GCP, CVEs, MITRE ATT&CK, compliance",
        "oficina": "Especialista en Microsoft Office: Excel, Word, PowerPoint, atajos, fórmulas",
        "general": "Asistente de cultura general: historia, ciencia, tecnología, explicaciones claras"
    }
    return descriptions.get(agent_name, "Agente especializado")


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Endpoint principal para interactuar con los agentes de AgentEagle++.

    Soporta enrutamiento automático: si agent="auto", el router decide
    qué agente especializado es más adecuado para la pregunta del usuario.
    """
    import time
    start_time = time.time()

    # === VALIDACIONES INICIALES ===

    # 1. Verificar que el servicio está inicializado
    if not app_state.initialized:
        logger.error("❌ Intento de chat con servicio no inicializado")
        raise HTTPException(status_code=503, detail="Servicio no disponible. Intenta más tarde.")

    # 2. Validar que el prompt no esté vacío
    if not request.prompt or not request.prompt.strip():
        raise HTTPException(status_code=400, detail="El prompt no puede estar vacío")

    # 3. Determinar qué agente usar (LÓGICA DE ENRUTAMIENTO)
    if request.agent == "auto" or not request.agent:
        # === MODO AUTO: Router decide automáticamente ===
        if not app_state.router:
            logger.warning("⚠️ Router no disponible, usando agente por defecto")
            target_agent = "general"
        else:
            target_agent = app_state.router.route(request.prompt)
            logger.info(f"🧭 Router seleccionó agente: '{target_agent}' para: '{request.prompt[:50]}...'")
        routed_agent = target_agent  # Guardar para respuesta
    else:
        # === MODO MANUAL: Usuario especificó agente ===
        target_agent = request.agent
        routed_agent = None  # No fue enrutado automáticamente
        logger.info(f"🧭 Agente especificado por usuario: '{target_agent}'")

    # 4. Validar que el agente objetivo existe y está listo
    if target_agent not in app_state.agents:
        available = list(app_state.agents.keys())
        logger.error(f"❌ Agente '{target_agent}' no encontrado. Disponibles: {available}")
        raise HTTPException(
            status_code=404,
            detail=f"Agente '{target_agent}' no encontrado. Disponibles: {', '.join(available)}"
        )

    agent = app_state.agents[target_agent]
    if not agent.is_ready():
        logger.error(f"❌ Agente '{target_agent}' no está listo")
        raise HTTPException(status_code=503, detail=f"Agente '{target_agent}' no disponible")

    # === PROCESAR CONSULTA CON EL AGENTE ===
    try:
        logger.info(f"💬 Procesando consulta con agente '{target_agent}': '{request.prompt[:80]}...'")

        # Ejecutar el agente (asíncrono)
        result = await agent.process(
            user_input=request.prompt,
            context=request.context or {}
        )

        elapsed_time = time.time() - start_time

        # === CONSTRUIR RESPUESTA ===
        response = ChatResponse(
            response=result.get("response", ""),
            agent=target_agent,
            routed_agent=routed_agent,
            model_name=result.get("model",
                                  Config.MODELS.get(Config.DEFAULT_MODEL_KEY, {}).get("ollama_model", "unknown")),
            success=result.get("success", False),
            time_elapsed=round(elapsed_time, 3),
            tokens_used=result.get("tokens_used"),
            intent_detected=result.get("intent_detected"),
            web_search_used=result.get("web_search_used", False),
            web_results_count=result.get("web_results_count", 0),
            web_search_category=result.get("web_search_category"),
            error=result.get("error") if not result.get("success") else None
        )

        # Logging de métricas
        logger.info(
            f"[{'✅' if response.success else '❌'}] {target_agent} | "
            f"user:{request.user_id} | "
            f"'{request.prompt[:40]}...' | "
            f"{response.time_elapsed:.2f}s | "
            f"{response.tokens_used or 0} tokens"
        )

        return response

    except HTTPException:
        # Re-lanzar excepciones HTTP para que FastAPI las maneje
        raise
    except Exception as e:
        # Capturar errores inesperados del agente
        logger.error(f"❌ Error procesando consulta con agente '{target_agent}': {e}", exc_info=True)
        elapsed_time = time.time() - start_time

        return ChatResponse(
            response=f"⚠️ Ocurrió un error interno procesando tu solicitud. Por favor intenta de nuevo.",
            agent=target_agent,
            routed_agent=routed_agent,
            model_name=Config.MODELS.get(Config.DEFAULT_MODEL_KEY, {}).get("ollama_model", "unknown"),
            success=False,
            time_elapsed=round(elapsed_time, 3),
            tokens_used=0,
            intent_detected=None,
            web_search_used=False,
            web_results_count=0,
            web_search_category=None,
            error=str(e)[:200]  # Limitar longitud del error
        )


# ==================== ENDPOINTS ADICIONALES (Opcionales) ====================

@app.get("/router/info", tags=["Router"])
async def router_info():
    """Información sobre el sistema de enrutamiento de agentes."""
    if not app_state.router:
        raise HTTPException(status_code=503, detail="Router no disponible")

    return {
        "default_agent": app_state.router.default_agent,
        "available_agents": app_state.router.get_available_agents(),
        "security_keywords_sample": app_state.router.SECURITY_KEYWORDS[:10],
        "office_keywords_sample": app_state.router.OFFICE_KEYWORDS[:10],
        "general_indicators_sample": app_state.router.GENERAL_INDICATORS[:10]
    }


@app.post("/router/test", tags=["Router"])
async def test_router(prompt: str):
    """
    Endpoint de prueba para ver a qué agente enrutaria el router una pregunta.
    Útil para debugging y desarrollo.
    """
    if not app_state.router:
        raise HTTPException(status_code=503, detail="Router no disponible")

    target_agent = app_state.router.route(prompt)
    return {
        "input": prompt,
        "routed_to": target_agent,
        "agent_description": _get_agent_description(target_agent)
    }


# ==================== MANEJO GLOBAL DE ERRORES ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Manejador global para excepciones HTTP."""
    logger.warning(f"⚠️ HTTP {exc.status_code}: {exc.detail} | {request.method} {request.url}")
    return {"detail": exc.detail}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    """Manejador global para excepciones no capturadas."""
    logger.error(f"❌ Error no capturado: {type(exc).__name__}: {exc} | {request.method} {request.url}", exc_info=True)
    return {"detail": "Error interno del servidor"}