from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from services.model_manager import ModelManager

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=Dict[str, str])
async def get_models():
    """
    Obtiene todos los modelos configurados.

    Returns:
        Diccionario con configuración de modelos
    """
    try:
        manager = ModelManager()
        return manager.get_all_models()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=Dict[str, bool])
async def check_models_health():
    """
    Verifica la disponibilidad de todos los modelos en Ollama.

    Returns:
        Diccionario con disponibilidad de cada modelo
    """
    try:
        manager = ModelManager()
        availability = manager.validate_models()
        return availability
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload")
async def reload_models():
    """
    Recarga la configuración de modelos desde el archivo YAML.

    Returns:
        Mensaje de éxito
    """
    try:
        manager = ModelManager()
        manager.reload()
        return {"status": "success", "message": "Configuración recargada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_type}")
async def get_model_for_task(task_type: str):
    """
    Obtiene el modelo configurado para una tarea específica.

    Args:
        task_type: Tipo de tarea (classification, extraction, etc.)

    Returns:
        Nombre del modelo
    """
    try:
        manager = ModelManager()
        model = manager.get_model(task_type)
        return {"task_type": task_type, "model": model}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))