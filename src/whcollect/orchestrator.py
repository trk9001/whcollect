import asyncio
import atexit
from asyncio import AbstractEventLoop
from collections.abc import Iterable
from pathlib import Path
from typing import Any, ClassVar

from aiohttp import ClientSession, ClientTimeout
from yarl import URL

from .requests import request_with_backoff

# Type alias for an asyncio-compatible event loop.
EventLoop = AbstractEventLoop


class Orchestrator:
    """Orchestrator to manage the downloading and saving of wallpapers."""

    API_BASE_URL: ClassVar[URL] = URL("https://wallhaven.cc/api/v1")
    DEFAULT_REQUEST_TIMEOUT: ClassVar[float] = 90.0  # Seconds.

    # Instance variables.
    username: str
    collections: set[str]
    api_key: str
    save_location: Path
    create_dirs: bool
    _loop: EventLoop
    _session: ClientSession
    _url_params: dict[str, str]
    _valid_collections: set[tuple[str, str]]

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
    ):
        self.username = username
        self.collections = set(collections)
        self.api_key = api_key
        self.save_location = (
            Path.cwd() if save_location is None else Path(save_location)
        )
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

        self._url_params = {}

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

        return self._valid_collections

    async def fetch_wallpapers_and_queue_downloads(self) -> None:
        """Fetch wallpapers and queue downloads."""
        base_url = self.API_BASE_URL / "collections" / self.username

        for collection_id, collection_label in self._valid_collections:  # noqa
            url = base_url / collection_id
            params = self._url_params.copy()
            page = 1

            while True:
                params["page"] = str(page)

                resp = await request_with_backoff(
                    self.session, "GET", url, params=params
                )
                async with resp:
                    obj: dict = await resp.json()

                if error := obj.get("error"):
                    raise ValueError(f"Error: {error}")

                ...

                if page >= obj["meta"]["last_page"]:
                    break

                page += 1

    def _close_session(self) -> None:
        """Cleanup function for atexit to close the HTTP client session."""
        if not self._session.closed:
            self._loop.run_until_complete(self._session.close())

    def _close_loop(self) -> None:
        """Cleanup function for atexit to close the event loop."""
        if self._loop.is_running():
            self._loop.close()
