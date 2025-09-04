import os
import subprocess
from typing import List, Optional, Tuple, Dict
from logger import logger
import configparser
import json
import time


def run_command(
    cmd: List[str],
    stdout: Optional[int] = subprocess.DEVNULL,
    stderr: Optional[int] = subprocess.DEVNULL,
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


def determine_source(stream_source: str, streamer_name: str) -> Optional[str]:
    if not stream_source or not streamer_name:
        logger.error("Stream source and streamer name cannot be empty")
        return None

    sources: Dict[str, str] = {
        "twitch": f"twitch.tv/{streamer_name}",
        "kick": f"kick.com/{streamer_name}",
        "youtube": f"youtube.com/@{streamer_name}/live",
    }
    url = sources.get(stream_source.lower())
    if url is None:
        raise ValueError(f"Unsupported stream source: {stream_source}")
    return url


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
        time.sleep(1)
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


def load_config(config_name: str) -> Optional[configparser.ConfigParser]:
    config = configparser.ConfigParser()
    config_file = f"{config_name}.ini"

    if not os.path.exists(config_file):
        logger.warning(f"The config file {config_file} not found for {config_name}.")
        return None

    config.read(config_file)
    logger.debug(f"Loaded configuration from {config_file}")
    return config
