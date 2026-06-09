import os
import sys
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from processor import Processor


class TestProcessorCommands:
    """Tests for FFmpeg command generation inside Processor"""

    @patch("processor.run_command")
    def test_convert_builds_correct_remux_command(self, mock_run):
        """Test that _convert builds the correct FFmpeg remux command"""

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        processor = Processor()
        input_path = "/videos/test.ts"
        expected_output = "/videos/test.mp4"

        result = processor._convert(input_path)

        # First FFmpeg call (remux)
        first_call = mock_run.call_args_list[0][0][0]

        assert first_call == [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-c",
            "copy",
            expected_output,
            "-loglevel",
            "error",
        ]

        assert result == expected_output

    @patch("processor.run_command")
    def test_encode_builds_correct_command(self, mock_run):
        """Test that _encode builds the correct FFmpeg encode command"""

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        processor = Processor()

        class FakeConfig:
            def get(self, section, key, fallback=None):
                return {
                    ("encoding", "codec"): "libx265",
                    ("encoding", "crf"): "25",
                    ("encoding", "preset"): "medium",
                    ("encoding", "log"): "error",
                }.get((section, key), fallback)

        fake_cfg = FakeConfig()

        input_path = "/videos/test.mp4"
        expected_output = "/videos/test.reencoded.mp4"

        result = processor._encode(input_path, fake_cfg)

        cmd = mock_run.call_args[0][0]

        assert cmd == [
            "ffmpeg",
            "-i",
            input_path,
            "-c:v",
            "libx265",
            "-crf",
            "25",
            "-preset",
            "medium",
            "-c:a",
            "copy",
            "-loglevel",
            "error",
            expected_output,
        ]

        assert result == expected_output
