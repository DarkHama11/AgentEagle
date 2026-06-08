"""
Módulo de canales de aprobación interactiva.
Extiende el sistema de aprobación existente permitiendo
aprobar/rechazar desde canales externos (Telegram, Slack, etc.)
"""

from .base_channel import BaseApprovalChannel
from .telegram_channel import TelegramApprovalChannel
from .channel_manager import ApprovalChannelManager

__all__ = [
    "BaseApprovalChannel",
    "TelegramApprovalChannel",
    "ApprovalChannelManager"
]