"""Management of the downloads started through the API.

Downloads run on a dedicated asyncio event loop living in a background thread.
Their state is kept in memory, indexed by anime id, and protected by a lock.
"""

from __future__ import annotations

import asyncio
import copy
import threading
import time
from pathlib import Path

from anime_downloader import fetch_page_httpx, process_anime_download
from config import animeunity_url, download_root
from logger import get_logger
from src.crawler.crawler import Crawler
from src.download_utils import DownloadCancelledError, DownloadHooks

logger = get_logger(__name__)

ACTIVE_STATUSES = ("queued", "running", "paused")
FINISHED_STATUSES = ("completed", "failed", "cancelled")

# Separate event loop, running in its own thread, for the download jobs
background_loop = asyncio.new_event_loop()

# In-memory tracking of the downloads, indexed by `anime_id`
downloads_status: dict[str, dict] = {}
downloads_lock = threading.Lock()


def _run_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Run the given event loop forever in the current thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


threading.Thread(
    target=_run_background_loop,
    args=(background_loop,),
    daemon=True,
).start()


def check_resource_availability(url: str) -> tuple[bool, str, str | None, int | None]:
    """Check that the anime page exists and return its name and episodes count."""
    logger.info("Verifying resource availability for URL: %s", url)
    soup = fetch_page_httpx(url)
    try:
        crawler = Crawler(url=url, episodes_range=(None, None), soup=soup)
    except Exception:  # pylint: disable=broad-exception-caught
        message = "Error initializing crawler"
        logger.exception(message)
        return False, message, None, None

    anime_name = crawler.extract_anime_name(soup, url)
    n_episodes = crawler._get_num_episodes()  # pylint: disable=protected-access
    if n_episodes < 1:
        message = "No episodes found for the given anime ID"
        logger.error(message)
        return False, message, None, None
    return True, "ok", anime_name, n_episodes


def _parse_episode(value: str | None) -> int | None:
    """Convert an episode number received as text, or None if it is missing."""
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        msg = "Numero di episodio non valido"
        raise ValueError(msg) from exc


def _resolve_custom_path(custom_path: str | None) -> str | None:
    """Resolve a custom download path, which must stay inside the download root.

    A relative path is taken from the download root; an absolute path, such as
    the mount point of a network share, is accepted if it is inside the root.
    """
    if not custom_path:
        return None
    root = Path(download_root).resolve()
    target = (root / custom_path).resolve()
    if target != root and root not in target.parents:
        msg = "Percorso personalizzato non valido"
        raise ValueError(msg)
    return str(target)


def _make_hooks(anime_id: str) -> DownloadHooks:
    """Build the hooks that connect a download to its entry in `downloads_status`."""

    def on_start(anime_name: str | None, total_episodes: int) -> None:
        with downloads_lock:
            info = downloads_status.get(anime_id)
            if info is None:
                return
            if anime_name:
                info["anime_name"] = anime_name
            info["total_episodes"] = total_episodes

    def on_progress(episode_idx: int, percentage: float) -> None:
        with downloads_lock:
            info = downloads_status.get(anime_id)
            if info is None:
                return
            info["episodes"][episode_idx] = percentage

            total = info.get("total_episodes")
            if total:
                summed = sum(info["episodes"].get(i, 0) for i in range(total))
                info["overall_percent"] = summed / total
            else:
                parts = list(info["episodes"].values())
                info["overall_percent"] = sum(parts) / len(parts)

    def get_flag(name: str) -> bool:
        with downloads_lock:
            return bool(downloads_status.get(anime_id, {}).get(name, False))

    return DownloadHooks(
        on_start=on_start,
        on_progress=on_progress,
        is_paused=lambda: get_flag("paused"),
        is_cancelled=lambda: get_flag("cancelled"),
    )


async def _run_download(anime_id: str, call_params: dict, hooks: DownloadHooks) -> None:
    """Run a download job and record its final status."""
    with downloads_lock:
        info = downloads_status[anime_id]
        if info.get("cancelled"):
            return
        info["started_at"] = time.time()
        if info.get("paused"):
            info["prev_status"] = "running"
        else:
            info["status"] = "running"

    try:
        await process_anime_download(**call_params, hooks=hooks)
    except DownloadCancelledError:
        final_status, message = "cancelled", None
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception("Error while downloading anime_id %s", anime_id)
        final_status, message = "failed", str(exc)
    else:
        final_status, message = "completed", None

    with downloads_lock:
        info = downloads_status.get(anime_id)
        if info is None:
            return
        info["status"] = final_status
        if message is not None:
            info["message"] = message
        info["finished_at"] = info.get("finished_at") or time.time()


