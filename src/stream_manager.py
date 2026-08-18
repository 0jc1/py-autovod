import sys
import time
import signal
from logger import logger
from settings import config
from stream_monitor import StreamMonitor
from uploader import uploader
from utils import get_size
from tqdm import tqdm


class StreamManager:
    """Class to manage multiple streamer monitors."""

    def __init__(self):
        self.monitors: dict[str, StreamMonitor] = {}
        self.running = False

        self.retry_delay = config.getint("general", "retry_delay", fallback=120)

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def __repr__(self):
        return f"{self.__class__.__name__}(running={self.running!r}, retry_delay={self.retry_delay!r})"

    def _signal_handler(self, signum: int, frame) -> None:
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def get_streamers_list(self) -> list[str]:
        if not config or not config.has_section("streamers"):
            logger.warning("No streamers section in configuration")
            return []

        streamers_str = config.get("streamers", "streamers", fallback="")
        if not streamers_str.strip():
            return []

        return list(
            set([s.strip() for s in streamers_str.strip(",").split(",") if s.strip()])
        )

    def start(self, streamer_name: str | None = None) -> None:
        if self.running:
            logger.warning("Stream manager is already running")
            return

        self.running = True
        streamers: list[str] = []

        if streamer_name:
            streamers = [streamer_name]
        else:
            streamers = self.get_streamers_list()
            if not streamers:
                logger.warning("No streamers to monitor")
                return

        logger.info(
            f"Starting to monitor {len(streamers)} streamers: {', '.join(streamers)}"
        )

        # Create and start a monitor for each streamer
        for name in streamers:
            monitor = StreamMonitor(name, self.retry_delay)
            self.monitors[name] = monitor
            monitor.daemon = True  # Set as daemon so they exit when main thread exits
            monitor.start()

        logger.success("Stream manager started successfully")

    def stop(self) -> None:
        if not self.running:
            return

        logger.info("Stopping all streamer monitors..")

        # Stop all monitors
        for streamer_name, monitor in self.monitors.items():
            monitor.stop()
            monitor.join(timeout=0.02)

        self.monitors.clear()
        self.running = False

        # Persist any remaining uploads and stop the background worker.
        try:
            uploader.stop()
        except Exception:
            logger.exception("Error stopping uploader")

    def list_monitored_streamers(self) -> list[str]:
        return list(self.monitors.keys())

    def wait(self) -> None:
        recordings_dir = "recordings"
        prev_size = get_size(recordings_dir)
        total = 0
        time.sleep(3)

        with tqdm(
            desc="Downloading",
            unit="MB",
            bar_format="{l_bar}{bar}| {n:.3f} MB ({postfix})",
            dynamic_ncols=True,
        ) as pbar:
            try:
                while self.running:
                    cur_size = get_size(recordings_dir)
                    speed = cur_size - prev_size
                    prev_size = cur_size
                    speed = max(speed, 0)
                    total += speed

                    # Set postfix to current speed
                    pbar.set_postfix_str(f"{speed:.3f} MB/s")
                    pbar.n = total
                    pbar.refresh()
                    time.sleep(1)
            except KeyboardInterrupt:
                pbar.close()
                self.stop()
