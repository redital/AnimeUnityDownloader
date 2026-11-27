"""Logging configuration shared by the web interface."""

import logging

from rich.logging import RichHandler

# Avoid configuring the logging more than once
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(show_time=False, show_level=False)],
    )

# Main logger used everywhere
logger = logging.getLogger("anime_downloader")
logger.setLevel(logging.INFO)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the logger with the given name, or the main logger."""
    return logging.getLogger(name or "anime_downloader")
