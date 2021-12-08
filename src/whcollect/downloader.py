from pathlib import Path

import aiofiles
from aiohttp import ClientSession, ClientTimeout
from yarl import URL


async def download_wallpaper(
    url: URL | str,
    location: Path | str,
    *,
    session: ClientSession | None = None,
    timeout: ClientTimeout | float = 90
) -> Path:
    """Download a wallpaper from a URL and save it to a directory.

    If a session is provided, it will be reused; otherwise a new session will be
    created with the specified/default timeout.
    """
    # Normalize the required arguments.
    url = URL(url)
    location = Path(location)

    if isinstance(session, ClientSession):
        close_session = False
    else:
        if not isinstance(timeout, ClientTimeout):
            timeout = ClientTimeout(timeout)
        session = ClientSession(timeout=timeout)
        close_session = True

    async with session.get(url, raise_for_status=True) as resp:
        file_name = url.path.split("/")[-1]
        full_path = location / file_name
        async with aiofiles.open(full_path, "wb") as f:
            await f.write(await resp.read())

    # Close the session only if it was just created.
    if close_session:
        await session.close()

    return full_path
