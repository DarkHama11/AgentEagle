# -*- coding: utf-8 -*-
# src/server/api.py
"""AgentEagle - API Server con FastAPI y Enrutamiento Inteligente de Agentes."""

import logging
import time
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..core.config import Config
from ..core.model_wrapper import ModelWrapper
from .router import AgentRouter, RouteResult
from agents import SeguridadAgent
from agents.oficina_agent import OficinaAgent
from agents.general_agent import GeneralAgent

logger = logging.getLogger(__name__)


# ============================================================================
# MODELOS PYDANTIC
# ============================================================================

class ChatRequest(BaseModel):
    """Solicitud de chat para la API."""
    user_input: str = Field(..., min_length=1, max_length=4000, description="Consulta del usuario")
    agent: Optional[str] = Field(default="auto", description="Agente a usar: auto, seguridad, oficina, general")
    conversation_history: Optional[List[Dict[str, str]]] = Field(default=None, description="Historial de mensajes")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Opciones adicionales para el modelo")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Contexto adicional para la consulta")


class ChatResponse(BaseModel):
    """Respuesta de chat de la API."""
    agent: str
    intent: str
    response: str
    tokens_used: int
    execution_time_ms: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Respuesta de health check."""
    status: str = "healthy"
    version: str = Config.API_VERSION
    agents: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))


class AgentInfo(BaseModel):
    """Información de un agente."""
    name: str
    description: str
    ready: bool
    model: str
    trigger_keywords: List[str] = Field(default_factory=list)
    health: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# ESTADO DE LA APLICACIÓN
# ============================================================================

class AppState:
    """Estado compartido de la aplicación."""

    def __init__(self):
        self.model_wrapper: Optional[ModelWrapper] = None
        self.agents: Dict[str, Any] = {}
        self.router: Optional[AgentRouter] = None
        self.initialized: bool = False


app_state = AppState()


# ============================================================================
# LIFESPAN MANAGER
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manager de ciclo de vida de la aplicación."""
    logger.info("🚀 Iniciando AgentEagle++ API...")

    try:
        # Cargar modelo
        logger.info(f"📦 Cargando modelo '{Config.DEFAULT_MODEL_KEY}'...")
        app_state.model_wrapper = ModelWrapper(model_key=Config.DEFAULT_MODEL_KEY).load()

        # Inicializar agentes
        logger.info("🤖 Inicializando agentes...")

        # Agente de seguridad
        seguridad = SeguridadAgent(
            model_key=Config.DEFAULT_MODEL_KEY,
            enable_web_search=Config.ENABLE_WEB_SEARCH,
            enable_skills=Config.ENABLE_SKILLS
        )
        app_state.agents["seguridad"] = seguridad.set_model(app_state.model_wrapper)

        # Agente de oficina
        oficina = OficinaAgent(model_key=Config.DEFAULT_MODEL_KEY)
        app_state.agents["oficina"] = oficina.set_model(app_state.model_wrapper)

        # Agente general
        general = GeneralAgent(model_key=Config.DEFAULT_MODEL_KEY, enable_web_search=Config.ENABLE_WEB_SEARCH)
        app_state.agents["general"] = general.set_model(app_state.model_wrapper)

        # Inicializar router
        logger.info("🧭 Inicializando AgentRouter...")
        app_state.router = AgentRouter(agents=app_state.agents, default_agent="general")

        app_state.initialized = True
        logger.info("✅ AgentEagle++ API inicializado correctamente")

        yield  # Aplicación corriendo

    except Exception as e:
        logger.error(f"❌ Error durante inicialización: {e}")
        raise
    finally:
        # Cleanup al cerrar
        logger.info("🔚 Cerrando AgentEagle++ API...")
        app_state.initialized = False
        app_state.agents.clear()
        app_state.model_wrapper = None
        logger.info("✅ AgentEagle++ API cerrado")


# ============================================================================
# CONFIGURACIÓN DE FASTAPI
# ============================================================================

