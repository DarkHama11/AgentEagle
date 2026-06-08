import re
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("AgentEagle.CaptionParserService")


class CaptionParserService:
    """
    Parsea el caption de un archivo enviado por Telegram para extraer:
    - Cantidad de copias
    - Grupo de impresora
    - Otras instrucciones
    """

    VALID_GROUPS = ['finance', 'legal', 'general']

    def parse(self, caption: Optional[str]) -> Dict[str, Any]:
        """
        Parsea el caption y extrae instrucciones.

        :param caption: Texto del caption (puede ser None o vacío)
        :return: Dict con copies, printer_group, has_instructions
        """
        result = {
            "copies": None,
            "printer_group": None,
            "has_instructions": False,
            "raw_caption": caption or ""
        }

        if not caption or not caption.strip():
            return result

        caption = caption.strip().lower()
        result["has_instructions"] = True

        # Patrón 1: "qty:N" o "cantidad:N"
        match = re.search(r'(?:qty|cantidad)\s*[:=]\s*(\d+)', caption)
        if match:
            result["copies"] = int(match.group(1))
            logger.info(f"📝 Caption parseado: qty={result['copies']}")

        # Patrón 2: "N copias" o "N copia"
        if result["copies"] is None:
            match = re.search(r'(\d+)\s*(?:copias?|copys?|unidades?)', caption)
            if match:
                result["copies"] = int(match.group(1))
                logger.info(f"📝 Caption parseado: {result['copies']} copias")

        # Patrón 3: Solo número al inicio o final
        if result["copies"] is None:
            match = re.search(r'^(\d+)$', caption) or re.search(r'\b(\d+)\b', caption)
            if match:
                num = int(match.group(1))
                if 1 <= num <= 100:  # Rango razonable
                    result["copies"] = num
                    logger.info(f"📝 Caption parseado: {result['copies']} (número simple)")

        # Patrón 4: Grupo de impresora
        for group in self.VALID_GROUPS:
            if group in caption.split():
                result["printer_group"] = group
                logger.info(f"📝 Caption parseado: grupo={group}")
                break

        return result

    def validate_copies(self, copies: Optional[int]) -> Optional[int]:
        """Valida y ajusta el número de copias."""
        if copies is None:
            return None
        if copies < 1:
            return 1
        if copies > 100:
            logger.warning(f"⚠️ Cantidad muy alta ({copies}), limitando a 100")
            return 100
        return copies