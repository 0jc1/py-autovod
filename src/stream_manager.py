import sys
import time
import signal
from typing import Dict, List, Optional
from logger import logger
from settings import config
from streamer_monitor import StreamerMonitor
from utils import get_size
from tqdm import tqdm


class StreamManager:
    """Class to manage multiple streamer monitors."""

    def __init__(self):
        """Initialize the stream manager."""
        self.monitors: Dict[str, StreamerMonitor] = {}
        self.running = False

        self.retry_delay = config.getint("general", "retry_delay", fallback=120)

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame) -> None:
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def get_streamers_list(self) -> List[str]:
        if not config or not config.has_section("streamers"):
            logger.error("No streamers section in configuration")
            return []

        if not config.has_option("streamers", "streamers"):
            logger.error("No streamers defined in configuration")
            return []

        streamers_str = config.get("streamers", "streamers", fallback="")
        if not streamers_str.strip():
            return []

        return list(
            set([s.strip() for s in streamers_str.strip(",").split(",") if s.strip()])
        )

    def start(self, streamer_name: Optional[str] = None) -> None:
        if self.running:
            logger.warning("Stream manager is already running")
            return

        self.running = True
        streamers: List[str] = []

        if streamer_name:
            streamers = [streamer_name]
        else:
            streamers = self.get_streamers_list()
            if not streamers:
                logger.error("No streamers to monitor")
                return

        logger.info(
            f"Starting to monitor {len(streamers)} streamers: {', '.join(streamers)}"
        )

        # Create and start a monitor for each streamer
        for name in streamers:
            monitor = StreamerMonitor(name, self.retry_delay)
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

    def list_monitored_streamers(self) -> List[str]:
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
                    total += speed

                    # Set postfix to current speed
                    pbar.set_postfix_str(f"{speed:.3f}MB/s")
                    pbar.n = total
                    pbar.refresh()
                    time.sleep(1)
            except KeyboardInterrupt:
                pbar.close()
                self.stop()
