# 🦅 AgentEagle

Motor de búsqueda especializado en ciberseguridad cloud con fine-tuning de LLMs.

## ✨ Features

- 🔍 SecuritySearch v2.1 con cache determinista
- 🎯 Validación 100% en 12 pruebas de búsqueda (CVE, MITRE, AWS, Azure, GCP)
- 🧰 Sistema de skills: aws_cli, cve_lookup, mitre_mapping, file_ops, compliance_check
- 🤖 Enrutamiento inteligente entre agentes (seguridad, oficina, general)
- 📊 Dashboard Streamlit interactivo
- 🔄 Fine-tuning QLoRA para modelos LLM especializados

## 🚀 Instalación

\\\ash
pip install -r requirements.txt
\\\

## 🏃‍♂️ Uso

\\\ash
# Ejecutar dashboard
streamlit run dashboard.py

# Ejecutar pruebas de búsqueda
python scripts/test_search_skills.py --verbose
\\\

## 📁 Estructura

\\\
AgentEagle/
├── 📄 main.py              # Entry point
├── 📄 dashboard.py         # UI Streamlit
├── 📁 src/                 # Código fuente
│   ├── agents/            # Agentes especializados
│   ├── skills/            # Skills de acción
│   ├── core/              # Configuración y utilidades
│   └── server/            # API FastAPI
├── 📁 tools/              # Herramientas de búsqueda
├── 📁 scripts/            # Scripts de fine-tuning y testing
└── 📄 requirements.txt    # Dependencias
\\\

## 📄 Licencia

MIT License - Ver archivo LICENSE para más detalles.
