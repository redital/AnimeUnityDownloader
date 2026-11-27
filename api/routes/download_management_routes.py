"""Routes to control the downloads started through the API."""

from flask import Blueprint, jsonify

from api.download_manager import (
    cancel_all_downloads,
    cancel_download,
    cleanup_finished_downloads,
    pause_all_downloads,
    remove_download,
    resume_all_downloads,
)

download_management_routes = Blueprint("download_management", __name__)


@download_management_routes.route("/downloads/pause", methods=["POST"])
def pause_downloads_route():
    """Pause all the downloads."""
    result, status_code = pause_all_downloads()
    return jsonify(result), status_code


@download_management_routes.route("/downloads/resume", methods=["POST"])
def resume_downloads_route():
    """Resume all the paused downloads."""
    result, status_code = resume_all_downloads()
    return jsonify(result), status_code


@download_management_routes.route("/downloads/cancel", methods=["POST"])
def cancel_downloads_route():
    """Cancel all the active downloads."""
    result, status_code = cancel_all_downloads()
    return jsonify(result), status_code


@download_management_routes.route("/download/<anime_id>/cancel", methods=["POST"])
def cancel_single_download_route(anime_id):
    """Cancel a single download."""
    result, status_code = cancel_download(anime_id)
    return jsonify(result), status_code


@download_management_routes.route("/download/<anime_id>/remove", methods=["POST"])
def remove_single_download_route(anime_id):
    """Remove a finished download from the list."""
    result, status_code = remove_download(anime_id)
    return jsonify(result), status_code


@download_management_routes.route("/downloads/cleanup", methods=["POST"])
def cleanup_finished_route():
    """Remove all the finished downloads from the list."""
    result, status_code = cleanup_finished_downloads()
    return jsonify(result), status_code
