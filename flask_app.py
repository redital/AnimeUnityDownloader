from flask import Flask, request, jsonify, render_template, send_from_directory
from logger import logger
from web_app.download_manager import start_download, get_download_status, list_downloads
from config import flask_app_config, template_folder, static_folder
from web_app.routes.nas_management_routes import nas_management_routes

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)

app.register_blueprint(nas_management_routes)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/download/<anime_id>', methods=['GET'])
def download_anime(anime_id):

    params = {
        "anime_id": anime_id,
        "start_episode": request.args.get('start_episode'),
        "end_episode": request.args.get('end_episode'),
        "custom_path": request.args.get('custom_path')
    }

    logger.info(f"Request received for download: {params}")

    try:
        result, status_code = start_download(params)
    except Exception as e:
        logger.exception("Errore durante l'avvio del download:")
        return jsonify({
            "status": "error",
            "message": "Errore interno del server",
            "traceback": str(e)
        }), 500

    return jsonify(result), status_code


@app.route('/download-status/<anime_id>', methods=['GET'])
def download_status(anime_id):
    result, status_code = get_download_status(anime_id)
    return jsonify(result), status_code


@app.route('/download-statuses', methods=['GET'])
def list_downloads_route():
    result, status_code = list_downloads()
    return jsonify(result), status_code


@app.errorhandler(Exception)
def handle_exception(e):
    logger.exception("Unhandled Exception:")
    logger.error(str(e.__class__.__name__) + ": " + str(e))
    logger.error(str(e.args))
    return {
        "status": "error",
        "message": str(e)
    }, 500


if __name__ == "__main__":
    run_args = dict(flask_app_config)
    run_args.setdefault("use_reloader", False)
    app.run(**run_args)