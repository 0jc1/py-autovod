import os
import sys
import tempfile
from unittest.mock import patch

# Add src to path to import utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils import determine_source, is_docker, get_size, load_config


class TestDetermineSource:
    """Test cases for determine_source function"""

    def test_twitch_source(self):
        """Test Twitch source URL generation"""
        result = determine_source("twitch", "channelname")
        assert result == "twitch.tv/channelname"

    def test_kick_source(self):
        """Test Kick source URL generation"""
        result = determine_source("kick", "channelname")
        assert result == "kick.com/channelname"

    def test_youtube_source(self):
        """Test YouTube source URL generation"""
        result = determine_source("youtube", "channelname")
        assert result == "youtube.com/@channelname/live"

    def test_case_insensitive(self):
        """Test that source is case-insensitive"""
        result = determine_source("TWITCH", "Streamer")
        assert result == "twitch.tv/streamer"

    def test_invalid_source(self):
        """Test invalid source returns None"""
        result = determine_source("invalid", "streamer")
        assert result is None

    def test_empty_source(self):
        """Test empty source returns None"""
        result = determine_source("", "streamer")
        assert result is None

    def test_empty_streamer(self):
        """Test empty streamer name returns None"""
        result = determine_source("twitch", "")
        assert result is None

    def test_both_empty(self):
        """Test both parameters empty returns None"""
        result = determine_source("", "")
        assert result is None


class TestIsDocker:
    """Test cases for is_docker function"""

    def test_not_in_docker(self):
        """Test when not running in Docker"""
        with patch("os.path.exists", return_value=False):
            result = is_docker()
            assert result is False

    def test_in_docker(self):
        """Test when running in Docker"""
        with patch("os.path.exists", return_value=True):
            result = is_docker()
            assert result is True


class TestGetSize:
    """Test cases for get_size function"""

    def test_get_size_empty_directory(self):
        """Test get_size with empty directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            size = get_size(tmpdir)
            assert size == 0.0

    def test_get_size_with_file(self):
        """Test get_size with a file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file with 1MB of data
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "wb") as f:
                f.write(b"0" * 1_000_000)

            size = get_size(tmpdir)
            assert 0.9 < size < 1.1  # Allow small margin for exact size

    def test_get_size_nonexistent_path(self):
        """Test get_size with nonexistent path"""
        result = get_size("/nonexistent/path")
        assert result == 0.0

    def test_get_size_multiple_files(self):
        """Test get_size with multiple files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 3 files with 500KB each
            for i in range(3):
                test_file = os.path.join(tmpdir, f"test{i}.txt")
                with open(test_file, "wb") as f:
                    f.write(b"0" * 500_000)

            size = get_size(tmpdir)
            assert 1.4 < size < 1.6  # ~1.5 MB


class TestLoadConfig:
    """Test cases for load_config function"""

    def test_load_config_success(self):
        """Test loading existing config file"""
        # Use the default.ini that exists in the project
        config = load_config("default")
        assert config is not None

    def test_load_config_nonexistent(self):
        """Test loading nonexistent config file"""
        config = load_config("nonexistent_config_file")
        assert config is None

    def test_load_config_returns_configparser(self):
        """Test that load_config returns ConfigParser object"""
        import configparser

        config = load_config("default")
        if config is not None:
            assert isinstance(config, configparser.ConfigParser)
