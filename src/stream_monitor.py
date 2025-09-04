import sys
import os
import time
import threading
import subprocess
import datetime
from io import BytesIO
from typing import Optional
from logger import logger
from utils import determine_source, load_config, fetch_metadata
from processor import processor
from streamlink import NoPluginError, Streamlink, PluginError, StreamError


class StreamMonitor(threading.Thread):
    """Class to monitor and download streams for a single streamer."""

    def __init__(self, streamer_name: str, retry_delay: int = 60):
        super().__init__(name=f"m-{streamer_name}")
        self.streamer_name = streamer_name.lower()
        self.retry_delay = retry_delay
        self.running = False
        self.config = None
        self.stream_metadata = {}
        self.session = None
        self.stream_source_url = None
        self._load_configuration()
        self._setup_session()

    def _setup_session(self):
        # set up Streamlink session for this stream
        self.session = Streamlink()
        self.session.set_option("stream-timeout", 60)


    def check_streamer_live(self, url : str):
        try:
            streams = self.session.streams(url)
            return streams != {}
        except Exception as e:
            logger.warning(f"{e}")
            return False


    def _load_configuration(self) -> bool:
        self.config = load_config(self.streamer_name)
        if not self.config:
            self.config = load_config("default")
            if not self.config:
                logger.error("Failed to load default config file.")
                return False

        # Get stream source from config
        try:
            stream_source = self.config["source"]["stream_source"]
            self.stream_source_url = determine_source(stream_source, self.streamer_name)
        except KeyError:
            logger.error(f"Missing source configuration for {self.streamer_name}")
            return False

        if not self.stream_source_url:
            logger.error(
                f"Unknown stream source: {stream_source} for {self.streamer_name}"
            )
            return False

        return True

    def download_video(self) -> tuple[bool, str]:
        if not self.config:
            return False, ""

        quality = self.config["streamlink"]["quality"]
        current_time = datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
        stream_title = self.stream_metadata.get("title", "")
        stream_id = self.stream_metadata.get("id", current_time)

        output_path = f"recordings/{self.streamer_name}/{stream_id}/{stream_title}-{self.streamer_name}-{current_time}.ts"

        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        
        try: 
            plugin_name, plugin_class, resolved_url = self.session.resolve_url(self.stream_source_url)
            plugin_options = {}
            chunk_size: int = 8192
            max_retries = 3       # number of attempts
            retry_delay = 2       # seconds between retries

            if plugin_name == "twitch":
                plugin_options = {"disable-ads": True}
    
            plugin = plugin_class(self.session, resolved_url, options=plugin_options)
            
            streams = plugin.streams()

            for attempt in range(1, max_retries + 1):
                try:
                    fd = streams[quality].open()
                    # prebuffer
                    fd.read(chunk_size)
                    break 
                except OSError as e:
                    logger.warning(f"Attempt {attempt} failed to open stream for {self.streamer_name}: {e}")
                    if attempt == max_retries:
                        logger.error("Max retries reached. Could not open stream.")
                        raise
                    time.sleep(retry_delay)

            # read then and write to file
            with open(output_path, "wb") as f:
                while True:
                    try:
                        data = fd.read(chunk_size)
                        if data == b"":  # empty bytes = end of stream
                            break
                        f.write(data)
                    except OSError as err:
                        logger.error(f"OSError while reading stream: {err}")
                        break
                
            fd.close()

        except (OSError, NoPluginError, PluginError, StreamError) as e:
            print(e)
            logger.error(f"bru")
            return False, ""
        
        return True, output_path

        # command = ["streamlink", "-o", output_path, self.stream_source_url, quality]

        # if self.config.has_option("streamlink", "flags"):
        #     flags = self.config.get("streamlink", "flags").strip(",").split(",")
        #     flags = [flag.strip() for flag in flags if flag.strip()]
        #     command.extend(flags)

        # try:
        #     # Start the download process
        #     self.current_process = subprocess.Popen(
        #         command, stdout=sys.stdout, stderr=subprocess.DEVNULL
        #     )
        #     retcode = self.current_process.wait()  # Wait until the stream ends
        #     success = retcode == 0

        #     if success:
        #         if output_path and os.path.exists(output_path):
        #             logger.debug(f"Found downloaded file: {output_path}")
        #             return True, output_path

        #         logger.warning("Could not find the downloaded file")
        #         return False, ""
        #     else:
        #         return False, ""

        # except Exception as e:
        #     logger.error(f"Error running streamlink: {e}")
        #     return False, ""
        # finally:
        #     self.current_process = None


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
                if self.check_streamer_live(self.stream_source_url):
                    logger.success(f"{self.streamer_name} is live!")

                    self.stream_metadata: dict = fetch_metadata(self.stream_source_url)
                    print('ok')
                    download_success, video_path = self.download_video()

                    if download_success:
                        logger.success(
                            f"Stream for {self.streamer_name} downloaded successfully"
                        )
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
        logger.debug(f"Stopped monitoring {self.streamer_name}")
