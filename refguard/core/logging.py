"""RefGuard 日志配置。"""
import logging
import sys
from pathlib import Path
from typing import Any

from .config import settings


class TextFormatter(logging.Formatter):
    """控制台日志格式化器。"""

    def format(self, record: logging.LogRecord) -> str:
        return super().format(record)


def setup_logging() -> None:
    """根据配置初始化日志。"""
    level = getattr(logging, settings.log_level)
    logging.getLogger().setLevel(level)
    if not logging.getLogger().handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(TextFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logging.getLogger().addHandler(h)
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
