from config import *

import asyncio
import os
import threading
import requests

from flask import Flask, request, jsonify

from anime_downloader import process_anime_download

app = Flask(__name__)

# Event loop separato per task asincroni
background_loop = asyncio.new_event_loop()

def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

# Avviamo il loop asincrono in un thread dedicato
threading.Thread(target=start_background_loop, args=(background_loop,), daemon=True).start()

def check_resource_availability(url):
    res = requests.get(url, timeout=5)
    if res.status_code != 200:
        if res.status_code == 404:
            return False, "Resource not found (404)"
        if res.status_code == 405:
            return False, "Method not allowed (405)"
        return False, f"Error, status code: {res.status_code}"
    return True, "ok"

@app.route('/download/<anime_id>', methods=['GET'])
def download_anime(anime_id):
    base_path = os.getcwd()

    check, message = check_resource_availability(f"https://www.animeunity.so/anime/{anime_id}")
    if not check:
        return jsonify({"status": "error", "message": message}), 404

    path = None
    if request.args.get('custom_path'):
        if request.args.get('full_path') and request.args.get('full_path').lower() == 'true':
            path = request.args.get('custom_path')
        else:
            path = os.path.join(base_path, request.args.get('custom_path'))

    process_anime_download_params = {
        "url": f"https://www.animeunity.so/anime/{anime_id}",
        "start_episode": request.args.get('start_episode'),
        "end_episode": request.args.get('end_episode'),
        "custom_path": path,
    }

    # Avvia la coroutine nel loop asincrono di background
    asyncio.run_coroutine_threadsafe(
        process_anime_download(**process_anime_download_params),
        background_loop
    )

    # RISPOSTA IMMEDIATA
    return jsonify({"status": "success", "message": "Richiesta presa in carico", "params":process_anime_download_params}), 200


if __name__ == "__main__":
    app.run(**flask_app_config)
