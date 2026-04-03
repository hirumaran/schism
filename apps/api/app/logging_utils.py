from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.config import dictConfig
from typing import Any

job_id_var: ContextVar[str | None] = ContextVar("job_id", default=None)


class JobContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "job_id"):
            record.job_id = job_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "job_id": getattr(record, "job_id", None),
        }
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in {
                "args",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            }:
                continue
            if key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str, log_format: str) -> None:
    formatter_name = "json" if log_format.lower() == "json" else "human"
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "job_context": {
                    "()": "app.logging_utils.JobContextFilter",
                }
            },
            "formatters": {
                "human": {
                    "format": "%(asctime)s %(levelname)s %(name)s [job_id=%(job_id)s] %(message)s",
                },
                "json": {
                    "()": "app.logging_utils.JsonFormatter",
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": formatter_name,
                    "filters": ["job_context"],
                }
            },
            "root": {
                "level": level.upper(),
                "handlers": ["default"],
            },
        }
    )


@contextmanager
def bind_job_id(job_id: str):
    token = job_id_var.set(job_id)
    try:
        yield
    finally:
        job_id_var.reset(token)


class StageTimer:
    def __init__(self, stage_name: str, logger: logging.Logger | None = None) -> None:
        self.stage_name = stage_name
        self.logger = logger or logging.getLogger(__name__)
        self._started = 0.0

    async def __aenter__(self) -> "StageTimer":
        self._started = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        elapsed = int((time.perf_counter() - self._started) * 1000)
        self.logger.info(
            "stage_complete",
            extra={"stage": self.stage_name, "duration_ms": elapsed},
        )
