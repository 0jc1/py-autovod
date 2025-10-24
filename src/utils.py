import os
import sys
import subprocess
from logger import logger
from pathlib import Path
import configparser
import json
import time


def run_command(
    cmd: list[str],
    stdout: int | None = subprocess.DEVNULL,
    stderr: int | None = subprocess.DEVNULL,
) -> subprocess.CompletedProcess:
    if not cmd:
        logger.warning("Command list is empty")
        return subprocess.CompletedProcess([], -1)

    logger.debug(f"Executing: {' '.join(cmd)}")
    try:
        return subprocess.run(cmd, stdout=stdout, stderr=stderr, check=True)
    except subprocess.CalledProcessError as e:
        logger.debug(f"Command failed with error: {e}")
        return subprocess.CompletedProcess(cmd, -1)


def is_docker() -> bool:
    return os.path.exists("/.dockerenv")


def determine_source(stream_source: str, streamer_name: str) -> str | None:
    if not stream_source or not streamer_name:
        logger.error("Stream source and streamer name cannot be empty")
        return None

    sources: dict[str, str] = {
        "twitch": f"twitch.tv/{streamer_name}",
        "kick": f"kick.com/{streamer_name}",
        "youtube": f"youtube.com/@{streamer_name}/live",
    }
    return sources.get(stream_source.lower())


def check_stream_live(url: str) -> bool:
    # TODO this takes many seconds, find a faster method
    result = run_command(["streamlink", url])
    return result.returncode == 0


def get_size(path: str) -> float:
    if not os.path.exists(path):
        logger.warning(f"Path does not exist: {path}")
        return 0.0

    bytes_total = sum(
        os.path.getsize(os.path.join(dirpath, filename))
        for dirpath, _, filenames in os.walk(path)
        for filename in filenames
    )
    return bytes_total / 1_000_000  # Convert to MB


def fetch_metadata(streamer_url: str) -> dict:
    try:
        time.sleep(25)
        result = subprocess.run(
            ["streamlink", "--json", streamer_url],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)["metadata"]
    except subprocess.CalledProcessError as e:
        print(f"Streamlink error: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return None


def get_version_from_toml() -> str:
    """
    Extracts the version string from a pyproject.toml file.
    Supports both PEP 621 ([project]) and Poetry ([tool.poetry]) formats.
    Works with Python 3.10+.
    """
    path = Path("pyproject.toml")
    try:
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib

        if not path.exists():
            raise FileNotFoundError(f"File {path} is missing!")

        with open(path, "rb") as f:
            data = tomllib.load(f)

        return data.get("project", {}).get("version", "0.0.0")

        # Poetry format
        # poetry_section = data.get("tool", {}).get("poetry", {})
        # if "version" in poetry_section:
        #     return poetry_section["version"]
    except Exception as e:
        logger.error(f"Error getting version from {path}: {e}")
    return "0.0.0"


def load_config(config_name: str) -> configparser.ConfigParser | None:
    config = configparser.ConfigParser()
    config_file = f"{config_name}.ini"

    if not os.path.exists(config_file):
        logger.warning(f"The config file {config_file} not found for {config_name}.")
        return None

    config.read(config_file)
    logger.debug(f"Loaded configuration from {config_file}")
    return config
