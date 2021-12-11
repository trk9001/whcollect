import asyncio
from asyncio import AbstractEventLoop
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from aiohttp import ClientSession, ClientTimeout
from yarl import URL

# Type alias for an asyncio-compatible event loop.
EventLoop = AbstractEventLoop


class Orchestrator:
    """Orchestrator to manage the downloading and saving of wallpapers."""

    API_BASE_URL: Final[URL] = URL("https://wallhaven.cc/api/v1")
    DEFAULT_REQUEST_TIMEOUT: Final[float] = 90.0  # Seconds.

    # Instance variables.
    username: str
    collections: Iterable[str]
    api_key: str
    save_location: Path
    create_dirs: bool
    _loop: EventLoop
    _session: ClientSession

    def __init__(
        self,
        username: str,
        collections: Iterable[str],
        api_key: str,
        save_location: Path | str | None = None,
        flat: bool = False,
        *,
        loop: EventLoop | None = None,
        session: ClientSession | None = None
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
        else:
            if not isinstance(loop, AbstractEventLoop):
                raise TypeError("'loop' must be an asyncio-compatible event loop")
            self._loop = loop

        # Set the HTTP client session up.
        if session is None:
            self._session = self._loop.run_until_complete(self._create_client_session())
        else:
            if not isinstance(session, ClientSession):
                raise TypeError(
                    "'session' must be an instance of aiohttp.ClientSession"
                )
            self._session = session

    @classmethod
    async def _create_client_session(cls) -> ClientSession:
        """Create the default HTTP client session to use for requests."""
        session = ClientSession(timeout=ClientTimeout(cls.DEFAULT_REQUEST_TIMEOUT))
        return session

    @property
    def session(self) -> ClientSession:
        return self._session

    @property
    def loop(self) -> EventLoop:
        return self._loop
