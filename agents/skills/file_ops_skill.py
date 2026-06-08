# src/agents/skills/file_ops_skill.py
"""AgentEagle++ - Skill para operaciones de archivos locales con seguridad."""
from .base_skill import BaseSkill, SkillExecutionError
from typing import Dict, Any, Optional, List
import logging
import os
import json
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class FileOpsSkill(BaseSkill):
    """
    Skill para operaciones de archivos locales con sandboxing.

    ⚠️ Diseñado para seguridad: solo directorios permitidos (whitelist)
    ✅ Ideal para: leer configs, exportar reportes, guardar resultados
    ❌ No permite: acceder a archivos del sistema, directorios protegidos
    """

    name = "file_ops"
    description = "Operaciones seguras de archivos locales (leer/escribir/listar) con sandboxing"
    version = "1.0.0"
    category = "file"

    # === Operaciones permitidas ===
    ALLOWED_OPERATIONS = ["read", "write", "list", "exists", "delete"]

    # === Extensiones permitidas (por seguridad) ===
    ALLOWED_EXTENSIONS = [".txt", ".json", ".csv", ".md", ".log", ".yaml", ".yml", ".xml", ".html"]

    # === Extensiones PROHIBIDAS ===
    FORBIDDEN_EXTENSIONS = [".exe", ".bat", ".cmd", ".ps1", ".sh", ".dll", ".so", ".py", ".js", ".vbs"]

    parameters = {
        "operation": {
            "type": str,
            "description": "Operación a realizar: read, write, list, exists, delete",
            "required": True,
            "enum": ["read", "write", "list", "exists", "delete"]
        },
        "file_path": {
            "type": str,
            "description": "Ruta del archivo o directorio (relativa a allowed_paths)",
            "required": True,
            "example": "reports/security_report.json"
        },
        "content": {
            "type": str,
            "description": "Contenido a escribir (solo para operación 'write')",
            "required": False,
            "example": "Datos a guardar..."
        },
        "encoding": {
            "type": str,
            "description": "Codificación del archivo",
            "required": False,
            "enum": ["utf-8", "latin-1", "ascii"],
            "default": "utf-8"
        },
    }

    required_permissions = ["file_read", "file_write"]
    default_timeout = 15

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        # === Directorios permitidos (sandbox) ===
        self.allowed_paths = config.get("allowed_paths", [
            "./data",
            "./exports",
            "./reports",
            "./logs"
        ]) if config else ["./data", "./exports", "./reports", "./logs"]

        # === Tamaño máximo de archivo (por seguridad) ===
        self.max_file_size = config.get("max_file_size", 10 * 1024 * 1024) if config else 10 * 1024 * 1024  # 10MB

        self._initialized = True
        logger.info("✅ FileOpsSkill inicializada (paths permitidos: " + str(self.allowed_paths) + ")")

    def _validate_path(self, file_path: str) -> tuple:
        """
        Valida que la ruta está dentro de los directorios permitidos.

        Returns:
            tuple: (is_valid: bool, reason: str, full_path: str)
        """
        # Normalizar ruta
        file_path = file_path.replace("\\", "/").strip()

        # Verificar que no intente salir del sandbox
        if ".." in file_path:
            return False, "Ruta inválida: no se permite '..' para salir del directorio permitido", None

        # Verificar extensión
        file_ext = Path(file_path).suffix.lower()
        if file_ext in self.FORBIDDEN_EXTENSIONS:
            return False, "Extensión prohibida: " + file_ext, None

        if file_ext and file_ext not in self.ALLOWED_EXTENSIONS:
            logger.warning("⚠️ Extensión no común: " + file_ext + " (permitida pero verificar)")

        # Construir ruta completa y verificar que está dentro de allowed_paths
        for allowed_path in self.allowed_paths:
            allowed_full = Path(allowed_path).resolve()
            target_full = (allowed_full / file_path).resolve()

            # Verificar que target está dentro de allowed
            try:
                target_full.relative_to(allowed_full)
                # Crear directorio si no existe (para write)
                target_full.parent.mkdir(parents=True, exist_ok=True)
                return True, "Ruta válida", str(target_full)
            except ValueError:
                continue

        return False, "Ruta fuera de directorios permitidos: " + str(self.allowed_paths), None

    def _sanitize_content(self, content: str) -> str:
        """Sanitiza contenido para evitar inyección de código."""
        # Remover posibles scripts o comandos peligrosos
        dangerous_patterns = [
            "__import__", "exec(", "eval(", "os.system", "subprocess",
            "import os", "import sys", "import subprocess"
        ]

        sanitized = content
        for pattern in dangerous_patterns:
            if pattern in sanitized:
                logger.warning("⚠️ Patrón peligroso detectado y removido: " + pattern)
                sanitized = sanitized.replace(pattern, "[REMOVED]")

        return sanitized

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta la operación de archivos con validaciones de seguridad."""
        start_time = time.time()

        # Validar input
        if not self.validate_input(input_data):
            raise SkillExecutionError("Input validation failed")

        operation = input_data.get("operation", "").lower()
        file_path = input_data.get("file_path", "")
        content = input_data.get("content", "")
        encoding = input_data.get("encoding", "utf-8")

        # Validar operación
        if operation not in self.ALLOWED_OPERATIONS:
            return {
                "success": False,
                "error": "Operación no permitida: " + operation + ". Operaciones válidas: " + ", ".join(
                    self.ALLOWED_OPERATIONS),
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "invalid_operation"}
            }

        # Validar ruta
        is_valid, reason, full_path = self._validate_path(file_path)
        if not is_valid:
            return {
                "success": False,
                "error": reason,
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "invalid_path"}
            }

        logger.info("📁 Ejecutando " + operation + " en: " + full_path)

        try:
            # === OPERACIÓN: READ ===
            if operation == "read":
                if not os.path.exists(full_path):
                    return {
                        "success": False,
                        "error": "Archivo no encontrado: " + file_path,
                        "output": None,
                        "metadata": {"skill_name": self.name, "reason": "file_not_found"}
                    }

                # Verificar tamaño del archivo
                file_size = os.path.getsize(full_path)
                if file_size > self.max_file_size:
                    return {
                        "success": False,
                        "error": "Archivo demasiado grande: " + str(file_size) + " bytes (máx: " + str(
                            self.max_file_size) + ")",
                        "output": None,
                        "metadata": {"skill_name": self.name, "reason": "file_too_large"}
                    }

                with open(full_path, 'r', encoding=encoding) as f:
                    file_content = f.read()

                return {
                    "success": True,
                    "output": {
                        "file_path": file_path,
                        "content": file_content,
                        "size_bytes": file_size,
                        "encoding": encoding
                    },
                    "error": None,
                    "metadata": {
                        "skill_name": self.name,
                        "skill_version": self.version,
                        "execution_time_ms": int((time.time() - start_time) * 1000),
                        "operation": operation,
                        "file_size": file_size
                    }
                }

            # === OPERACIÓN: WRITE ===
            elif operation == "write":
                if not content:
                    return {
                        "success": False,
                        "error": "Contenido vacío: no se puede escribir archivo vacío",
                        "output": None,
                        "metadata": {"skill_name": self.name, "reason": "empty_content"}
                    }

                # Sanitizar contenido
                sanitized_content = self._sanitize_content(content)

                # Crear directorio si no existe
                Path(full_path).parent.mkdir(parents=True, exist_ok=True)

                with open(full_path, 'w', encoding=encoding) as f:
                    f.write(sanitized_content)

                return {
                    "success": True,
                    "output": {
                        "file_path": file_path,
                        "bytes_written": len(sanitized_content),
                        "encoding": encoding
                    },
                    "error": None,
                    "metadata": {
                        "skill_name": self.name,
                        "skill_version": self.version,
                        "execution_time_ms": int((time.time() - start_time) * 1000),
                        "operation": operation,
                        "bytes_written": len(sanitized_content)
                    }
                }

            # === OPERACIÓN: LIST ===
            elif operation == "list":
                if not os.path.exists(full_path):
                    return {
                        "success": False,
                        "error": "Directorio no encontrado: " + file_path,
                        "output": None,
                        "metadata": {"skill_name": self.name, "reason": "directory_not_found"}
                    }

                if not os.path.isdir(full_path):
                    return {
                        "success": False,
                        "error": "No es un directorio: " + file_path,
                        "output": None,
                        "metadata": {"skill_name": self.name, "reason": "not_a_directory"}
                    }

                files = []
                for item in os.listdir(full_path):
                    item_path = os.path.join(full_path, item)
                    files.append({
                        "name": item,
                        "is_file": os.path.isfile(item_path),
                        "is_dir": os.path.isdir(item_path),
                        "size": os.path.getsize(item_path) if os.path.isfile(item_path) else 0
                    })

                return {
                    "success": True,
                    "output": {
                        "directory": file_path,
                        "files": files,
                        "total_items": len(files)
                    },
                    "error": None,
                    "metadata": {
                        "skill_name": self.name,
                        "skill_version": self.version,
                        "execution_time_ms": int((time.time() - start_time) * 1000),
                        "operation": operation,
                        "items_count": len(files)
                    }
                }

            # === OPERACIÓN: EXISTS ===
            elif operation == "exists":
                exists = os.path.exists(full_path)
                is_file = os.path.isfile(full_path) if exists else False
                is_dir = os.path.isdir(full_path) if exists else False

                return {
                    "success": True,
                    "output": {
                        "file_path": file_path,
                        "exists": exists,
                        "is_file": is_file,
                        "is_directory": is_dir
                    },
                    "error": None,
                    "metadata": {
                        "skill_name": self.name,
                        "skill_version": self.version,
                        "execution_time_ms": int((time.time() - start_time) * 1000),
                        "operation": operation
                    }
                }

            # === OPERACIÓN: DELETE ===
            elif operation == "delete":
                if not os.path.exists(full_path):
                    return {
                        "success": False,
                        "error": "Archivo/directorio no encontrado: " + file_path,
                        "output": None,
                        "metadata": {"skill_name": self.name, "reason": "not_found"}
                    }

                if os.path.isdir(full_path):
                    os.rmdir(full_path)  # Solo directorios vacíos por seguridad
                    action = "directorio vacío eliminado"
                else:
                    os.remove(full_path)
                    action = "archivo eliminado"

                return {
                    "success": True,
                    "output": {
                        "file_path": file_path,
                        "action": action
                    },
                    "error": None,
                    "metadata": {
                        "skill_name": self.name,
                        "skill_version": self.version,
                        "execution_time_ms": int((time.time() - start_time) * 1000),
                        "operation": operation
                    }
                }

            else:
                return {
                    "success": False,
                    "error": "Operación no implementada: " + operation,
                    "output": None,
                    "metadata": {"skill_name": self.name, "reason": "not_implemented"}
                }

        except PermissionError:
            return {
                "success": False,
                "error": "Permiso denegado: no tienes permisos para esta operación",
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "permission_denied"}
            }
        except Exception as e:
            logger.error("❌ Error en FileOpsSkill: " + str(e))
            return {
                "success": False,
                "error": "Error: " + str(e)[:200],
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "unexpected_error"}
            }