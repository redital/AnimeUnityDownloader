import logging
from rich.logging import RichHandler

# Evita configurazioni multiple del logging
if not logging.getLogger().handlers:

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(show_time=False, show_level=False)]#,rich_tracebacks=True
    )

# Logger principale usato ovunque
logger = logging.getLogger("anime_downloader")
logger.setLevel(logging.INFO)

# Funzione helper opzionale
def get_logger(name: str = None):
    return logging.getLogger(name or "anime_downloader")
