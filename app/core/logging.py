import contextvars
import json
import logging
from datetime import datetime, timezone


request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
request_method_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_method", default="-")
request_path_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_path", default="-")


class JsonFormatter(logging.Formatter):
    """Render logs as structured JSON for production-friendly ingestion."""

    RESERVED_ATTRS = {
        "args",
        "asctime",
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
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "method": request_method_var.get(),
            "endpoint": request_path_var.get(),
        }

        for key, value in record.__dict__.items():
            if key in self.RESERVED_ATTRS or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    root_logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)
