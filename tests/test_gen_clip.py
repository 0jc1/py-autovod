import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.modules.pop("gen_clip", None)

from gen_clip import (  # noqa: E402
    _convert_clip_to_shorts,
    _shorts_output_path,
    chunk_list,
    extract_clip,
    load_clips,
    parse_clip_data,
    process_chunk,
)


def valid_clip():
    return {
        "name": "Great clip",
        "start": 10,
        "end": 20,
        "score": 9,
        "factors": "engaging",
        "platforms": "shorts",
    }


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


@pytest.mark.parametrize(
    ("values", "chunk_size", "expected"),
    [
        ([], 3, []),
        ([1, 2, 3, 4], 2, [[1, 2], [3, 4]]),
        ([1, 2, 3, 4, 5], 2, [[1, 2], [3, 4], [5]]),
        ([1, 2], 5, [[1, 2]]),
        ([1, 2, 3], 1, [[1], [2], [3]]),
    ],
)
def test_chunk_list(values, chunk_size, expected):
    assert chunk_list(values, chunk_size) == expected


def test_chunk_list_rejects_zero_chunk_size():
    with pytest.raises(ValueError):
        chunk_list([1, 2, 3], 0)


def test_load_clips_reads_json_payload(tmp_path):
    clips = [valid_clip()]
    clips_path = tmp_path / "clips.json"
    clips_path.write_text(json.dumps(clips))

    assert load_clips(str(clips_path)) == clips


def test_load_clips_reports_missing_file(tmp_path):
    missing_path = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError, match="Clips file not found"):
        load_clips(str(missing_path))


def test_load_clips_reports_invalid_json(tmp_path):
    clips_path = tmp_path / "clips.json"
    clips_path.write_text("not-json")

    with pytest.raises(ValueError, match="Invalid JSON format"):
        load_clips(str(clips_path))


def test_process_chunk_parses_ranked_results():
    parsed_clips = [valid_clip()]

    with (
        patch("gen_clip.rank_clips_chunk", return_value="ranked") as rank,
        patch("gen_clip.parse_clip_data", return_value=parsed_clips) as parse,
    ):
        result = process_chunk(([{"text": "clip"}], 3))

    assert result == parsed_clips
    rank.assert_called_once_with([{"text": "clip"}])
    parse.assert_called_once_with("ranked")


def test_process_chunk_returns_empty_when_ranking_returns_nothing():
    with patch("gen_clip.rank_clips_chunk", return_value=""):
        assert process_chunk(([{"text": "clip"}], 3)) == []


def test_process_chunk_returns_empty_when_ranking_raises():
    with patch("gen_clip.rank_clips_chunk", side_effect=RuntimeError("offline")):
        assert process_chunk(([{"text": "clip"}], 3)) == []


@pytest.mark.parametrize("input_string", [None, ""])
def test_parse_clip_data_returns_empty_for_empty_input(input_string):
    assert parse_clip_data(input_string) == []


def test_parse_clip_data_accepts_plain_json():
    clip = valid_clip()

    assert parse_clip_data(json.dumps({"clips": [clip]})) == [clip]


def test_parse_clip_data_accepts_markdown_fenced_json():
    clip = valid_clip()
    payload = f"```json\n{json.dumps({'clips': [clip]})}\n```"

    assert parse_clip_data(payload) == [clip]


@pytest.mark.parametrize(
    "missing_key", ["name", "start", "end", "score", "factors", "platforms"]
)
def test_parse_clip_data_filters_clips_missing_required_keys(missing_key):
    complete_clip = valid_clip()
    incomplete_clip = valid_clip()
    incomplete_clip.pop(missing_key)
    payload = json.dumps({"clips": [incomplete_clip, complete_clip]})

    assert parse_clip_data(payload) == [complete_clip]


@pytest.mark.parametrize("payload", ["{", "not-json", '{"clips": [}'])
def test_parse_clip_data_returns_empty_for_malformed_json(payload):
    assert parse_clip_data(payload) == []


@pytest.mark.parametrize(
    ("input_path", "expected_path"),
    [
        ("clip.mp4", "clip_shorts.mp4"),
        ("/tmp/archive.name.mov", "/tmp/archive.name_shorts.mp4"),
        ("extensionless", "extensionless_shorts.mp4"),
    ],
)
def test_shorts_output_path(input_path, expected_path):
    assert _shorts_output_path(input_path) == expected_path


def test_convert_clip_to_shorts_builds_ffmpeg_command():
    completed = subprocess.CompletedProcess(args=[], returncode=0)

    with patch("gen_clip.run_command", return_value=completed) as run_command:
        result, output_path = _convert_clip_to_shorts("clip.mp4")

    assert result is completed
    assert output_path == "clip_shorts.mp4"
    assert run_command.call_args.args[0] == [
        "ffmpeg",
        "-y",
        "-i",
        "clip.mp4",
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "clip_shorts.mp4",
    ]


def test_extract_clip_returns_failure_when_ffmpeg_fails(tmp_path):
    completed = subprocess.CompletedProcess(args=[], returncode=1)

    with patch("gen_clip.run_command", return_value=completed):
        success, error = extract_clip("vod.mp4", tmp_path, valid_clip())

    assert success is False
    assert error == "FFmpeg failed with code 1"


@pytest.mark.parametrize(
    ("name", "expected_filename"),
    [
        ("folder/name", "foldername.mp4"),
        ("🔥Highlight", "Highlight.mp4"),
        ('"Quoted"', "Quoted.mp4"),
    ],
)
def test_extract_clip_sanitizes_filename(tmp_path, name, expected_filename):
    completed = subprocess.CompletedProcess(args=[], returncode=0)
    clip_data = valid_clip()
    clip_data["name"] = name

    with (
        patch("gen_clip.run_command", return_value=completed) as run_command,
        patch("gen_clip.os.path.exists", return_value=True),
    ):
        success, output_file = extract_clip("vod.mp4", tmp_path, clip_data)

    expected_output = str(Path(tmp_path) / expected_filename)
    assert success is True
    assert output_file == expected_output
    assert run_command.call_args.args[0][-1] == expected_output
