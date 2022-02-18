import asyncio
from collections.abc import Iterable
from typing import Literal

from aiohttp import ClientResponse, ClientResponseError, ClientSession
from yarl import URL

from .exceptions import BadResponse

# Literal type for supported HTTP methods.
HTTP_METHOD = Literal["GET"]

# Default max times to try a request (eight tries means 127 seconds between the
# first and last requests).
DEFAULT_MAX_TRIES = 8


async def request_with_backoff(
    session: ClientSession,
    method: HTTP_METHOD,
    url: URL | str,
    *,
    retry_for_statuses: Iterable[int] | None = None,
    max_tries: int = DEFAULT_MAX_TRIES,
    **kwargs,
) -> ClientResponse:
    """Make a request, retrying with exponential backoff if it fails.

    Example usage:
    ```
    async with aiohttp.ClientSession(raise_for_status=True) as session:
        response = await request_with_backoff(session, "GET", "example.com")
        async with response:
            obj = await response.text()
    ```
    """
    if retry_for_statuses is None:
        retry_for_statuses = [429]

    # Store the last exception raised while making a request.
    last_exc: Exception | None = None

    for n in range(max_tries):
        try:
            resp = await session.request(method, url, **kwargs)
            if resp.status not in retry_for_statuses:
                return resp
        except ClientResponseError as exc:
            if exc.status not in retry_for_statuses:
                raise exc
            last_exc = exc

        if n < max_tries:
            await asyncio.sleep(2 ** n)

    raise BadResponse(f"Tried {max_tries} times", last_exception_caught=last_exc)
