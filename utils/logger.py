import logging
from config import Config

logger = logging.getLogger("XTVbot")

def debug(msg, level="info"):
    if Config.DEBUG_MODE:
        if level == "warning":
            logger.warning(msg)
        elif level == "error":
            logger.error(msg)
        elif level == "debug":
            logger.debug(msg)
        else:
            logger.info(msg)
