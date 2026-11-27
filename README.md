# AnimeUnity Downloader

> A Python-based tool for downloading anime series from AnimeUnity, featuring progress tracking for each episode. It efficiently extracts video URLs and manages downloads.

![Demo](https://github.com/Lysagxra/AnimeUnityDownloader/blob/8e274bdfb71f8fc714fa02322ec2b3eda61cce53/assets/demo.png)

## Features

- Downloads multiple episodes concurrently.
- Supports [batch downloading](https://github.com/Lysagxra/AnimeUnityDownloader?tab=readme-ov-file#batch-download) via a list of URLs.
- Supports downloading a [specified range of episodes](https://github.com/Lysagxra/AnimeUnityDownloader?tab=readme-ov-file#single-anime-download).
- Supports [custom download location](https://github.com/Lysagxra/AnimeUnityDownloader/tree/main?tab=readme-ov-file#file-download-location).
- Tracks download progress with a progress bar.
- Automatically creates a directory structure for organized storage.

## Dependencies

- Python 3
- `requests` - for HTTP requests
- `BeautifulSoup` (bs4) - for HTML parsing
- `rich` - for progress display in terminal
- `fake_useragent` - for generating fake user agents for web scraping
- `httpx` - for making asynchronous HTTP requests
- `ffmpeg` - for downloading episodes available only as HLS streams (e.g. `brew install ffmpeg` on macOS)

<details>

<summary>Show directory structure</summary>

```
project-root/
├── helpers/
│ ├── crawlers/
│ │ ├── crawler.py        # Module for crawling tasks
│ │ └── crawler_utils.py  # Utilities for extracting media download links
│ ├── config.py           # Manages constants and settings used across the project
│ ├── download_utils.py   # Utilities for managing the download process
│ ├── file_utils.py       # Utilities for managing file operations
│ ├── general_utils.py    # Miscellaneous utility functions
│ └── progress_utils.py   # Tools for progress tracking and reporting
├── anime_downloader.py   # Module for downloading anime episodes
├── main.py               # Main script to run the downloader
└── URLs.txt              # Text file containing anime URLs
```

</details>

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Lysagxra/AnimeUnityDownloader.git
```

2. Navigate to the project directory:

```bash
cd AnimeUnityDownloader
```

3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Single Anime Download

To download a single anime, you can use the `anime_downloader.py` script.

### Usage

Run the script followed by the anime URL you want to download:

```bash
python3 anime_downloader.py <anime_url> [--start <start_episode>] [--end <end_episode>] [--episodes <episode_list>]
```

- `<anime_url>`: The URL of the anime series.
- `--start <start_episode>`: The starting episode number (optional).
- `--end <end_episode>`: The ending episode number (optional).
- `--episodes <episode_list>`: Comma or space separated list of specific episode numbers to download.

### Examples

To download all episodes:
```bash
python3 anime_downloader.py https://www.animeunity.to/anime/1517-yuru-yuri
```

To download a specific range of episodes (e.g., episodes 5 to 10):
```bash
python3 anime_downloader.py https://www.animeunity.to/anime/1517-yuru-yuri --start 5 --end 10
```

To download episodes starting from a specific episode:
```bash
python3 anime_downloader.py https://www.animeunity.to/anime/1517-yuru-yuri --start 5
```
In this case, the script will download all episodes starting from the `--start` episode to the last episode.

To download episodes up to a certain episode:
```bash
python3 anime_downloader.py https://www.animeunity.to/anime/1517-yuru-yuri --end 10
```
In this case, the script will download all episodes starting from the first episode to the `--end` episode.

To download only specific episodes (e.g., episodes 3, 7, 12, and 15) add the `--episodes` flag and the list of episodes separated by comma or space or both

```bash
python3 anime_downloader.py https://www.animeunity.to/anime/1517-yuru-yuri --episodes 3,7,12,15
python3 anime_downloader.py https://www.animeunity.to/anime/1517-yuru-yuri --episodes 3 7 12 15
```

This is useful when you already have some episodes and only need to download the missing ones, avoiding re-downloading an entire range.

## Batch Download

### Usage

1. Create a `URLs.txt` file in the project root and list the anime URLs you want to download.

- Example of `URLs.txt`:

```
https://www.animeunity.to/anime/1517-yuru-yuri
https://www.animeunity.to/anime/3871-chainsaw-man
https://www.animeunity.to/anime/2598-made-in-abyss
```

- Ensure that each URL is on its own line without any extra spaces.
- You can add as many URLs as you need, following the same format.

2. Run the main script via the command line:

```bash
python3 main.py
```

## API

A small [Flask](https://flask.palletsprojects.com/) application exposes the downloader through an HTTP API, so that downloads can be started and controlled from other programs.

```bash
pip install -r requirements.txt
python3 flask_app.py
```

The API listens on `http://localhost:5000`. It has no authentication: do not expose it to untrusted networks.

- `GET /download/<anime_id>?start_episode=&end_episode=&episodes=&custom_path=` starts a download. `episodes` is a comma-separated list such as `1,3,5-8` and can be combined with a range; without any of them the whole anime is downloaded. Several downloads of the same anime can run together as long as they do not share episodes: each one has a `job_id` such as `<anime_id>:1-3`.
- `GET /download-status/<anime_id>` and `GET /download-statuses` report the progress. The status of a single job is also available with `?job_id=`; an anime with several jobs returns the list of all of them.
- `POST /downloads/pause`, `/downloads/resume`, `/downloads/cancel` and `/downloads/cleanup` act on all the downloads.
- `POST /download/<job_id>/cancel` and `/download/<job_id>/remove` act on a single one (the anime id works too when the anime has a single job).

The application is configured through environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_HOST` | `0.0.0.0` | Address to bind to |
| `FLASK_PORT` | `5000` | Port to listen on |
| `FLASK_DEBUG` | `false` | Enable Flask debug mode |
| `SSL_CONTEXT` | unset | Set to `adhoc` to serve over HTTPS (requires the `cryptography` package) |
| `ANIMEUNITY_URL` | `https://www.animeunity.to` | Base URL of AnimeUnity |
| `DOWNLOAD_ROOT` | working directory | Folder under which downloads may be saved. A custom download path, relative or absolute, must be inside it: set it to the mount point of a network share to save there |

## Web Interface

A web page served by the same application lets you start downloads by anime ID, follow their progress, and pause, resume, cancel or clear them from the browser.

```bash
python3 flask_app.py
```

Then open `http://localhost:5000` (`http://localhost:8222` when using [Docker](#docker)). The page uses the [API](#api), so it is configured in the same way and the same warning about authentication applies.

## Docker

The API can be run in a container:

```bash
docker compose up -d --build
```

The service is then available on `http://localhost:8222`. Downloads are saved in `./Downloads`: to save them on a network share, set `MEDIA_DIRECTORY` to its mount point on the host. These settings, together with the variables of the [API](#api), can be changed with a `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST_PORT` | `8222` | Port exposed on the host |
| `MEDIA_DIRECTORY` | `./Downloads` | Host folder mounted as the download folder |

## File Download Location

If the `--custom-path <custom_path>` argument is used, the downloaded files will be saved in `<custom_path>/Downloads`. Otherwise, the files will be saved in a `Downloads` folder created within the script's directory

### Usage

```bash
python3 main.py --custom-path <custom_path>
```

### Example

```bash
python3 main.py --custom-path /path/to/external/drive
```
