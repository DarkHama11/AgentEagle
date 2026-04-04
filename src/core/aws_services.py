# src/core/aws_services.py
"""AgentEagle++ - Lista completa de servicios AWS para detección inteligente (200+ servicios)."""

AWS_SERVICES = {
    # Compute
    "compute": [
        "ec2", "elastic compute cloud", "lambda", "ecs", "elastic container service",
        "eks", "elastic kubernetes service", "fargate", "batch", "lightsail",
        "app runner", "nitro", "outposts", "local zones", "wavelength"
    ],
    # Storage
    "storage": [
        "s3", "simple storage service", "ebs", "elastic block store", "efs",
        "elastic file system", "fsx", "glacier", "storage gateway", "snowball",
        "snowmobile", "datasync", "backup", "storage lens"
    ],
    # Database
    "database": [
        "rds", "relational database service", "dynamodb", "aurora", "redshift",
        "elasticache", "documentdb", "neptune", "timestream", "keyspaces",
        "memorydb", "dms", "database migration service"
    ],
    # Networking & Content Delivery
    "networking": [
        "vpc", "virtual private cloud", "cloudfront", "route53", "api gateway",
        "direct connect", "transit gateway", "private link", "global accelerator",
        "app mesh", "cloud map", "verified access", "client vpn", "site-to-site vpn"
    ],
    # Security, Identity & Compliance
    "security": [
        "iam", "identity and access management", "kms", "key management service",
        "cloudtrail", "guardduty", "inspector", "security hub", "waf", "shield",
        "secrets manager", "certificate manager", "artifact", "config", "macie",
        "detective", "firewall manager", "sso", "single sign-on", "cognito",
        "directory service", "resource access manager", "audit manager"
    ],
    # Management & Governance
    "management": [
        "cloudwatch", "cloudformation", "systems manager", "trusted advisor",
        "organizations", "control tower", "service catalog", "managed services",
        "well-architected tool", "cost explorer", "budgets", "billing",
        "license manager", "chatbot", "application discovery service"
    ],
    # Analytics
    "analytics": [
        "athena", "emr", "elastic mapreduce", "kinesis", "quicksight", "glue",
        "data pipeline", "lake formation", "managed airflow", "msk",
        "managed streaming for kafka", "redshift spectrum", "opensearch"
    ],
    # Machine Learning & AI
    "ml": [
        "sagemaker", "rekognition", "comprehend", "lex", "polly", "transcribe",
        "translate", "textract", "forecast", "personalize", "fraud detector",
        "codeguru", "devops guru", "monitron", "lookout"
    ],
    # Application Integration
    "integration": [
        "sns", "simple notification service", "sqs", "simple queue service",
        "eventbridge", "step functions", "appsync", "mq", "amazon mq",
        "transfer family", "appflow", "eventbridge pipes"
    ],
    # Developer Tools
    "devtools": [
        "codecommit", "codebuild", "codedeploy", "codepipeline", "cloud9",
        "x-ray", "cloudshell", "toolkit", "cli", "sdk", "copilot"
    ],
    # Migration & Transfer
    "migration": [
        "migration hub", "application migration service", "server migration service",
        "database migration service", "data sync", "transfer for sftp",
        "transfer for ftps", "transfer for ftp", "elastic disaster recovery"
    ],
    # IoT
    "iot": [
        "iot core", "iot greengrass", "iot analytics", "iot events", "iot site-wise",
        "iot things graph", "iot device defender", "iot device management",
        "freeRTOS", "panorama", "twinmaker"
    ],
    # Business Applications
    "business": [
        "workspaces", "chime", "connect", "pinpoint", "simple email service",
        "workdocs", "workmail", "appstream"
    ],
    # End User Computing
    "enduser": [
        "workspaces", "appstream", "workdocs", "workmail", "honeycode",
        "nimble studio", "dev environments"
    ],
    # Robotics
    "robotics": [
        "robomaker", "braket", "quantum computing"
    ],
    # Satellite
    "satellite": [
        "ground station"
    ],
    # Game Tech
    "gaming": [
        "gamelift", "lumberyard"
    ],
    # AR/VR
    "arvr": [
        "sumerian"
    ]
}

# Flatten all service names for quick lookup
ALL_AWS_SERVICE_NAMES = []
for category, services in AWS_SERVICES.items():
    for service in services:
        ALL_AWS_SERVICE_NAMES.append(service.lower().replace('-', ' ').replace('_', ' '))


def is_aws_service_query(user_input: str) -> tuple[bool, str, str]:
    """
    Detecta si la pregunta menciona un servicio AWS.

    Returns:
        tuple: (is_aws_service: bool, service_name: str, category: str)
    """
    t = user_input.lower().strip()

    for category, services in AWS_SERVICES.items():
        for service in services:
            service_normalized = service.replace('-', ' ').replace('_', ' ')
            if service_normalized in t or service in t:
                canonical_name = services[0] if services else service
                return True, canonical_name, category

    return False, None, None