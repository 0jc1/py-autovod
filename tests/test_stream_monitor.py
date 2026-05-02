import configparser
import os
import pytest
import sys
from stream_monitor import StreamMonitor
from unittest.mock import patch

from utils import load_config

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestStreamMonitor:
    """Test cases for StreamMonitor class"""

    def test_streamlink_command_construction(self):
        """Test streamlink command is constructed correctly from config"""
        with patch.object(StreamMonitor, "_load_configuration", return_value=True):
            monitor = StreamMonitor("streamername")
            monitor.config = configparser.ConfigParser()
            # Populate config directly
            monitor.config.read_dict({"streamlink": {"quality": "1080p60,720p,best"}})
            command = monitor._construct_streamlink_command("stream.url", "output/path")
            assert command[-1] == "1080p60,720p,best"

    def test_quality_config_with_fallbacks(self):
        """Test quality fallback is read correctly from config file"""
        with patch.object(StreamMonitor, "_load_configuration", return_value=True):
            monitor = StreamMonitor("streamername")
            # Load stubbed config file
            monitor.config = load_config("tests/data/quality_fallback")

            command = monitor._construct_streamlink_command("stream.url", "output/path")
            assert command[-1] == "1080p60,720p,best"

    def test_quality_config_with_single_value(self):
        """Test streamlink single-value quality is read correctly from config file"""
        with patch.object(StreamMonitor, "_load_configuration", return_value=True):
            monitor = StreamMonitor("streamername")
            # Load stubbed config file
            monitor.config = load_config("tests/data/quality_non_fallback")

            command = monitor._construct_streamlink_command("stream.url", "output/path")
            assert command[-1] == "best"
