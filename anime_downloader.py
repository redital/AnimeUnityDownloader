"""Module to download anime episodes from a given AnimeUnity URL.

It extracts the anime ID, formats the anime name, retrieves episode URLs, and
downloads episodes concurrently.

Usage:
    - Run the script with the URL of the anime page as a command-line argument.
    - It will create a directory structure in the 'Downloads' folder based on
      the anime name where each episode will be downloaded.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from rich.live import Live

from src.config import (
    DEFAULT_LANGUAGE,
    DOWNLOAD_QUALITIES,
    HTTP_STATUS_OK,
    parse_arguments,
)
from src.crawler.crawler import Crawler
from src.download_utils import (
    get_episode_filename,
    remove_special_characters,
    run_in_parallel,
    save_file_with_progress,
)
from src.file_utils import create_download_directory
from src.general_utils import (
    clear_terminal,
    fetch_page_httpx,
    prepare_cloudscraper_session,
)
from src.progress_utils import create_progress_bar, create_progress_table


def download_episode(
    download_link: str,
    download_path: str,
    episode_number: str,
    task_info: tuple,
    retries: int = 4,
) -> None:
    """Download an episode from /episode-videos/{id}/download with quality fallback."""
    parsed_download_link = urlparse(download_link)
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,video/mp4,*/*;q=0.8",
        "Referer": f"{parsed_download_link.scheme}://{parsed_download_link.netloc}/",
    }

    for attempt in range(retries):
        try:
            scraper = prepare_cloudscraper_session()
            response = None

            for quality in DOWNLOAD_QUALITIES:
                res = scraper.get(
                    f"{download_link}?quality={quality}",
                    stream=True,
                    headers=headers,
                    timeout=20,
                    allow_redirects=True,
                )

                content_type = res.headers.get("Content-Type", "").lower()
                if (
                    res.status_code == HTTP_STATUS_OK
                    and "text/html" not in content_type
                ):
                    response = res
                    break

                logging.warning(
                    "Episode %s (%sp) returned status %s (%s)",
                    episode_number,
                    quality,
                    res.status_code,
                    content_type,
                )
                res.close()

            if response is None:
#                pass
                msg = f"No valid MP4 stream found for episode {episode_number}"
                raise requests.RequestException(msg)

        except requests.RequestException as req_err:
            logging.warning(
                "Attempt %d/%d failed for episode %s: %s",
                attempt + 1,
                retries,
                episode_number,
                req_err,
            )
            if attempt < retries - 1:
                time.sleep(10 * (attempt + 1) + random.uniform(1, 2))  # noqa: S311

        else:
            with response:
                filename = get_episode_filename(
                    download_link,
                    response,
                ) or get_hls_episode_filename(download_path, episode_number)
                save_file_with_progress(
                    response,
                    Path(download_path) / filename,
                    task_info,
                )
            break


def get_hls_episode_filename(download_path: str, episode_number: str) -> str:
    """Build the file name of an episode downloaded from its HLS stream."""
    anime_name = remove_special_characters(Path(download_path).name.replace(" ", "_"))
    return f"{anime_name}_Ep_{episode_number.zfill(2)}.mp4"


def process_video_url(
    video_url: str,
    download_path: str,
    task_info: tuple,
) -> None:
    """Download an episode from its direct video URL."""
    episode_number = str(task_info[-1])
    download_episode(video_url, download_path, episode_number, task_info)


def download_anime(anime_name: str, video_urls: list[str], download_path: str, progress_callback: callable | None = None) -> None:
    """Download episodes of a specified anime from provided video URLs."""
    job_progress = create_progress_bar()
    progress_table = create_progress_table(anime_name, job_progress)

    with Live(progress_table, refresh_per_second=10):
        run_in_parallel(process_video_url, video_urls, job_progress, download_path, extra_info=progress_callback)


async def process_anime_download(
    url: str,
    episodes_range: tuple = (None, None),
    episodes: list[int] | None = None,
    custom_path: str | None = None,
    progress_callback: callable | dict | None = None,
    start_episode: int | None = None,
    end_episode: int | None = None,
    episode_numbers: list[int] | None = None,
) -> None:
    """Process the download of an anime from the specified URL."""
    if start_episode is not None or end_episode is not None:
        episodes_range = (start_episode, end_episode)
    if episode_numbers is not None and episodes is None:
        episodes = episode_numbers

    soup = await asyncio.to_thread(fetch_page_httpx, url)
    crawler = await asyncio.to_thread(
        Crawler,
        url=url,
        episodes_range=episodes_range,
        episodes=episodes,
        soup=soup,
    )
    anime_name = crawler.extract_anime_name(soup, url)
    download_path = create_download_directory(anime_name, custom_path=custom_path)
    video_urls = await crawler.collect_video_urls()

    cb = progress_callback.get("progress_cb") if isinstance(progress_callback, dict) else progress_callback

    if callable(cb):
        cb("__total__", len(video_urls))
        cb("__anime_name__", anime_name)

    await asyncio.to_thread(
        download_anime,
        anime_name,
        video_urls,
        download_path,
        progress_callback=progress_callback,
    )


async def main() -> None:
    """Execute the script to download anime episodes from a given AnimeUnity URL."""
    clear_terminal()
    args = parse_arguments()
    episodes = parse_episodes_list(args.episodes)
    await process_anime_download(
        args.url,
        episodes_range=(args.start, args.end),
        episodes=episodes,
        custom_path=args.custom_path,
    )


if __name__ == "__main__":
    asyncio.run(main())
