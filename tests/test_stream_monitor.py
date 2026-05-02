import pytest
import os
import sys
from unittest.mock import MagicMock, patch
import configparser

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from stream_monitor import StreamMonitor

class TestStreamMonitorQuality:
    def _make_monitor(self, quality: str) -> StreamMonitor:
        monitor = StreamMonitor.__new__(StreamMonitor)
        config = configparser.ConfigParser()
        config.read_dict({
            "streamlink": {"quality": quality},
            "source": {"stream_source": "twitch"},
        })
        monitor.config = config
        monitor.streamer_name = "teststreamer"
        monitor.datetime_format = "%d-%m-%Y-%H-%M-%S"
        monitor.stream_metadata = {}
        monitor.stream_source_url = "https://twitch.tv/teststreamer"
        monitor.stream_platform = None
        monitor.current_process = None
        return monitor

    def test_single_quality_in_command(self):
        monitor = self._make_monitor("best")
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.wait.return_value = 1
            monitor.download_video()
            args = mock_popen.call_args[0][0]
            assert args[-1] == "best"

    def test_fallback_quality_list_in_command(self):
        monitor = self._make_monitor("1080p60,720p,best")
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.wait.return_value = 1
            monitor.download_video()
            args = mock_popen.call_args[0][0]
            assert args[-1] == "1080p60,720p,best"