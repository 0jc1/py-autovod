import os
import sys
import types
from unittest.mock import patch

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
sys.modules.setdefault("uploader", uploader)

from processor import Processor


def test_convert_builds_valid_shorts_ffmpeg_command():
    processor = object.__new__(Processor)

    with patch("processor.MIN_DURATION", 60), patch("processor.run_command") as run_command:
        output_path = processor._convert("/tmp/recordings/input.ts")

    assert output_path == "/tmp/recordings/input.mp4"
    assert run_command.call_args_list[1].args[0] == [
        "ffmpeg",
        "-i",
        "/tmp/recordings/input.mp4",
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1",
        "-c",
        "copy",
        "/tmp/recordings/shorts_input.mp4",
        "-loglevel",
        "error",
    ]
