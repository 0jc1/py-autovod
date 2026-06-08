import os
import sys
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from uploader_commands import upload_with_rclone


class TestUploaderCommands:
    """Tests for the rclone uploader command builder"""

    @patch("uploader_commands.run_command")
    def test_rclone_upload_success(self, mock_run):
        """Test that upload_with_rclone builds the correct command and succeeds"""

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="uploaded",
            stderr=""
        )

        local = "recordings/test.mp4"
        remote = "myremote:uploads/test.mp4"

        result = upload_with_rclone(local, remote)

        # Ensure run_command was called correctly
        mock_run.assert_called_once()
        called_args = mock_run.call_args[0][0]

        assert called_args == [
            "rclone",
            "copyto",
            local,
            remote
        ]

        # Ensure result is passed through
        assert result.returncode == 0
        assert result.stdout == "uploaded"

    @patch("uploader_commands.run_command")
    def test_rclone_upload_failure(self, mock_run):
        """Test that upload_with_rclone handles errors"""

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="upload failed"
        )

        local = "recordings/test.mp4"
        remote = "myremote:uploads/test.mp4"

        result = upload_with_rclone(local, remote)

        assert result.returncode == 1
        assert result.stderr == "upload failed"
