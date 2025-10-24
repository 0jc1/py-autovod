import sys
import os
import time
import threading
import subprocess
import datetime
from logger import logger
from utils import determine_source, check_stream_live, load_config, fetch_metadata
from processor import processor


class StreamMonitor(threading.Thread):
    """Class to monitor and download streams for a single streamer."""

    def __init__(self, streamer_name: str, retry_delay: int = 60):
        super().__init__(name=f"m-{streamer_name}")
        self.streamer_name = streamer_name.lower()
        self.DATETIME_FORMAT = "%d-%m-%Y-%H-%M-%S"
        self.retry_delay = retry_delay
        self.running = False
        self.config = None
        self.stream_metadata = {}
        self.stream_source_url = None
        self.current_process = None  # Store the running streamlink subprocess
        self._load_configuration()

    def _load_configuration(self) -> bool:
        self.config = load_config(self.streamer_name) or load_config("default")
        if not self.config:
            logger.error("Failed to load configuration file.")
            return False

        # Get stream source from config
        match self.config["source"]:
            case {"stream_source": stream_source}:
                self.stream_source_url = determine_source(stream_source, self.streamer_name)
                if not self.stream_source_url:
                    logger.error(f"Unknown stream source: {stream_source} for {self.streamer_name}")
                    return False
            case _:
                logger.error(f"Missing source configuration for {self.streamer_name}")
                return False

        return True

    def download_video(self) -> tuple[bool, str]:
        if not self.config:
            return False, ""

        quality = self.config["streamlink"]["quality"]
        current_time = datetime.datetime.now().strftime(self.DATETIME_FORMAT)
        stream_title = self.stream_metadata.get("title", "")
        stream_id = self.stream_metadata.get("id", current_time)

        output_path = f"recordings/{self.streamer_name}/{stream_id}/{stream_title}-{self.streamer_name}-{current_time}.ts"

        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)

        command = ["streamlink", "-o", output_path, self.stream_source_url, quality]

        if self.config.has_option("streamlink", "flags"):
            flags = self.config.get("streamlink", "flags").strip(",").split(",")
            command.extend([flag.strip() for flag in flags if flag.strip()])

        try:
            # Start the download process
            self.current_process = subprocess.Popen(
                command, stdout=sys.stdout, stderr=subprocess.DEVNULL
            )
            success = self.current_process.wait() == 0 # Wait until the stream ends

            if success:
                if output_path and os.path.exists(output_path):
                    logger.debug(f"Found downloaded file: {output_path}")
                    return True, output_path

                logger.warning("Could not find the downloaded file")
                return False, ""
            else:
                return False, ""

        except Exception as e:
            logger.error(f"Error running streamlink: {e}")
            return False, ""
        finally:
            self.current_process = None

    def run(self) -> None:
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
                    logger.success(f"{self.streamer_name} is live!")

                    self.stream_metadata: dict = fetch_metadata(self.stream_source_url)
                    download_success, video_path = self.download_video()

                    if download_success:
                        logger.success(f"Stream for {self.streamer_name} downloaded successfully")
                    else:
                        logger.warning(
                            f"Failed to download stream for {self.streamer_name}"
                        )

                    # Process video
                    if video_path:
                        processor.process(video_path, self.streamer_name, self.config)
                    else:
                        logger.error("Downloaded file path not found, cannot process")

                else:
                    logger.info(
                        f"{self.streamer_name} is offline. Retrying in {self.retry_delay} seconds.."
                    )
            except Exception as e:
                logger.error(f"Error monitoring {self.streamer_name}: {e}")

            time.sleep(self.retry_delay)

    def stop(self) -> None:
        self.running = False
        if self.current_process is not None:
            logger.debug(f"Terminating streamlink process for {self.streamer_name}")
            self.current_process.terminate()
            try:
                self.current_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logger.debug("Process did not terminate in time; killing it")
                self.current_process.kill()
            self.current_process = None
        logger.debug(f"Stopped monitoring {self.streamer_name}")