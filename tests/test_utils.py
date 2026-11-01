import os
import subprocess
import sys
import tempfile
from unittest.mock import patch

# Add src to path to import utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils import determine_source, is_docker, get_size, load_config, StreamPlatform


class TestDetermineSource:
    """Test cases for determine_source function"""

    def test_twitch_source(self):
        """Test Twitch source URL generation"""
        result = determine_source(StreamPlatform.TWITCH, "channelname")
        assert result == "twitch.tv/channelname"

    def test_kick_source(self):
        """Test Kick source URL generation"""
        result = determine_source(StreamPlatform.KICK, "channelname")
        assert result == "kick.com/channelname"

    def test_youtube_source(self):
        """Test YouTube source URL generation"""
        result = determine_source(StreamPlatform.YOUTUBE, "channelname")
        assert result == "youtube.com/@channelname/live"

    def test_case_insensitive(self):
        """Test that streamer name is case-insensitive"""
        result = determine_source(StreamPlatform.TWITCH, "Streamer")
        assert result == "twitch.tv/streamer"

    def test_empty_streamer(self):
        """Test empty streamer name returns None"""
        result = determine_source(StreamPlatform.TWITCH, "")
        assert result is None


class TestStreamPlatform:
    """Test cases for StreamPlatform enum"""

    def test_from_string_twitch(self):
        """Test converting 'twitch' string to enum"""
        result = StreamPlatform.from_string("twitch")
        assert result == StreamPlatform.TWITCH

    def test_from_string_youtube(self):
        """Test converting 'youtube' string to enum"""
        result = StreamPlatform.from_string("youtube")
        assert result == StreamPlatform.YOUTUBE


class TestFetchMetadata:
    """Test cases for fetch_metadata polling behaviour"""

    @patch("utils.subprocess.run")
    @patch("utils.time.sleep")
    def test_returns_immediately_on_success(self, mock_sleep, mock_run):
        """Should return metadata on first successful response without sleeping."""
        from utils import fetch_metadata
        import json

        mock_run.return_value.stdout = json.dumps({
            "metadata": {"title": "Live stream", "id": "123"}
        })
        mock_run.return_value.returncode = 0

        result = fetch_metadata("https://twitch.tv/test")

        assert result["title"] == "Live stream"
        assert result["id"] == "123"
        mock_sleep.assert_not_called()
        mock_run.assert_called_once()

    @patch("utils.subprocess.run")
    @patch("utils.time.sleep")
    def test_retries_until_success(self, mock_sleep, mock_run):
        """Should poll with backoff and return as soon as valid metadata appears."""
        from utils import fetch_metadata
        import json
        from subprocess import CalledProcessError

        # First two calls fail, third succeeds
        mock_run.side_effect = [
            CalledProcessError(1, ["streamlink"]),
            CalledProcessError(1, ["streamlink"]),
            subprocess.CompletedProcess(["streamlink"], 0, stdout=json.dumps({"metadata": {"title": "Finally"}})),
        ]

        result = fetch_metadata("https://kick.com/test", max_attempts=5)

        assert result["title"] == "Finally"
        assert mock_run.call_count == 3
        # Should have slept for the second and third attempts
        assert mock_sleep.call_count == 2

    @patch("utils.subprocess.run")
    @patch("utils.time.sleep")
    def test_returns_empty_dict_after_all_failures(self, mock_sleep, mock_run):
        """Should return {} when all attempts fail."""
        from utils import fetch_metadata
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(1, ["streamlink"])

        result = fetch_metadata("https://youtube.com/@test/live", max_attempts=3)

        assert result == {}
        assert mock_run.call_count == 3
