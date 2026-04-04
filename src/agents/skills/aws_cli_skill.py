# src/agents/skills/aws_cli_skill.py
"""AgentEagle++ - Skill para ejecutar comandos AWS CLI de forma sandboxed."""
from .base_skill import BaseSkill, SkillExecutionError
from typing import Dict, Any, Optional, List
import subprocess
import json
import logging
import re
import time

logger = logging.getLogger(__name__)


class AwsCliSkill(BaseSkill):
    """
    Skill para ejecutar comandos AWS CLI con validación de seguridad.

    ⚠️ Diseñado para sandboxing: solo comandos pre-aprobados (whitelist).
    ✅ Ideal para: consultar recursos, verificar configuración, listar servicios.
    ❌ No permite: crear/eliminar recursos, modificar políticas, acciones destructivas.
    """

    name = "aws_cli"
    description = "Ejecuta comandos AWS CLI de solo lectura para consultar recursos cloud"
    version = "1.0.0"
    category = "aws"

    # === Whitelist de comandos permitidos (solo lectura) ===
    ALLOWED_COMMANDS = [
        # S3
        "s3 ls", "s3api head-bucket", "s3api get-bucket-policy",
        "s3api get-bucket-acl", "s3api get-bucket-versioning",
        "s3api get-bucket-encryption", "s3api get-bucket-logging",
        "s3api list-buckets", "s3api get-object",

        # IAM
        "iam get-user", "iam list-roles", "iam get-role",
        "iam list-users", "iam get-account-summary",
        "iam list-policies", "iam get-policy",

        # EC2
        "ec2 describe-instances", "ec2 describe-security-groups",
        "ec2 describe-vpcs", "ec2 describe-subnets",

        # CloudTrail
        "cloudtrail describe-trails", "cloudtrail lookup-events",

        # GuardDuty
        "guardduty list-detectors", "guardduty get-detector",

        # KMS
        "kms list-keys", "kms describe-key",

        # Config
        "config describe-config-rules", "config describe-config-recorders",

        # Lambda
        "lambda list-functions", "lambda get-function",

        # RDS
        "rds describe-db-instances", "rds describe-db-snapshots",
    ]

    # === Comandos explícitamente PROHIBIDOS ===
    FORBIDDEN_COMMANDS = [
        "delete", "remove", "destroy", "terminate", "kill",
        "put-bucket-policy", "put-role-policy", "attach-user-policy",
        "create-key", "create-access-key", "update-key"
    ]

    parameters = {
        "command": {
            "type": str,
            "description": "Comando AWS CLI a ejecutar (sin prefijo 'aws')",
            "required": True,
            "example": "s3 ls"
        },
        "region": {
            "type": str,
            "description": "Región AWS (opcional, usa default si no se especifica)",
            "required": False,
            "default": "us-east-1"
        },
        "profile": {
            "type": str,
            "description": "Perfil AWS a usar (opcional)",
            "required": False,
            "default": "default"
        },
        "output_format": {
            "type": str,
            "description": "Formato de salida: json, text, table",
            "required": False,
            "enum": ["json", "text", "table"],
            "default": "json"
        },
    }

    required_permissions = ["aws_cli", "network"]
    default_timeout = 30

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.default_region = config.get("default_region", "us-east-1") if config else "us-east-1"
        self.default_profile = config.get("default_profile", "default") if config else "default"
        self._initialized = True
        logger.info(f"✅ AwsCliSkill inicializada (región: {self.default_region})")

    def _validate_command(self, command: str) -> tuple:
        """
        Valida que el comando está en la whitelist permitida.

        Returns:
            tuple: (is_allowed: bool, reason: str)
        """
        cmd_normalized = " ".join(command.lower().split())

        # Verificar comandos prohibidos explícitamente
        for forbidden in self.FORBIDDEN_COMMANDS:
            if forbidden in cmd_normalized:
                return False, "Comando prohibido: '" + forbidden + "' no está permitido por seguridad"

        # Verificar whitelist
        for allowed in self.ALLOWED_COMMANDS:
            if cmd_normalized.startswith(allowed):
                return True, "Comando permitido en whitelist"

        return False, "Comando no está en whitelist. Comandos permitidos: " + ", ".join(
            self.ALLOWED_COMMANDS[:5]) + "..."

    def _sanitize_output(self, output: str) -> str:
        """Sanitiza la salida para evitar exposición de datos sensibles."""
        sanitized = output

        # Patrones para ocultar datos sensibles
        sensitive_patterns = [
            (r'AKIA[0-9A-Z]{16}', '[REDACTED_ACCESS_KEY]'),
            (r'wJalrXUtnFEMI/K7MDENG/[a-zA-Z0-9/+=]+', '[REDACTED_SECRET_KEY]'),
            (r'\d{12}', '[REDACTED_ACCOUNT_ID]'),
        ]

        for pattern, replacement in sensitive_patterns:
            sanitized = re.sub(pattern, replacement, sanitized)

        return sanitized

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta el comando AWS CLI con validaciones de seguridad."""
        start_time = time.time()

        # Validar input
        if not self.validate_input(input_data):
            raise SkillExecutionError("Input validation failed")

        command = input_data["command"]
        region = input_data.get("region", self.default_region)
        profile = input_data.get("profile", self.default_profile)
        output_format = input_data.get("output_format", "json")

        # Validar comando contra whitelist
        is_allowed, reason = self._validate_command(command)
        if not is_allowed:
            execution_time = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "error": reason,
                "output": None,
                "metadata": {
                    "skill_name": self.name,
                    "skill_version": self.version,
                    "execution_time_ms": execution_time,
                    "reason": "command_not_allowed"
                }
            }

        # Construir comando completo
        cli_cmd = ["aws"]
        cli_cmd.extend(command.split())
        cli_cmd.extend(["--region", region, "--profile", profile, "--output", output_format])

        logger.info("🔧 Ejecutando AWS CLI: " + " ".join(cli_cmd))

        try:
            # Ejecutar comando (sandboxed: sin shell=True por seguridad)
            result = subprocess.run(
                cli_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False
            )

            execution_time = int((time.time() - start_time) * 1000)

            if result.returncode != 0:
                error_msg = result.stderr.strip()[:500]
                return {
                    "success": False,
                    "error": "AWS CLI error: " + error_msg,
                    "output": None,
                    "metadata": {
                        "skill_name": self.name,
                        "skill_version": self.version,
                        "execution_time_ms": execution_time,
                        "returncode": result.returncode
                    }
                }

            # Procesar salida
            output = result.stdout.strip()
            output_sanitized = self._sanitize_output(output)

            # Parsear JSON si es posible
            parsed_output = None
            if output_format == "json":
                try:
                    parsed_output = json.loads(output_sanitized)
                except json.JSONDecodeError:
                    pass

            return {
                "success": True,
                "output": parsed_output or output_sanitized,
                "error": None,
                "metadata": {
                    "skill_name": self.name,
                    "skill_version": self.version,
                    "execution_time_ms": execution_time,
                    "command": command,
                    "region": region,
                    "items_count": len(parsed_output) if isinstance(parsed_output, list) else 1
                }
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout ejecutando comando AWS CLI (>" + str(self.timeout) + "s)",
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "timeout"}
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "AWS CLI no encontrado. Instala desde: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html",
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "cli_not_found"}
            }
        except Exception as e:
            logger.error("❌ Error ejecutando AWS CLI skill: " + str(e))
            return {
                "success": False,
                "error": "Error inesperado: " + str(e)[:200],
                "output": None,
                "metadata": {"skill_name": self.name, "reason": "unexpected_error"}
            }