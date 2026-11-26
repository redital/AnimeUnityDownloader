"""Utilities for handling file downloads with progress tracking."""

from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote

from .config import (
    DOWNLOAD_WORKERS,
    LARGE_FILE_CHUNK_SIZE,
    TASK_COLOR,
    THRESHOLDS,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from requests import Response
    from rich.progress import Progress

PAUSE_POLL_SECONDS = 0.5
MANAGER_POLL_SECONDS = 0.01


class DownloadCancelledError(Exception):
    """Raised inside a download worker when the download has been cancelled."""


@dataclass(frozen=True)
class DownloadHooks:
    """Optional callbacks that let a front-end follow and control downloads.

    Attributes:
        on_start: Called once with the anime name and the number of episodes.
        on_progress: Called with the episode index and its completion percentage.
        is_paused: Polled between chunks; the download waits while it is true.
        is_cancelled: Polled between chunks; when true the download is aborted.

    """

    on_start: Callable[[str | None, int], None] | None = None
    on_progress: Callable[[int, float], None] | None = None
    is_paused: Callable[[], bool] | None = None
    is_cancelled: Callable[[], bool] | None = None


class TaskInfo(tuple):
    """Progress handles of a download, unpackable as (job_progress, task, overall).

    The optional hooks and the episode index are exposed as attributes, so code
    that unpacks the three handles (e.g. the HLS downloader) is not affected.
    """

    def __new__(
        cls,
        handles: tuple,
        hooks: DownloadHooks | None = None,
        episode_idx: int | None = None,
    ) -> TaskInfo:
        obj = super().__new__(cls, handles)
        obj.hooks = hooks
        obj.episode_idx = episode_idx
        return obj


def remove_special_characters(input_string: str) -> str:
    """Remove special characters from the input string."""
    return re.sub(r"[^a-zA-Z0-9_.-]", "", input_string)


def get_episode_filename(
    download_link: str,
    response: Response | None = None,
) -> str | None:
    """Extract a sanitized .mp4 filename from response headers or URL."""
    if response is not None:
        disposition = response.headers.get("Content-Disposition", "")
        match = re.search(
            r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?',
            disposition,
            re.IGNORECASE,
        )
        if match:
            cleaned = remove_special_characters(unquote(match.group(1).strip()))
            if cleaned.lower().endswith(".mp4"):
                return cleaned

        final_path_name = unquote(response.url.split("?")[0].rstrip("/").split("/")[-1])
        cleaned_url_name = remove_special_characters(final_path_name)
        if cleaned_url_name.lower().endswith(".mp4"):
            return cleaned_url_name

    if download_link and "=" in download_link:
        filename = unquote(download_link.split("=")[-1])
        cleaned = remove_special_characters(filename)
        if cleaned.lower().endswith(".mp4"):
            return cleaned

    return None


def get_chunk_size(file_size: int) -> int:
    """Determine the optimal chunk size based on the file size."""
    for threshold, chunk_size in THRESHOLDS:
        if file_size < threshold:
            return chunk_size

    return LARGE_FILE_CHUNK_SIZE


def wait_while_paused(hooks: DownloadHooks | None) -> None:
    """Block while the download is paused; raise if it has been cancelled."""
    if hooks is None:
        return
    while True:
        if hooks.is_cancelled is not None and hooks.is_cancelled():
            raise DownloadCancelledError
        if hooks.is_paused is None or not hooks.is_paused():
            return
        time.sleep(PAUSE_POLL_SECONDS)


def notify_progress(
    hooks: DownloadHooks | None,
    episode_idx: int | None,
    percentage: float,
) -> None:
    """Report the progress of an episode to the optional progress hook."""
    if hooks is not None and hooks.on_progress is not None and episode_idx is not None:
        hooks.on_progress(episode_idx, percentage)


def save_file_with_progress(
    response: Response,
    final_path: str,
    task_info: tuple,
) -> None:
    """Save a file to the specified path while tracking and updating progress."""
    job_progress, task, overall_task = task_info
    hooks = getattr(task_info, "hooks", None)
    episode_idx = getattr(task_info, "episode_idx", None)
    file_size = int(response.headers.get("Content-Length", -1))
    chunk_size = get_chunk_size(file_size)
    total_downloaded = 0

    try:
        with Path(final_path).open("wb") as file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                wait_while_paused(hooks)
                if chunk:
                    file.write(chunk)
                    total_downloaded += len(chunk)
                    if file_size > 0:
                        progress_percentage = (total_downloaded / file_size) * 100
                        job_progress.update(task, completed=progress_percentage)
                        notify_progress(hooks, episode_idx, progress_percentage)
    except DownloadCancelledError:
        Path(final_path).unlink(missing_ok=True)
        raise

    job_progress.update(task, completed=100, visible=False)
    job_progress.advance(overall_task)
    notify_progress(hooks, episode_idx, 100.0)


def manage_running_tasks(futures: dict, job_progress: Progress) -> None:
    """Manage the status of running tasks and update their progress."""
    while futures:
        for future in list(futures.keys()):
            if future.running() or future.done():
                task = futures.pop(future)
                if not future.done():
                    job_progress.update(task, visible=True)
        if futures:
            time.sleep(MANAGER_POLL_SECONDS)


def check_workers(futures: list) -> None:
    """Log the failed downloads and raise if any of them has been cancelled."""
    cancelled = False
    for future in futures:
        exc = future.exception()
        if isinstance(exc, DownloadCancelledError):
            cancelled = True
        elif exc is not None:
            logging.error("Download worker failed: %s", exc, exc_info=exc)

    if cancelled:
        raise DownloadCancelledError


def run_in_parallel(
    func: callable,
    items: list,
    job_progress: Progress,
    *args: tuple,
    hooks: DownloadHooks | None = None,
) -> None:
    """Execute a function in parallel for a list of items, updating progress."""
    num_items = len(items)
    futures = {}
    all_futures = []

    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
        overall_task = job_progress.add_task(
            f"[{TASK_COLOR}]Progress", total=num_items, visible=True,
        )
        for indx, item in enumerate(items):
            task = job_progress.add_task(
                f"[{TASK_COLOR}]Episode {indx + 1}/{num_items}",
                total=100,
                visible=False,
            )
            task_info = TaskInfo((job_progress, task, overall_task), hooks, indx)
            future = executor.submit(func, item, *args, task_info)
            futures[future] = task
            all_futures.append(future)
            manage_running_tasks(futures, job_progress)

    check_workers(all_futures)
