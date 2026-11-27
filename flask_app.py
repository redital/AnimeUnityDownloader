"""Flask application exposing the download API."""

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from config import flask_app_config
from logger import logger
from api.download_manager import (
    get_download_status,
    list_downloads,
    start_download,
)
from api.routes.download_management_routes import download_management_routes

app = Flask(__name__, static_folder=None)

app.register_blueprint(download_management_routes)


@app.route("/download/<anime_id>", methods=["GET"])
def download_anime(anime_id):
    """Start the download of an anime, optionally limited to a range of episodes."""
    params = {
        "anime_id": anime_id,
        "start_episode": request.args.get("start_episode"),
        "end_episode": request.args.get("end_episode"),
        "custom_path": request.args.get("custom_path"),
    }

    logger.info("Request received for download: %s", params)

    try:
        result, status_code = start_download(params)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Errore durante l'avvio del download:")
        return jsonify(
            {"status": "error", "message": "Errore interno del server"},
        ), 500

    return jsonify(result), status_code


@app.route("/download-status/<anime_id>", methods=["GET"])
def download_status(anime_id):
    """Return the status of a single download."""
    result, status_code = get_download_status(anime_id)
    return jsonify(result), status_code


@app.route("/download-statuses", methods=["GET"])
def list_downloads_route():
    """Return the status of all the downloads."""
    result, status_code = list_downloads()
    return jsonify(result), status_code


@app.errorhandler(Exception)
def handle_exception(error):
    """Return errors as JSON, keeping the status code of HTTP errors."""
    if isinstance(error, HTTPException):
        return jsonify(
            {"status": "error", "message": error.description},
        ), error.code

    logger.exception("Unhandled Exception:")
    return jsonify({"status": "error", "message": str(error)}), 500


if __name__ == "__main__":
    run_args = dict(flask_app_config)
    run_args.setdefault("use_reloader", False)
    app.run(**run_args)
