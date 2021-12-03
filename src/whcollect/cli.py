from pathlib import Path
from typing import Final

import click

from . import __version__

# Environment variable to check for the API key.
API_KEY_ENV_VAR: Final = "WALLHAVEN_API_KEY"

# Click command context settings.
cli_context_settings = {"help_option_names": ["-h", "--help"]}


@click.command(context_settings=cli_context_settings)
@click.argument("username")
@click.argument("collections", nargs=-1, required=True)
@click.version_option(
    __version__,
    "-v",
    "--version",
    message="%(prog)s %(version)s",
)
@click.option(
    "-a",
    "--api-key",
    envvar=API_KEY_ENV_VAR,
    help="Your wallhaven API key.",
)
@click.option(
    "-d",
    "--dest",
    "destination",
    type=click.Path(exists=True, file_okay=False, writable=True, path_type=Path),
    help=(
        "The destination directory (must exist and be writable; "
        "files here may be overwritten)."
    ),
)
@click.option(
    "-f",
    "--flat",
    is_flag=True,
    help="Suppress creating per-collection subdirectories",
)
def cli(username: str, collections: list[str], api_key: str, destination: Path) -> None:
    """Download wallpapers from your wallhaven collections.

    USERNAME refers to your wallhaven username, and COLLECTIONS is a
    space-separated list of collection labels or IDs.
    """
    print(f"username: <{username}>")
    print(f"collections: <{collections}>")
    print(f"api_key: <{api_key}>")
    print(f"destination: <{destination}>")
