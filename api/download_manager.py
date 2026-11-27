"""Management of the downloads started through the API.

Downloads run on a dedicated asyncio event loop living in a background thread.
Their state is kept in memory, indexed by job id (the anime id plus the
selected episodes), and protected by a lock.
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

# In-memory tracking of the downloads, indexed by `job_id`
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


def _parse_episodes_list(value: str | None, n_episodes: int) -> list[int]:
    """Convert a list such as "1,3,5-8" into episode numbers."""
    numbers: list[int] = []
    for token in (value or "").split(","):
        text = token.strip()
        if not text:
            continue
        first, _, last = text.partition("-")
        try:
            low = int(first)
            high = int(last) if last else low
        except ValueError as exc:
            msg = f"Episodio non valido: {text!r}"
            raise ValueError(msg) from exc
        if low < 1 or high > n_episodes or low > high:
            msg = f"Episodi {text!r} non validi: devono essere tra 1 e {n_episodes}"
            raise ValueError(msg)
        numbers.extend(range(low, high + 1))
    return numbers


def _build_selection(
    start_episode: int | None,
    end_episode: int | None,
    episodes: str | None,
    n_episodes: int,
) -> list[int] | None:
    """Return the sorted episodes to download, or None for the whole anime."""
    if start_episode is None and end_episode is None and not episodes:
        return None

    selected = set(_parse_episodes_list(episodes, n_episodes))
    if start_episode is not None or end_episode is not None:
        low = start_episode if start_episode is not None else 1
        high = end_episode if end_episode is not None else n_episodes
        if low < 1 or low > n_episodes:
            msg = f"L'episodio iniziale deve essere compreso tra 1 e {n_episodes}"
            raise ValueError(msg)
        if high < 1 or high > n_episodes:
            msg = f"L'episodio finale deve essere compreso tra 1 e {n_episodes}"
            raise ValueError(msg)
        if low > high:
            msg = "L'episodio iniziale non può essere maggiore di quello finale"
            raise ValueError(msg)
        selected.update(range(low, high + 1))
    return sorted(selected)


def _selection_label(selection: list[int] | None) -> str:
    """Describe a selection in a compact form, e.g. "1-3,5"."""
    if selection is None:
        return "all"
    groups: list[list[int]] = []
    for number in selection:
        if groups and number == groups[-1][1] + 1:
            groups[-1][1] = number
        else:
            groups.append([number, number])
    return ",".join(str(a) if a == b else f"{a}-{b}" for a, b in groups)


def _active_episodes(anime_id: str) -> set[int] | None:
    """Return the episodes of an anime already being downloaded.

    None means that an active job is downloading the whole anime. To be called
    with `downloads_lock` held.
    """
    taken: set[int] = set()
    for info in downloads_status.values():
        if info["anime_id"] != anime_id or info["status"] not in ACTIVE_STATUSES:
            continue
        if info["selection"] is None:
            return None
        taken.update(info["selection"])
    return taken


def _find_jobs(key: str) -> list[str]:
    """Return the ids of the jobs matching a job id or an anime id.

    To be called with `downloads_lock` held.
    """
    if key in downloads_status:
        return [key]
    return [
        job_id for job_id, info in downloads_status.items() if info["anime_id"] == key
    ]


def _make_hooks(job_id: str) -> DownloadHooks:
    """Build the hooks that connect a download to its entry in `downloads_status`."""

    def on_start(anime_name: str | None, total_episodes: int) -> None:
        with downloads_lock:
            info = downloads_status.get(job_id)
            if info is None:
                return
            if anime_name:
                info["anime_name"] = anime_name
            info["total_episodes"] = total_episodes

    def on_progress(episode_idx: int, percentage: float) -> None:
        with downloads_lock:
            info = downloads_status.get(job_id)
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
            return bool(downloads_status.get(job_id, {}).get(name, False))

    return DownloadHooks(
        on_start=on_start,
        on_progress=on_progress,
        is_paused=lambda: get_flag("paused"),
        is_cancelled=lambda: get_flag("cancelled"),
    )


async def _run_download(job_id: str, call_params: dict, hooks: DownloadHooks) -> None:
    """Run a download job and record its final status."""
    with downloads_lock:
        info = downloads_status[job_id]
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
        logger.exception("Error while downloading job %s", job_id)
        final_status, message = "failed", str(exc)
    else:
        final_status, message = "completed", None

    with downloads_lock:
        info = downloads_status.get(job_id)
        if info is None:
            return
        info["status"] = final_status
        if message is not None:
            info["message"] = message
        info["finished_at"] = info.get("finished_at") or time.time()


def start_download(params: dict) -> tuple[dict, int]:
    """Check the requested anime and start its download in the background.

    The episodes can be given as a range (`start_episode`, `end_episode`), as a
    list (`episodes`, e.g. "1,3,5-8") or both. Several downloads of the same
    anime can run together, as long as they do not share episodes.
    """
    anime_id = params.get("anime_id")
    episodes_text = params.get("episodes")
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

    try:
        selection = _build_selection(
            start_episode,
            end_episode,
            episodes_text,
            n_episodes,
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc), "anime_id": anime_id}, 400

    logger.info(
        "Resource available for anime_id %s: %s with %s episodes.",
        anime_id,
        anime_name,
        n_episodes,
    )
    options = {
        "url": url,
        "start_episode": start_episode,
        "end_episode": end_episode,
        "episodes": episodes_text,
        "custom_path": custom_path,
    }
    return _launch_job(anime_id, anime_name, n_episodes, selection, options)


def _launch_job(
    anime_id: str,
    anime_name: str | None,
    n_episodes: int,
    selection: list[int] | None,
    options: dict,
) -> tuple[dict, int]:
    """Register a download job and start it, unless its episodes are taken."""
    with downloads_lock:
        taken = _active_episodes(anime_id)
        skipped: list[int] = []
        if selection is None:
            if taken is None or taken:
                return {
                    "status": "error",
                    "message": "Download già in corso per questo anime",
                    "anime_id": anime_id,
                }, 400
        else:
            remaining = [] if taken is None else [e for e in selection if e not in taken]
            if not remaining:
                return {
                    "status": "error",
                    "message": "Tutti gli episodi richiesti sono già in coda oppure in download",
                    "anime_id": anime_id,
                }, 409
            skipped = [e for e in selection if e not in remaining]
            selection = remaining

        job_id = f"{anime_id}:{_selection_label(selection)}"
        downloads_status[job_id] = {
            "job_id": job_id,
            "anime_id": anime_id,
            "anime_name": anime_name,
            "status": "queued",
            "message": None,
            "params": options,
            "selection": selection,
            "started_at": None,
            "finished_at": None,
            "episodes": {},
            "total_episodes": len(selection) if selection else n_episodes,
            "overall_percent": 0.0,
        }

    # A plain range is passed as such; otherwise the explicit episodes are used
    use_list = bool(options["episodes"]) or bool(skipped)
    call_params = {
        "url": options["url"],
        "episodes_range": (
            (None, None)
            if use_list
            else (options["start_episode"], options["end_episode"])
        ),
        "episodes": selection if use_list else None,
        "custom_path": options["custom_path"],
    }
    asyncio.run_coroutine_threadsafe(
        _run_download(job_id, call_params, _make_hooks(job_id)),
        background_loop,
    )

    logger.info("Download %s taken over: %s", job_id, options)
    return {
        "status": "success",
        "message": "Richiesta presa in carico",
        "anime_id": anime_id,
        "job_id": job_id,
        "skipped_episodes": skipped,
        "params": options,
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


AMBIGUOUS_MESSAGE = "Più download per questo anime: indicare il job_id"


def cancel_download(key: str) -> tuple[dict, int]:
    """Cancel a single download, given its job id (or its anime id)."""
    with downloads_lock:
        matches = _find_jobs(key)
        if not matches:
            return {"status": "error", "message": "Download non trovato"}, 404
        if len(matches) > 1:
            return {"status": "error", "message": AMBIGUOUS_MESSAGE}, 400
        info = downloads_status[matches[0]]
        if info.get("status") in FINISHED_STATUSES:
            return {"status": "error", "message": "Download già terminato"}, 400
        info["cancelled"] = True
        info["status"] = "cancelled"
        info["finished_at"] = time.time()
    return {"status": "success", "message": f"Download {matches[0]} annullato"}, 200


def remove_download(key: str) -> tuple[dict, int]:
    """Remove a download from the list, unless it is still active."""
    with downloads_lock:
        matches = _find_jobs(key)
        if not matches:
            return {"status": "error", "message": "Download non trovato"}, 404
        if len(matches) > 1:
            return {"status": "error", "message": AMBIGUOUS_MESSAGE}, 400
        if downloads_status[matches[0]].get("status") in ACTIVE_STATUSES:
            return {
                "status": "error",
                "message": "Impossibile rimuovere un task ancora attivo",
            }, 400
        del downloads_status[matches[0]]
    return {"status": "success", "message": f"Download {matches[0]} rimosso"}, 200


def cleanup_finished_downloads() -> tuple[dict, int]:
    """Remove all the downloads that are completed, failed or cancelled."""
    with downloads_lock:
        removed = [
            job_id
            for job_id, info in downloads_status.items()
            if info.get("status") in FINISHED_STATUSES
        ]
        for job_id in removed:
            del downloads_status[job_id]
    return {
        "status": "success",
        "message": f"Rimosse {len(removed)} task",
        "removed": removed,
    }, 200


def get_download_status(
    anime_id: str,
    job_id: str | None = None,
) -> tuple[dict, int]:
    """Return the status of a download, given its job id or its anime id.

    When an anime id matches several jobs, the list of all of them is returned.
    """
    with downloads_lock:
        key = job_id if job_id in downloads_status else anime_id
        items = [copy.deepcopy(downloads_status[j]) for j in _find_jobs(key)]
    if not items:
        message = "Download non trovato"
        logger.error(message)
        return {"status": "error", "message": message}, 404
    return {"status": "success", "data": items[0] if len(items) == 1 else items}, 200


def list_downloads() -> tuple[dict, int]:
    """Return the status of all the downloads."""
    with downloads_lock:
        items = copy.deepcopy(list(downloads_status.values()))
    return {"status": "success", "data": items}, 200
