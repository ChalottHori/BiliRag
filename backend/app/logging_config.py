"""日志配置：落盘 `data/logs/`，并对敏感信息做脱敏过滤。"""

from __future__ import annotations

import logging
import logging.config
import sys
from typing import Any

from .config import get_data_dir

# 命中这些关键字的日志行会被整体丢弃，避免 cookie / api_key 泄露。
_SCRUB_KEYWORDS = ("cookie", "api_key", "apikey", "sessdata", "bili_jct", "token")


class _ScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lower()
        return not any(keyword in message for keyword in _SCRUB_KEYWORDS)


def setup_logging(level: int = logging.INFO) -> None:
    logs_dir = get_data_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"scrub": {"()": _ScrubFilter}},
        "formatters": {
            "default": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stderr,
                "formatter": "default",
                "filters": ["scrub"],
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(logs_dir / "app.log"),
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 3,
                "formatter": "default",
                "filters": ["scrub"],
            },
        },
        "root": {"handlers": ["console", "file"], "level": level},
    }
    logging.config.dictConfig(config)
