import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

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

    def test_from_string_case_insensitive(self):
        """Test that from_string is case-insensitive"""
        result = StreamPlatform.from_string("TWITCH")
        assert result == StreamPlatform.TWITCH

    def test_from_string_invalid(self):
        """Test invalid string returns None"""
        result = StreamPlatform.from_string("invalid")
        assert result is None

    def test_from_string_empty(self):
        """Test empty string returns None"""
        result = StreamPlatform.from_string("")
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


class TestRunCommand:
    """Tests for the run_command utility function"""

    @patch("utils.subprocess.Popen")
    def test_run_command_success(self, mock_popen):
        """Test that run_command captures stdout on success"""
        from utils import run_command

        process_mock = MagicMock()
        process_mock.communicate.return_value = (b"hello world", b"")
        process_mock.returncode = 0
        mock_popen.return_value = process_mock

        result = run_command(["echo", "hello"])

        assert result.returncode == 0
        assert result.stdout == "hello world"
        assert result.stderr == ""

    @patch("utils.subprocess.Popen")
    def test_run_command_error(self, mock_popen):
        """Test that run_command captures stderr on failure"""
        from utils import run_command

        process_mock = MagicMock()
        process_mock.communicate.return_value = (b"", b"error occurred")
        process_mock.returncode = 1
        mock_popen.return_value = process_mock

        result = run_command(["bad", "cmd"])

        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr == "error occurred"

    @patch("utils.subprocess.Popen")
    def test_run_command_calls_popen_correctly(self, mock_popen):
        """Ensure subprocess.Popen is called with the correct arguments"""
        from utils import run_command

        process_mock = MagicMock()
        process_mock.communicate.return_value = (b"", b"")
        process_mock.returncode = 0
        mock_popen.return_value = process_mock

        cmd = ["ffmpeg", "-i", "input.mp4"]
        run_command(cmd)

        mock_popen.assert_called_once()
        called_args, called_kwargs = mock_popen.call_args

        assert called_args[0] == cmd
        assert "stdout" in called_kwargs
        assert "stderr" in called_kwargs
