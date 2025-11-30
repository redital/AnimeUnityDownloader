from flask import Flask, request, jsonify
import logging
from rich.logging import RichHandler
from web_app.download_manager import start_download, get_download_status, list_downloads
from config import flask_app_config

app = Flask(__name__)

# Configurazione del logging con RichHandler
rich_handler = RichHandler(show_time=False)
logging.getLogger("werkzeug").handlers = [rich_handler]
logging.getLogger("werkzeug").setLevel(logging.INFO)

# Assicurati che anche il logger di Flask usi RichHandler
app.logger.handlers = [rich_handler]
app.logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO, handlers=[rich_handler])

@app.route('/download/<anime_id>', methods=['GET'])
def download_anime(anime_id):
    params = {
        "anime_id": anime_id,
        "start_episode": request.args.get('start_episode'),
        "end_episode": request.args.get('end_episode'),
        "custom_path": request.args.get('custom_path')
    }
    result, status_code = start_download(params)
    return jsonify(result), status_code

@app.route('/download-status/<anime_id>', methods=['GET'])
def download_status(anime_id):
    result, status_code = get_download_status(anime_id)
    return jsonify(result)

@app.route('/download-statuses', methods=['GET'])
def list_downloads_route():
    result, status_code = list_downloads()
    return jsonify(result)

if __name__ == "__main__":
    run_args = dict(flask_app_config)
    run_args.setdefault("use_reloader", False)
    app.run(**run_args)
