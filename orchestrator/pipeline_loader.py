import os
import yaml
from typing import Dict, Any


class PipelineLoader:
    """Carga y parsea configuraciones de pipelines en formato YAML."""

    def __init__(self, pipelines_dir: str):
        self.pipelines_dir = pipelines_dir

    def load(self, pipeline_name: str) -> Dict[str, Any]:
        file_path = os.path.join(self.pipelines_dir, f"{pipeline_name}.yaml")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Pipeline no encontrado: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)

        if not config or "steps" not in config:
            raise ValueError(f"El pipeline '{pipeline_name}' no tiene una estructura válida (falta 'steps').")

        return config