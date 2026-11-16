"""Rotating application log setup for Windows Bar."""

import logging
import logging.handlers
import sys
import threading
from pathlib import Path

LOGGER_NAME = "windowsbar"
MAX_LOG_BYTES = 1_048_576
BACKUP_COUNT = 4


def configure_logging(app_dir):
    """Write application and uncaught-thread exceptions under ``logs/``."""
    log_path = Path(app_dir) / "logs" / "windowsbar.log"
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for old in list(logger.handlers):
        if getattr(old, "_windowsbar_file_handler", False):
            logger.removeHandler(old)
            old.close()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=MAX_LOG_BYTES, backupCount=BACKUP_COUNT,
            encoding="utf-8")
    except OSError:
        logger.exception("Could not open the Windows Bar log file at %s", log_path)
        return None

    handler._windowsbar_file_handler = True
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s"))
    logger.addHandler(handler)

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.error("Uncaught exception", exc_info=(
            exc_type, exc_value, exc_traceback))

    def handle_thread_exception(args):
        logger.error("Uncaught exception in thread %s", args.thread.name,
                     exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = handle_exception
    threading.excepthook = handle_thread_exception
    return log_path