app = FastAPI(
    title=Config.API_TITLE,
    description="API para asistentes de IA locales especializados en seguridad cloud, oficina y cultura general",
    version=Config.API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=Config.CORS_CREDENTIALS,
    allow_methods=Config.CORS_METHODS,
    allow_headers=Config.CORS_HEADERS,
)


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Endpoint raíz con información de la API."""
    return {
        "service": "AgentEagle++ API",
        "version": Config.API_VERSION,
        "docs": "/docs",
        "health": "/health",
        "agents": "/agents",
        "chat": "/chat (POST)"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Verificar estado de salud de la API y agentes."""
    if not app_state.initialized:
        raise HTTPException(status_code=503, detail="API not initialized")

    agents_health = {}
    for name, agent in app_state.agents.items():
        try:
            # ✅ FIX: Sin await - health_check() es síncrono
            health = agent.health_check()
            agents_health[name] = health
        except Exception as e:
            logger.warning(f"⚠️ Error obteniendo info de agente '{name}': {e}")
            agents_health[name] = {"name": name, "ready": False, "error": str(e)}

    return HealthResponse(
        status="healthy",
        version=Config.API_VERSION,
        agents=agents_health,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S")
    )


@app.get("/agents", response_model=Dict[str, AgentInfo], tags=["Agents"])
async def list_agents():
    """Listar información de todos los agentes disponibles."""
    if not app_state.initialized:
        raise HTTPException(status_code=503, detail="API not initialized")

    result = {}
    for name, agent in app_state.agents.items():
        try:
            # ✅ FIX: Sin await - métodos son síncronos
            health = agent.health_check()
            result[name] = AgentInfo(
                name=agent.name,
                description=agent.description,
                ready=agent.is_ready(),
                model=agent.config.get("ollama_model", "unknown"),
                trigger_keywords=agent.trigger_keywords,
                health=health
            )
        except Exception as e:
            logger.warning(f"⚠️ Error obteniendo info de agente '{name}': {e}")
            result[name] = AgentInfo(
                name=name,
                description="Error loading agent",
                ready=False,
                model="unknown",
                health={"error": str(e)}
            )

    return result


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Endpoint principal para interactuar con los agentes de AgentEagle++.

    - **user_input**: Consulta del usuario (requerido)
    - **agent**: Agente a usar: auto, seguridad, oficina, general (default: auto)
    - **conversation_history**: Historial opcional de mensajes
    - **options**: Opciones adicionales para el modelo
    - **context**: Contexto adicional para la consulta

    Returns:
        ChatResponse: Respuesta estructurada del agente
    """
    if not app_state.initialized:
        raise HTTPException(status_code=503, detail="API not initialized")

    if not app_state.router:
        raise HTTPException(status_code=503, detail="Router not initialized")

    start_time = time.time()

    try:
        # Seleccionar agente
        route_result: RouteResult = app_state.router.route(
            query=request.user_input,
            preferred_agent=request.agent
        )

        agent_name = route_result.agent_name
        agent = app_state.agents.get(agent_name)

        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

        logger.info(f"🧭 Router seleccionó agente: '{agent_name}' para: '{request.user_input[:50]}...'")
        logger.info(f"💬 Procesando consulta con agente '{agent_name}': '{request.user_input[:50]}...'")

        # ✅ FIX: process() ahora acepta parametro 'context'
        result = await agent.process(
            user_input=request.user_input,
            conversation_history=request.conversation_history,
            options=request.options,
            context=request.context  # ✅ Nuevo parametro
        )

        execution_time = (time.time() - start_time) * 1000

        logger.info(
            f"[✅] {agent_name} | user:streamlit_user | '{request.user_input[:30]}...' | {execution_time:.0f}ms | {result.tokens_used} tokens")

        return ChatResponse(
            agent=result.agent,
            intent=result.intent,
            response=result.response,
            tokens_used=result.tokens_used,
            execution_time_ms=round(execution_time, 2),
            metadata=result.metadata,
            error=result.error
        )

    except HTTPException:
        raise
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(
            f"❌ Error procesando consulta con agente '{agent_name if 'agent_name' in locals() else 'unknown'}': {e}")

        return ChatResponse(
            agent="error",
            intent="error",
            response="Lo siento, ocurrió un error procesando tu consulta. Por favor intenta nuevamente.",
            tokens_used=0,
            execution_time_ms=round(execution_time, 2),
            metadata={"error_type": type(e).__name__},
            error=str(e)[:200]
        )


@app.get("/models", tags=["Models"])
async def list_models():
    """Listar modelos disponibles configurados."""
    return {
        "default": Config.DEFAULT_MODEL,
        "available": Config.MODELS_DISPONIBLES,
        "models": Config.MODELS
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handler global para excepciones no capturadas."""
    logger.error(f"❌ Error no capturado: {exc} | {request.method} {request.url}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)[:200] if Config.API_DEBUG else "An unexpected error occurred"
        }
    )


# ============================================================================
# EJECUCIÓN DIRECTA (para desarrollo)
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.server.api:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=Config.API_DEBUG,
        log_level=Config.LOG_LEVEL.lower()
    )