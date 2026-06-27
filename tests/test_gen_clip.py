import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.modules.pop("gen_clip", None)

from gen_clip import extract_clip  # noqa: E402


def test_extract_clip_can_create_shorts_variant(tmp_path):
    completed = subprocess.CompletedProcess(args=[], returncode=0)
    clip_data = {"name": "Great clip", "start": 10, "end": 20}

    with (
        patch("gen_clip.run_command", return_value=completed) as run_command,
        patch("gen_clip.os.path.exists", return_value=True),
    ):
        success, output_file = extract_clip(
            "vod.mp4", tmp_path, clip_data, shorts_format=True
        )

    assert success is True
    assert output_file == str(Path(tmp_path) / "Great clip.mp4")
    assert run_command.call_args_list[0].args[0] == [
        "ffmpeg",
        "-y",
        "-ss",
        "10",
        "-to",
        "20",
        "-i",
        "vod.mp4",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        str(Path(tmp_path) / "Great clip.mp4"),
    ]
    assert run_command.call_args_list[1].args[0] == [
        "ffmpeg",
        "-y",
        "-i",
        str(Path(tmp_path) / "Great clip.mp4"),
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        str(Path(tmp_path) / "Great clip_shorts.mp4"),
    ]
