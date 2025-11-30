from config import *

import asyncio
import os
import threading
import requests
import time
from threading import Lock

from flask import Flask, request, jsonify

from anime_downloader import process_anime_download

import logging
from rich.logging import RichHandler

app = Flask(__name__)

# Event loop separato per task asincroni
background_loop = asyncio.new_event_loop()

# Configure logging with RichHandler so logs temporarily clear Live UI
rich_handler = RichHandler(show_time=False)
logging.getLogger("werkzeug").handlers = [rich_handler]
logging.getLogger("werkzeug").setLevel(logging.INFO)

# Ensure the Flask app logger also uses RichHandler
app.logger.handlers = [rich_handler]
app.logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO, handlers=[rich_handler])

def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

# Avviamo il loop asincrono in un thread dedicato
threading.Thread(target=start_background_loop, args=(background_loop,), daemon=True).start()

# Tracciamento in-memory dei download per `anime_id`
downloads_status: dict = {}
downloads_lock = Lock()

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

    # Se un download per lo stesso anime è già in coda/ in esecuzione, rifiuta
    with downloads_lock:
        existing = downloads_status.get(anime_id)
        if existing and existing.get("status") in ("queued", "running"):
            return jsonify({"status": "error", "message": "Download già in corso per questo anime", "anime_id": anime_id}), 409

        # registra stato iniziale per questo anime_id
        downloads_status[anime_id] = {
            "anime_id": anime_id,
            "status": "queued",
            "message": None,
            "params": process_anime_download_params,
            "started_at": None,
            "finished_at": None,
            # per-episode tracking
            "episodes": {},
            "total_episodes": None,
            "overall_percent": 0.0,
        }

    # callback che verrà chiamata da save_file_with_progress
    def progress_callback(episode_idx, value):
        """Riceve due tipi di chiamata:
        - progress_callback('__total__', total) -> imposta `total_episodes`
        - progress_callback(episode_idx:int, percent:float) -> aggiorna percentuale episodio
        """
        with downloads_lock:
            info = downloads_status.get(anime_id)
            if info is None:
                return

            if episode_idx == "__total__":
                try:
                    info["total_episodes"] = int(value)
                except Exception:
                    info["total_episodes"] = None
                return

            # update episode percent
            try:
                idx = int(episode_idx)
                pct = float(value)
            except Exception:
                return

            info.setdefault("episodes", {})[idx] = pct

            # calcola percentuale complessiva: se total_episodes conosciuto, usa quello, altrimenti media dei presentI
            total = info.get("total_episodes")
            if total and total > 0:
                # somma percentuali attendendo 0 per mancanti
                summed = sum(info["episodes"].get(i, 0) for i in range(total))
                overall = summed / total
            else:
                parts = list(info["episodes"].values())
                overall = (sum(parts) / len(parts)) if parts else 0.0

            info["overall_percent"] = overall

    # passiamo il callback ai parametri di download
    process_anime_download_params_full = process_anime_download_params.copy()
    process_anime_download_params_full["progress_callback"] = progress_callback

    async def _job_wrapper():
        with downloads_lock:
            downloads_status[anime_id]["status"] = "running"
            downloads_status[anime_id]["started_at"] = time.time()

        try:
            await process_anime_download(**process_anime_download_params_full)

        except Exception as exc:  # noqa: BLE001 - log exception to status
            with downloads_lock:
                downloads_status[anime_id]["status"] = "failed"
                downloads_status[anime_id]["message"] = str(exc)
                downloads_status[anime_id]["finished_at"] = time.time()
        else:
            with downloads_lock:
                downloads_status[anime_id]["status"] = "completed"
                downloads_status[anime_id]["finished_at"] = time.time()

    # Avvia la coroutine wrapper nel loop asincrono di background
    asyncio.run_coroutine_threadsafe(_job_wrapper(), background_loop)

    # RISPOSTA IMMEDIATA con anime_id per monitoraggio
    return jsonify({"status": "success", "message": "Richiesta presa in carico", "anime_id": anime_id, "params": process_anime_download_params}), 200


@app.route('/download-status/<anime_id>', methods=['GET'])
def download_status(anime_id):
    """Recupera lo stato del download dato l'`anime_id`."""
    with downloads_lock:
        info = downloads_status.get(anime_id)

    if not info:
        return jsonify({"status": "error", "message": "Download non trovato"}), 404

    return jsonify({"status": "success", "data": info}), 200


@app.route('/download-statuses', methods=['GET'])
def list_downloads():
    """Lista tutti i download (stati)."""
    with downloads_lock:
        items = list(downloads_status.values())

    return jsonify({"status": "success", "data": items}), 200


if __name__ == "__main__":
    # Disable the reloader to avoid duplicate processes which can interfere with
    # Rich Live output. If you need the reloader during development, remove
    # `use_reloader=False` but expect possible duplicated UI artifacts.
    run_args = dict(flask_app_config)
    run_args.setdefault("use_reloader", False)
    app.run(**run_args)
