import asyncio
import os
import threading
import time
from threading import Lock
import requests
from anime_downloader import process_anime_download ,fetch_page_httpx
from src.crawler.crawler import Crawler

from logger import get_logger
from web_app.nas_power_manager import nas_manager, nas_power_on


logger = get_logger(__name__)
  


# Event loop separato per task asincroni
background_loop = asyncio.new_event_loop()

# Tracciamento in-memory dei download per `anime_id`
downloads_status = {}
downloads_lock = Lock()

def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

# Avviamo il loop asincrono in un thread dedicato
threading.Thread(target=start_background_loop, args=(background_loop,), daemon=True).start()

# def check_resource_availability(url):
#     logger.info(f"Verifying resource availability for URL: {url}")
#     res = requests.get(url, timeout=5)
#     if res.status_code != 200:
#         #res.raise_for_status()
#         if res.status_code == 404:
#             msg = "Resource not found (404)"
#             logger.info(msg)
#             return False, msg
#         elif res.status_code == 405:
#             msg = "Anime id not found (405)"
#             logger.info(msg)
#             return False, msg
#         msg = f"Error, status code: {res.status_code}"
#         logger.info(msg)
#         return False, msg
#     return True, "ok"
def new_check_resource_availability(url):
    logger.info(f"Verifying resource availability for URL: {url}")
    try:
        crawler = Crawler(url=url, start_episode=None, end_episode=None)
    except Exception as e:
        message = f"Error initializing crawler"
        logger.error(message)
        logger.exception(e)
        return False, message, None, None
    soup = fetch_page_httpx(url)
    anime_name = crawler.extract_anime_name(soup, url)
    n_episodes = crawler.num_episodes
    if n_episodes<1:
        message = "No episodes found for the given anime ID"
        logger.error(message)
        return False, message, None, None
    return True, "ok", anime_name, n_episodes

def progress_callback(anime_id, episode_idx, value):
    """Callback per il monitoraggio del progresso del download"""
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

        if episode_idx == "__anime_name__":
            info["anime_name"] = str(value)
            return

        # Update episodio
        try:
            idx = int(episode_idx)
            pct = float(value)
        except Exception:
            return

        info.setdefault("episodes", {})[idx] = pct

        # Calcola la percentuale totale
        total = info.get("total_episodes")
        if total and total > 0:
            summed = sum(info["episodes"].get(i, 0) for i in range(total))
            overall = summed / total
        else:
            parts = list(info["episodes"].values())
            overall = (sum(parts) / len(parts)) if parts else 0.0

        info["overall_percent"] = overall

def power_check_before_download():
    nas_online, mount_ok = nas_manager.get_nas_status()
    logger.info(f"NAS status - Online: {nas_online}, Mount OK: {mount_ok}")

    return nas_power_on(nas_online, mount_ok)

