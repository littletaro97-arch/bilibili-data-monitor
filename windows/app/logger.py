from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import BASE_DIR


def setup_logging() -> logging.Logger:
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("bilibili_local_analytics")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


logger = setup_logging()


def clear_log_file() -> bool:
    file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    try:
        for handler in file_handlers:
            handler.acquire()
            try:
                if handler.stream:
                    handler.stream.close()
                    handler.stream = None
                Path(handler.baseFilename).write_text("", encoding="utf-8")
                handler.stream = handler._open()
            finally:
                handler.release()
        return True
    except OSError:
        return False
