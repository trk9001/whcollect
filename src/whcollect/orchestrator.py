import asyncio
import atexit
import logging
from asyncio import AbstractEventLoop, Queue, Task
from collections.abc import Iterable
from pathlib import Path
from typing import Any, ClassVar

from aiohttp import ClientSession, ClientTimeout
from yarl import URL

from .downloader import download_wallpaper
from .requests import request_with_backoff

logger = logging.getLogger(__name__)

# Type alias for an asyncio-compatible event loop.
EventLoop = AbstractEventLoop


class Orchestrator:
    """Orchestrator to manage the downloading and saving of wallpapers.

    Attributes:
        API_BASE_URL: Wallhaven API URL.
        DEFAULT_REQUEST_TIMEOUT: Self-explanatory.
        DEFAULT_MAX_DOWNLOAD_WORKERS: Maximum number of workers that will
            concurrently consume queued wallpapers for downloading.
        username: Wallhaven username.
        collections: Set of wallhaven collection IDs or names.
        api_key: Wallhaven API key.
        save_location: Directory to save the collections in.
        create_dirs: Whether to create per-collection directories.
    """

    API_BASE_URL: ClassVar[URL] = URL("https://wallhaven.cc/api/v1")
    DEFAULT_REQUEST_TIMEOUT: ClassVar[float] = 90.0  # Seconds.
    DEFAULT_MAX_DOWNLOAD_WORKERS: ClassVar[int] = 4

    # Instance variables.
    username: str
    collections: set[str]
    api_key: str
    save_location: Path
    create_dirs: bool
    url_params: dict[str, str]
    _loop: EventLoop
    _session: ClientSession
    _valid_collections: set[tuple[str, str]]
    _download_queue: Queue[tuple[URL | str, Path | str]]

    def __init__(
        self,
        username: str,
        collections: Iterable[str],
        api_key: str,
        save_location: Path | str | None = None,
        flat: bool = False,
        *,
        loop: EventLoop | None = None,
        session: ClientSession | None = None,
        **extra_params,
    ):
        self.username = username
        self.collections = set(collections)
        self.api_key = api_key

        if save_location is None:
            self.save_location = Path.cwd()
        else:
            self.save_location = Path(save_location)
            if not self.save_location.is_dir():
                raise NotADirectoryError(f"Directory must exist: {self.save_location}")
        self.create_dirs = not flat

        # Set the asyncio event loop up.
        if loop is None:
            self._loop = asyncio.new_event_loop()
            atexit.register(self._close_loop)
        else:
            if not isinstance(loop, AbstractEventLoop):
                raise TypeError("'loop' must be an asyncio-compatible event loop")
            self._loop = loop

        # Set the HTTP client session up.
        if session is None:
            self._session = self._loop.run_until_complete(self._create_client_session())
            # The registered functions are invoked in the reverse order, so `_close_session`
            # must be registered after `_close_loop` if both are registered.
            atexit.register(self._close_session)
        else:
            if not isinstance(session, ClientSession):
                raise TypeError(
                    "'session' must be an instance of aiohttp.ClientSession"
                )
            self._session = session

        self.url_params = extra_params

    async def _create_client_session(self) -> ClientSession:
        """Create the default HTTP client session to use for requests."""
        session = ClientSession(
            headers={"X-API-Key": self.api_key},
            timeout=ClientTimeout(self.DEFAULT_REQUEST_TIMEOUT),
            raise_for_status=True,
        )
        return session

    @property
    def session(self) -> ClientSession:
        return self._session

    @property
    def loop(self) -> EventLoop:
        return self._loop

    async def fetch_and_normalize_collections(self) -> set[tuple[str, str]]:
        """Fetch and validate collection IDs."""
        url = self.API_BASE_URL / "collections" / self.username
        logger.info(f"GET {url}")
        async with self.session.get(url) as resp:
            obj: dict = await resp.json()

        if error := obj.get("error"):
            raise ValueError(f"Error: {error}")

        self._valid_collections = set()
        for item in obj["data"]:  # type: dict[str, Any]
            label = item["label"]
            id_ = str(item["id"])
            if label in self.collections or id_ in self.collections:
                self._valid_collections.add((id_, label))

        logger.info(f"Validated collections: {self._valid_collections}")
        return self._valid_collections

    def construct_wallpaper_destination(self, collection_label: str) -> Path:
        """Construct the final save location using the collection name."""
        if self.create_dirs:
            save_path = self.save_location / collection_label
            save_path.mkdir(exist_ok=True)
            return save_path

        return self.save_location

    async def fetch_and_queue_wallpapers_for_downloading(self) -> None:
        """Fetch wallpapers and queue downloads."""
        base_url = self.API_BASE_URL / "collections" / self.username

        self._download_queue = Queue()

        for collection_id, collection_label in self._valid_collections:
            url = base_url / collection_id
            save_location = self.construct_wallpaper_destination(collection_label)
            params = self.url_params.copy()
            page = 1

            while True:
                params["page"] = str(page)

                logger.info(f"GET {url}{f' (params: {params})' if params else ''}")
                resp = await request_with_backoff(
                    self.session, "GET", url, params=params
                )
                async with resp:
                    obj: dict = await resp.json()

                if error := obj.get("error"):
                    raise ValueError(f"Error: {error}")

                for item in obj["data"]:  # type: dict[str, Any]
                    queue_item = (item["path"], save_location)
                    await self._download_queue.put(queue_item)
                    logger.info(f"Added to download queue: {queue_item}")

                if page >= obj["meta"]["last_page"]:
                    break

                page += 1

        logger.info("Finished queueing wallpapers for downloading")

    async def download_wallpapers(self, *, max_workers: int | None = None) -> None:
        """Download queued wallpapers."""

        async def worker(name: str) -> None:
            while True:
                downloader_args = await self._download_queue.get()
                logger.info(f"Worker<{name}>: Gotten from queue: {downloader_args}")
                await download_wallpaper(*downloader_args)
                self._download_queue.task_done()

        tasks: list[Task] = []
        max_workers = max_workers or self.DEFAULT_MAX_DOWNLOAD_WORKERS
        for i in range(max_workers):
            tasks.append(asyncio.create_task(worker(name=f"#{i+1}")))

        await self._download_queue.join()
        logger.info("All download queue items have been processed")

        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _close_session(self) -> None:
        """Cleanup function for atexit to close the HTTP client session."""
        if not self._session.closed:
            self._loop.run_until_complete(self._session.close())

    def _close_loop(self) -> None:
        """Cleanup function for atexit to close the event loop."""
        if self._loop.is_running():
            self._loop.close()
