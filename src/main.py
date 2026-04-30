#!/usr/bin/env python3

import os
import sys
import argparse
from logger import logger
from utils import get_version_from_toml
from settings import CLIPCEPTION_ENABLED
from stream_manager import StreamManager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AutoVOD - Automatic VOD downloader and uploader for Twitch, Kick, and YouTube"
    )
    parser.add_argument("-n", "--name", help="Single streamer name to monitor")
    parser.add_argument(
        "-v", "--version", action="store_true", help="Display the current version"
    )
    return parser.parse_args()


def main() -> int:
    version = get_version_from_toml()

    logger.info(f"Starting Py-AutoVOD v{version}")

    args = parse_args()

    recordings_dir = "recordings"
    if not os.path.exists(recordings_dir):
        try:
            os.mkdir(recordings_dir)
        except Exception as e:
            print(f"Failed to create recordings directory: {e}")
            return 1

    if args.version:
        print(f"Version: {version}")
        return 0

    logger.info(f"Clipception Enabled: {CLIPCEPTION_ENABLED}")

    manager = StreamManager()
    manager.start(args.name) if args.name else manager.start()
    manager.wait()
    return 0


if __name__ == "__main__":
    if sys.version_info < (3, 9):
        print("Error: Python 3.9 or higher is required")
        print("Current Python version: " + sys.version)
        sys.exit(1)
    sys.exit(main())
