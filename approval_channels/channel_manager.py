import logging
from typing import Dict, List, Optional
from .base_channel import BaseApprovalChannel

logger = logging.getLogger("AgentEagle.ApprovalChannelManager")


class ApprovalChannelManager:
    """
    Gestor central de canales de aprobación.
    Permite registrar múltiples canales (Telegram, Slack, etc.)
    y enrutar solicitudes al canal apropiado.
    """

    def __init__(self):
        self._channels: Dict[str, BaseApprovalChannel] = {}
        logger.info("ApprovalChannelManager inicializado")

    def register_channel(self, channel: BaseApprovalChannel) -> None:
        """Registra un nuevo canal de aprobación."""
        name = channel.channel_name
        if name in self._channels:
            logger.warning(f"Canal '{name}' ya registrado. Sobrescribiendo.")

        self._channels[name] = channel
        logger.info(f"✅ Canal registrado: {name}")

    def unregister_channel(self, channel_name: str) -> None:
        """Elimina un canal registrado."""
        if channel_name in self._channels:
            self._channels[channel_name].stop()
            del self._channels[channel_name]
            logger.info(f"Canal eliminado: {channel_name}")

    def get_channel(self, channel_name: str) -> Optional[BaseApprovalChannel]:
        """Obtiene un canal por nombre."""
        return self._channels.get(channel_name)

    def list_channels(self) -> List[str]:
        """Lista todos los canales registrados."""
        return list(self._channels.keys())

    def start_all(self) -> None:
        """Inicia todos los canales registrados."""
        for name, channel in self._channels.items():
            try:
                channel.start()
                logger.info(f"✅ Canal iniciado: {name}")
            except Exception as e:
                logger.error(f"Error iniciando canal {name}: {e}")

    def stop_all(self) -> None:
        """Detiene todos los canales."""
        for name, channel in self._channels.items():
            try:
                channel.stop()
                logger.info(f"🛑 Canal detenido: {name}")
            except Exception as e:
                logger.error(f"Error deteniendo canal {name}: {e}")