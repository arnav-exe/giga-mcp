import json
import logging
from datetime import datetime, timezone


LOGGER_NAME = "giga_mcp_logger"


def init_logger(level=logging.INFO):
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


def log_event(event, **payload):
    logger = logging.getLogger(LOGGER_NAME)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **payload,
    }
    logger.info(json.dumps(record, sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    init_logger()

    log_event("hello world")
