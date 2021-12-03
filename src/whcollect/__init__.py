from pathlib import Path

import tomli


def version_from_pyproject_toml() -> str:
    """Extract the program version from pyproject.toml in the root directory."""
    version = "n/a"
    project_root = Path(__file__).parent.parent.parent
    if (pyproject_toml := project_root / "pyproject.toml").is_file():
        with pyproject_toml.open("rb") as f:
            try:
                toml_dict = tomli.load(f)
                version = toml_dict["tool"]["poetry"]["version"]
            except (tomli.TOMLDecodeError, KeyError):
                pass
    return version


__version__ = version_from_pyproject_toml()
