import json
import logging
from datetime import datetime, timezone


LOGGER_NAME = "instant_context_logger"


def init_logger(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        logger.setLevel(level)
        return logger
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def log_event(event: str, **payload: object) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **payload,
    }
    logger.info(json.dumps(record, sort_keys=True, ensure_ascii=True))
