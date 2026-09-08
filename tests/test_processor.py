import configparser
import os
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

# Add src to path to import processor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Keep processor imports lightweight for command-construction tests.
transcription = types.ModuleType("transcription")
transcription.MIN_DURATION = 999
transcription.process_video = lambda *args, **kwargs: None
sys.modules.setdefault("transcription", transcription)

gen_clip = types.ModuleType("gen_clip")
gen_clip.generate_clips = lambda *args, **kwargs: None
gen_clip.process_clips = lambda *args, **kwargs: None
sys.modules.setdefault("gen_clip", gen_clip)

uploader = types.ModuleType("uploader")
uploader.upload_youtube = lambda *args, **kwargs: None


class _FakeUploader:
    def __init__(self):
        self.items = []

    def enqueue(self, *args, **kwargs):
        self.items.append((args, kwargs))


uploader.uploader = _FakeUploader()
sys.modules.setdefault("uploader", uploader)

from processor import Processor  # noqa: E402


def test_encode_writes_to_reencoded_output_path():
    streamer_config = configparser.ConfigParser()
    streamer_config["encoding"] = {
        "codec": "libx264",
        "crf": "23",
        "preset": "fast",
        "log": "warning",
    }
    completed = subprocess.CompletedProcess(args=[], returncode=0)

    with patch("processor.run_command", return_value=completed) as run_command:
        output_path = Processor._encode(
            object.__new__(Processor), "/tmp/input.mp4", streamer_config
        )

    assert output_path == "/tmp/input.reencoded.mp4"
    run_command.assert_called_once_with(
        [
            "ffmpeg",
            "-i",
            "/tmp/input.mp4",
            "-c:v",
            "libx264",
            "-crf",
            "23",
            "-preset",
            "fast",
            "-c:a",
            "copy",
            "-loglevel",
            "warning",
            "/tmp/input.reencoded.mp4",
        ]
    )


def test_encode_preserves_extensionless_input_names():
    streamer_config = configparser.ConfigParser()
    streamer_config["encoding"] = {}
    completed = subprocess.CompletedProcess(args=[], returncode=0)

    with patch("processor.run_command", return_value=completed):
        output_path = Processor._encode(
            object.__new__(Processor), Path("recording"), streamer_config
        )

    assert output_path == "recording.reencoded"


def test_convert_does_not_build_shorts_from_full_vod():
    processor = object.__new__(Processor)

    with patch("processor.run_command") as run_command:
        output_path = processor._convert("/tmp/recordings/input.ts")

    assert output_path == "/tmp/recordings/input.mp4"
    run_command.assert_called_once_with(
        [
            "ffmpeg",
            "-i",
            "/tmp/recordings/input.ts",
            "-c",
            "copy",
            "/tmp/recordings/input.mp4",
            "-loglevel",
            "error",
        ]
    )


def test_process_single_file_passes_shorts_format_to_clips():
    processor = object.__new__(Processor)

    with (
        patch("processor.os.path.exists", return_value=True),
        patch("processor.process_video"),
        patch("processor.generate_clips"),
        patch("processor.process_clips") as process_clips,
        patch("processor.config.getint", return_value=10),
        patch("processor.config.getboolean", return_value=True),
    ):
        processor._process_single_file("/tmp/recordings/input.mp4", "streamer")

    process_clips.assert_called_once_with(
        "/tmp/recordings/input.mp4",
        "/tmp/recordings/clips",
        "/tmp/recordings/top_clips_one.json",
        min_score=0,
        shorts_format=True,
    )


@pytest.mark.parametrize(
    ("input_path", "expected_output"),
    [
        ("recording.ts", "recording.mp4"),
        ("/tmp/archive.name.mkv", "/tmp/archive.name.mp4"),
        ("/tmp/extensionless", "/tmp/extensionless.mp4"),
    ],
)
def test_convert_builds_output_path_from_input_name(input_path, expected_output):
    processor = object.__new__(Processor)

    with patch("processor.run_command") as run_command:
        output_path = processor._convert(input_path)

    assert output_path == expected_output
    assert run_command.call_args.args[0][-3:] == [expected_output, "-loglevel", "error"]


def test_encode_uses_default_options():
    streamer_config = configparser.ConfigParser()
    streamer_config["encoding"] = {}
    completed = subprocess.CompletedProcess(args=[], returncode=0)

    with patch("processor.run_command", return_value=completed) as run_command:
        output_path = Processor._encode(
            object.__new__(Processor), "/tmp/input.mp4", streamer_config
        )

    assert output_path == "/tmp/input.reencoded.mp4"
    assert run_command.call_args.args[0] == [
        "ffmpeg",
        "-i",
        "/tmp/input.mp4",
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
        "/tmp/input.reencoded.mp4",
    ]


def test_encode_returns_none_when_ffmpeg_fails():
    streamer_config = configparser.ConfigParser()
    streamer_config["encoding"] = {}
    completed = subprocess.CompletedProcess(
        args=[], returncode=1, stderr="encoding failed"
    )

    with patch("processor.run_command", return_value=completed):
        output_path = Processor._encode(
            object.__new__(Processor), "/tmp/input.mp4", streamer_config
        )

    assert output_path is None


def test_encode_returns_none_when_command_raises():
    streamer_config = configparser.ConfigParser()
    streamer_config["encoding"] = {}

    with patch("processor.run_command", side_effect=OSError("ffmpeg missing")):
        output_path = Processor._encode(
            object.__new__(Processor), "/tmp/input.mp4", streamer_config
        )

    assert output_path is None
