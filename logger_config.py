import logging
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

def get_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    try:
        level = getattr(logging, LOG_LEVEL)
    except Exception:
        level = logging.INFO
    logger.setLevel(level)
    return logger
