import sys
import time
import threading
import os
from loguru import logger
from utils import (
    run_command,
    determine_source,
    check_stream_live,
    fetch_metadata,
    load_config,
)
from transcription import process_ts_file
import settings


class StreamerMonitor(threading.Thread):
    """Class to monitor and download streams for a single streamer."""

    def __init__(self, streamer_name: str, retry_delay: int = 60):
        """

        Args:
            streamer_name: The name of the streamer to monitor
            retry_delay: Time in seconds to wait between checks if stream is offline
        """
        super().__init__(name=f"m-{streamer_name}")
        self.streamer_name = streamer_name
        self.retry_delay = retry_delay
        self.running = False
        self.config = None
        self.stream_source_url = None

        self._load_configuration()

    def _load_configuration(self) -> bool:
        self.config = load_config(self.streamer_name)
        if not self.config:
            self.config = load_config("default")

        stream_source = self.config["source"]["stream_source"]
        self.stream_source_url = determine_source(stream_source, self.streamer_name)

        if not self.stream_source_url:
            logger.error(
                f"Unknown stream source: {stream_source} for {self.streamer_name}"
            )
            return False

        return True

    def process_video(self, video_title=None, video_description=None) -> bool:
        if not self.config:
            return False

        quality = self.config["streamlink"]["quality"]

        command = [
            "streamlink",
            "-o",
            f"recordings/{{author}}/{{id}}/{{author}}-{{time:%Y-%m-%d-%H-%M-%S}}.ts",
            self.stream_source_url,
            quality,
        ]

        if self.config.has_option("streamlink", "flags"):
            flags = self.config.get("streamlink", "flags").strip(",").split(",")
            flags = [flag.strip() for flag in flags if flag.strip()]
            command.extend(flags)

        result = run_command(
            command,
            stdout=sys.stdout,
        )

        # streamlink returns when stream ends
        success = result.returncode == 0

        # If download was successful and transcription is enabled, process the video for transcription
        if success and settings.config.getboolean(
            "transcription", "enabled", fallback=False
        ):
            # Find the most recently downloaded file
            streamer_dir = f"recordings/{self.streamer_name}"
            if os.path.exists(streamer_dir):
                files = [
                    os.path.join(streamer_dir, f)
                    for f in os.listdir(streamer_dir)
                    if f.endswith(".ts")
                ]
                if files:
                    # Sort by modification time, newest first
                    latest_file = max(files, key=os.path.getmtime)
                    logger.info(f"Found latest recording: {latest_file}")

                    run_command(
                        [
                            "ffmpeg",
                            "-i",
                            latest_file,
                            "-c",
                            "copy",
                            latest_file.replace(".ts", ".mp4"),
                        ],
                        stdout=sys.stdout,
                    )

                    model_name = settings.config.get("transcription", "model_name")
                    cleanup_wav = settings.config.getboolean(
                        "transcription", "cleanup_wav", fallback=True
                    )

                    # Process the file for transcription
                    try:
                        transcription_success, transcript_path = process_ts_file(
                            latest_file, model_name, cleanup_wav
                        )

                        if transcription_success:
                            logger.success(f"Transcription saved to {transcript_path}")
                        else:
                            logger.error("Transcription failed")
                    except Exception as e:
                        logger.error(f"Error during transcription: {e}")
                else:
                    logger.warning(f"No .ts files found in {streamer_dir}")

        return success

    def run(self):
        if not self.config or not self.stream_source_url:
            logger.error(
                f"Cannot start monitoring for {self.streamer_name}: missing configuration"
            )
            return

        self.running = True
        logger.info(f"Started monitoring {self.streamer_name}")

        while self.running:
            try:
                if check_stream_live(self.stream_source_url):
                    logger.info(f"{self.streamer_name} is live")

                    video_title = None
                    video_description = None

                    if self.config.getboolean("source", "api_calls", fallback=False):
                        video_title, video_description = fetch_metadata(
                            self.config["source"]["api_url"], self.streamer_name
                        )

                    download_success = self.process_video(
                        video_title, video_description
                    )

                    if download_success:
                        logger.success(
                            f"Stream for {self.streamer_name} downloaded successfully"
                        )
                    else:
                        logger.error(f"Stream download failed for {self.streamer_name}")

                else:
                    logger.info(
                        f"{self.streamer_name} is offline. Retrying in {self.retry_delay} seconds..."
                    )

            except Exception as e:
                logger.error(f"Error monitoring {self.streamer_name}: {e}")

            # Sleep before next check
            time.sleep(self.retry_delay)

    def stop(self):
        """Stop the monitoring thread."""
        self.running = False
        logger.info(f"Stopped monitoring {self.streamer_name}")
