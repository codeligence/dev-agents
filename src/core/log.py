# Copyright (C) 2025 Codeligence
#
# This file is part of Dev Agents.
#
# Dev Agents is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Dev Agents is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Dev Agents.  If not, see <https://www.gnu.org/licenses/>.


import contextvars
import logging
import os
from pathlib import Path

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
context_token_var: contextvars.ContextVar[str] = contextvars.ContextVar("thread_ts", default="main")
_context_based_handlers: dict[str, logging.FileHandler] = {}

_logger_cache = {}


class LoggingConfig:
    """Type-safe configuration class for logging settings."""

    def __init__(self, base_config):
        """Initialize with base configuration.

        Args:
            base_config: BaseConfig instance (avoiding circular import by not typing)
        """
        self._base_config = base_config

    def get_log_dir(self) -> str:
        """Get the logging directory path.

        Priority order:
        1. Configuration file setting (core.log.dir)
        2. LOG_DIR environment variable (backward compatibility)
        3. Default to ./logs

        Returns:
            Absolute path to the logging directory
        """
        # First try the config file setting
        log_dir = self._base_config.get_value('core.log.dir', ".")
        return str(Path(log_dir).resolve())

    def is_configured(self) -> bool:
        try:
            log_dir = Path(self.get_log_dir())
            log_dir.mkdir(parents=True, exist_ok=True)
            return log_dir.exists() and log_dir.is_dir()
        except Exception:
            return False


class ThreadFilter(logging.Filter):
    """Adds `thread_ts` from the context to every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.thread_ts = context_token_var.get()
        return True


class ThreadRouter(logging.Handler):
    """
    One handler per thread.
    Re-uses handlers so log files stay open only once per thread_ts.
    """

    def __init__(self, logs_dir: str = "logs") -> None:
        super().__init__()
        self.logs_dir = logs_dir
        os.makedirs(self.logs_dir, exist_ok=True)

    def emit(self, record: logging.LogRecord) -> None:
        thread_id = getattr(record, "thread_ts", "main")
        h = _context_based_handlers.get(thread_id)
        if h is None:
            log_path = os.path.join(self.logs_dir, f"{thread_id}.log")
            h = logging.FileHandler(log_path, mode="a", encoding="utf-8")
            h.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s [%(thread_ts)s] %(message)s")
            )
            _context_based_handlers[thread_id] = h
        h.emit(record)


def setup_thread_logging(base_config=None):
    """
    Set up the thread-based logging system for the root logger.
    This should be called once at application startup.

    Args:
        base_config: BaseConfig instance. If None, uses default config.
    """
    # Import here to avoid circular imports
    from core.config import get_default_config

    if base_config is None:
        base_config = get_default_config()

    logging_config = LoggingConfig(base_config)
    logs_dir = logging_config.get_log_dir()

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Add console handler if not already present
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(console)

    # Add thread router if not already present
    if not any(isinstance(h, ThreadRouter) for h in root.handlers):
        thread_router = ThreadRouter(logs_dir)
        thread_router.addFilter(ThreadFilter())
        root.addHandler(thread_router)

    # Configure other loggers
    logging.getLogger("pydantic_ai").setLevel(logging.DEBUG)
    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.DEBUG)
    logging.getLogger("codeligence").setLevel(logging.DEBUG)
    logging.getLogger("codeligence_dev").setLevel(logging.DEBUG)


def get_logger(logger_name="codeligence", level="DEBUG"):
    """
    Configure logging for the application. Optionally set up file logging and custom logger name.
    Uses a Singleton pattern to avoid duplicate handlers and duplicate logs.
    """
    key = logger_name
    if key in _logger_cache:
        return _logger_cache[key]
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level) if isinstance(level, str) else level)

    # Allow propagation to root logger for file logging via ThreadRouter
    logger.propagate = True

    # No need to add console handler since we propagate to root logger
    # which already has console and file handlers via setup_thread_logging()

    _logger_cache[key] = logger
    return logger


def set_context_token(thread_ts: str) -> contextvars.Token:
    """
    Set the current thread_ts in the context.
    Returns a token that can be used to reset the context with reset_thread_ts.
    """
    return context_token_var.set(thread_ts)


def reset_context_token(token: contextvars.Token) -> None:
    """
    Reset the thread_ts context variable using the token from set_thread_ts.
    Also clean up the handler for the thread if it exists.
    """
    # Get the previous thread_ts before resetting
    previous_thread_ts = context_token_var.get()

    # Reset the context variable
    context_token_var.reset(token)

    # Clean up the handler for this thread if it exists
    if previous_thread_ts in _context_based_handlers:
        handler = _context_based_handlers[previous_thread_ts]
        # Flush and close the handler
        handler.flush()
        handler.close()
        # Remove from the global dictionary
        del _context_based_handlers[previous_thread_ts]