def start_download(params: dict) -> tuple[dict, int]:
    """Check the requested anime and start its download in the background."""
    anime_id = params.get("anime_id")
    try:
        start_episode = _parse_episode(params.get("start_episode"))
        end_episode = _parse_episode(params.get("end_episode"))
        custom_path = _resolve_custom_path(params.get("custom_path"))
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}, 400

    url = f"{animeunity_url}/anime/{anime_id}"
    available, message, anime_name, n_episodes = check_resource_availability(url)
    if not available:
        return {"status": "error", "message": message}, 404

    logger.info(
        "Resource available for anime_id %s: %s with %s episodes.",
        anime_id,
        anime_name,
        n_episodes,
    )

    status_params = {
        "url": url,
        "start_episode": start_episode,
        "end_episode": end_episode,
        "custom_path": custom_path,
    }

    with downloads_lock:
        existing = downloads_status.get(anime_id)
        if existing and existing.get("status") in ACTIVE_STATUSES:
            return {
                "status": "error",
                "message": "Download già in corso per questo anime",
                "anime_id": anime_id,
            }, 400

        downloads_status[anime_id] = {
            "anime_id": anime_id,
            "anime_name": anime_name,
            "status": "queued",
            "message": None,
            "params": status_params,
            "started_at": None,
            "finished_at": None,
            "episodes": {},
            "total_episodes": n_episodes,
            "overall_percent": 0.0,
        }

    call_params = {
        "url": url,
        "episodes_range": (start_episode, end_episode),
        "custom_path": custom_path,
    }
    asyncio.run_coroutine_threadsafe(
        _run_download(anime_id, call_params, _make_hooks(anime_id)),
        background_loop,
    )

    logger.info("Download of anime_id %s taken over: %s", anime_id, status_params)
    return {
        "status": "success",
        "message": "Richiesta presa in carico",
        "anime_id": anime_id,
        "params": status_params,
    }, 200


def pause_all_downloads() -> tuple[dict, int]:
    """Pause all the queued and running downloads."""
    with downloads_lock:
        for info in downloads_status.values():
            if info.get("status") in ("running", "queued"):
                info["paused"] = True
                info["prev_status"] = info.get("status")
                info["status"] = "paused"
    return {"status": "success", "message": "Tutti i download messi in pausa"}, 200


def resume_all_downloads() -> tuple[dict, int]:
    """Resume all the paused downloads."""
    with downloads_lock:
        for info in downloads_status.values():
            if info.get("status") == "paused":
                info["paused"] = False
                previous = info.pop("prev_status", None)
                info["status"] = previous if previous in ("queued", "running") else "running"
    return {"status": "success", "message": "Tutti i download ripresi"}, 200


def cancel_all_downloads() -> tuple[dict, int]:
    """Cancel all the active downloads."""
    with downloads_lock:
        for info in downloads_status.values():
            if info.get("status") in ACTIVE_STATUSES:
                info["cancelled"] = True
                info["status"] = "cancelled"
                info["finished_at"] = time.time()
    return {"status": "success", "message": "Tutti i download annullati"}, 200


def cancel_download(anime_id: str) -> tuple[dict, int]:
    """Cancel a single download."""
    with downloads_lock:
        info = downloads_status.get(anime_id)
        if not info:
            return {"status": "error", "message": "Download non trovato"}, 404
        if info.get("status") in FINISHED_STATUSES:
            return {"status": "error", "message": "Download già terminato"}, 400
        info["cancelled"] = True
        info["status"] = "cancelled"
        info["finished_at"] = time.time()
    return {"status": "success", "message": f"Download {anime_id} annullato"}, 200


def remove_download(anime_id: str) -> tuple[dict, int]:
    """Remove a download from the list, unless it is still active."""
    with downloads_lock:
        info = downloads_status.get(anime_id)
        if not info:
            return {"status": "error", "message": "Download non trovato"}, 404
        if info.get("status") in ACTIVE_STATUSES:
            return {
                "status": "error",
                "message": "Impossibile rimuovere un task ancora attivo",
            }, 400
        del downloads_status[anime_id]
    return {"status": "success", "message": f"Download {anime_id} rimosso"}, 200


def cleanup_finished_downloads() -> tuple[dict, int]:
    """Remove all the downloads that are completed, failed or cancelled."""
    with downloads_lock:
        removed = [
            anime_id
            for anime_id, info in downloads_status.items()
            if info.get("status") in FINISHED_STATUSES
        ]
        for anime_id in removed:
            del downloads_status[anime_id]
    return {
        "status": "success",
        "message": f"Rimosse {len(removed)} task",
        "removed": removed,
    }, 200


def get_download_status(anime_id: str) -> tuple[dict, int]:
    """Return the status of a single download."""
    with downloads_lock:
        info = copy.deepcopy(downloads_status.get(anime_id))
    if not info:
        message = "Download non trovato"
        logger.error(message)
        return {"status": "error", "message": message}, 404
    return {"status": "success", "data": info}, 200


def list_downloads() -> tuple[dict, int]:
    """Return the status of all the downloads."""
    with downloads_lock:
        items = copy.deepcopy(list(downloads_status.values()))
    return {"status": "success", "data": items}, 200