def start_download(params):
    anime_id = params.get("anime_id")
    base_path = os.getcwd()

    # Verifica se la risorsa è disponibile
    check, message, anime_name, n_episodes = new_check_resource_availability(f"https://www.animeunity.so/anime/{anime_id}")
    if not check:
        return {"status": "error", "message": message}, 404

    logger.info(f"Resource available for anime_id {anime_id}: {anime_name} with {n_episodes} episodes.")
    
    logger.info("Verifying NAS status before starting download.")
    power_check = power_check_before_download()
    if power_check[1] != 200:
        return power_check
    
    logger.info("NAS is ready. Proceeding with download.")

    path = None
    if params.get('custom_path'):
        path = os.path.join(base_path, params['custom_path'])

    process_anime_download_params = {
        "url": f"https://www.animeunity.so/anime/{anime_id}",
        "start_episode": int(params.get('start_episode')) if params.get('start_episode') else None,
        "end_episode": int(params.get('end_episode')) if params.get('end_episode') else None,
        "custom_path": path,
    }

    # Se un download per lo stesso anime è già in coda, rifiuta
    with downloads_lock:
        existing = downloads_status.get(anime_id)
        if existing and existing.get("status") in ("queued", "running"):
            return {"status": "error", "message": "Download già in corso per questo anime", "anime_id": anime_id}, 400

        # Registra stato iniziale
        downloads_status[anime_id] = {
            "anime_id": anime_id,
            "anime_name": anime_name,
            "status": "queued",
            "message": None,
            "params": process_anime_download_params,
            "started_at": None,
            "finished_at": None,
            "episodes": {},
            "total_episodes": n_episodes,
            "overall_percent": 0.0,
        }

    # Avvia la coroutine per il download
    async def _job_wrapper():
        with downloads_lock:
            downloads_status[anime_id]["status"] = "running"
            downloads_status[anime_id]["started_at"] = time.time()

        try:
            # prepare control callback and wrapped progress callback to pass extra info
            def control_cb():
                with downloads_lock:
                    info = downloads_status.get(anime_id, {})
                    return {
                        'paused': bool(info.get('paused', False)),
                        'cancelled': bool(info.get('cancelled', False)),
                    }

            def wrapped_progress_cb(idx, val):
                return progress_callback(anime_id, idx, val)

            extra_info = {
                'progress_cb': wrapped_progress_cb,
                'control_cb': control_cb,
            }

            await process_anime_download(**process_anime_download_params, progress_callback=extra_info)
        except Exception as exc:
            # handle cancellation specially
            msg = str(exc)
            logger.exception(f"Errore durante il download per anime_id {anime_id}:{exc}")
            with downloads_lock:
                if 'download_cancelled' in msg or 'download_cancelled' in repr(exc):
                    downloads_status[anime_id]["status"] = "cancelled"
                else:
                    downloads_status[anime_id]["status"] = "failed"
                    downloads_status[anime_id]["message"] = str(exc)
                downloads_status[anime_id]["finished_at"] = time.time()
        else:
            with downloads_lock:
                downloads_status[anime_id]["status"] = "completed"
                downloads_status[anime_id]["finished_at"] = time.time()

    asyncio.run_coroutine_threadsafe(_job_wrapper(), background_loop)

    logger.info(f"Preso in carico download per anime_id: {anime_id} con parametri: {process_anime_download_params}")
    return {"status": "success", "message": "Richiesta presa in carico", "anime_id": anime_id, "params": process_anime_download_params}, 200


def pause_all_downloads():
    with downloads_lock:
        for aid, info in downloads_status.items():
            if info.get('status') in ('running', 'queued'):
                info['paused'] = True
                info['prev_status'] = info.get('status')
                info['status'] = 'paused'
    return {"status": "success", "message": "Tutti i download messi in pausa"}, 200


def resume_all_downloads():
    with downloads_lock:
        for aid, info in downloads_status.items():
            if info.get('status') == 'paused':
                info['paused'] = False
                # restore previous status or set to running
                prev = info.pop('prev_status', None)
                info['status'] = prev if prev in ('queued', 'running') else 'running'
    return {"status": "success", "message": "Tutti i download ripresi"}, 200


def cancel_all_downloads():
    with downloads_lock:
        for aid, info in downloads_status.items():
            # mark cancelled; running threads will pick this up
            if info.get('status') in ('running', 'queued', 'paused'):
                info['cancelled'] = True
                info['status'] = 'cancelled'
                info['finished_at'] = time.time()
    return {"status": "success", "message": "Tutti i download annullati"}, 200


def cancel_download(anime_id):
    with downloads_lock:
        info = downloads_status.get(anime_id)
        if not info:
            return {"status": "error", "message": "Download non trovato"}, 404
        if info.get('status') in ('completed', 'cancelled', 'failed'):
            return {"status": "error", "message": "Download già terminato"}, 400
        info['cancelled'] = True
        info['status'] = 'cancelled'
        info['finished_at'] = time.time()
    return {"status": "success", "message": f"Download {anime_id} annullato"}, 200

def get_download_status(anime_id):
    with downloads_lock:
        info = downloads_status.get(anime_id)
    if not info:
        msg = "Download non trovato"
        logger.error(msg)
        return {"status": "error", "message": msg}, 404
    return {"status": "success", "data": info}, 200

def list_downloads():
    with downloads_lock:
        items = list(downloads_status.values())
    return {"status": "success", "data": items}, 200
