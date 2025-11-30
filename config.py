import os

flask_app_config = {
    "debug": os.environ.get("FLASK_DEBUG", True),
    "host": os.environ.get("FLASK_HOST", "0.0.0.0"),
    "port": os.environ.get("FLASK_PORT", 5000),
    "ssl_context":os.environ.get("SSL_CONTEXT", None)
}

