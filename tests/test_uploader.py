import configparser
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Other tests install a lightweight uploader stub in sys.modules. Drop it so we
# load the real module under test (ModuleType stubs have no __file__/Uploader).
sys.modules.pop("uploader", None)

import uploader as uploader_mod  # noqa: E402
from uploader import Uploader  # noqa: E402


@pytest.fixture(autouse=True)
def reset_uploader_singleton(tmp_path):
    """Each test gets a fresh Uploader singleton with no auto-started worker."""
    uploader_mod.Uploader._instance = None
    # Avoid the module-level singleton from interfering with assertions.
    queue_path = tmp_path / "upload_queue.json"
    instance = Uploader(
        queue_path=str(queue_path),
        max_attempts=5,
        base_backoff_seconds=0.01,
        auto_start=False,
    )
    yield instance
    instance.stop(timeout=1.0)
    uploader_mod.Uploader._instance = None


def _streamer_config(
    service="youtube", save_on_fail=False, save_locally=True, max_attempts=5
):
    cfg = configparser.ConfigParser()
    cfg["upload"] = {
        "upload": "true",
        "service": service,
        "save_on_fail": str(save_on_fail).lower(),
        "max_attempts": str(max_attempts),
    }
    cfg["local"] = {"save_locally": str(save_locally).lower()}
    cfg["rclone"] = {"remote": "remote", "directory": "vods"}
    return cfg


def test_retry_after_transient_failure_then_success(tmp_path, reset_uploader_singleton):
    """Simulated 503 then success is retried and does not lose the file job."""
    video = tmp_path / "vod.mp4"
    video.write_bytes(b"data")

    attempts = {"n": 0}

    def flaky_upload(filename, service, options):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("HTTP 503 Service Unavailable")
        return None

    worker = reset_uploader_singleton
    worker._upload_fn = flaky_upload
    worker.enqueue(
        filename=str(video),
        service="youtube",
        streamer_config=_streamer_config(max_attempts=5),
    )

    # Drain the queue on this thread (no background worker).
    item = worker.queue.get(timeout=1)
    worker._handle_item(item)
    # First failure re-queues.
    assert worker.queue.qsize() == 1
    item2 = worker.queue.get(timeout=1)
    worker._handle_item(item2)

    assert attempts["n"] == 2
    assert worker.queue.qsize() == 0
    assert video.exists()


def test_save_on_fail_keeps_file_after_exhausted_retries(
    tmp_path, reset_uploader_singleton
):
    video = tmp_path / "vod.mp4"
    video.write_bytes(b"data")

    def always_fail(filename, service, options):
        raise RuntimeError("HTTP 503 Service Unavailable")

    worker = reset_uploader_singleton
    worker._upload_fn = always_fail
    worker.max_attempts = 3
    worker.base_backoff_seconds = 0.001
    worker.enqueue(
        filename=str(video),
        streamer_config=_streamer_config(
            save_on_fail=True, save_locally=False, max_attempts=3
        ),
    )

    # Process until permanent failure (3 attempts).
    for _ in range(3):
        item = worker.queue.get(timeout=1)
        worker._handle_item(item)

    assert worker.queue.qsize() == 0
    assert video.exists()


def test_delete_after_success_when_not_saving_locally(
    tmp_path, reset_uploader_singleton
):
    video = tmp_path / "vod.mp4"
    video.write_bytes(b"data")
    ts = tmp_path / "vod.ts"
    ts.write_bytes(b"ts")

    worker = reset_uploader_singleton
    worker._upload_fn = lambda *a, **k: None
    worker.enqueue(
        filename=str(video),
        ts_path=str(ts),
        streamer_config=_streamer_config(save_locally=False, save_on_fail=False),
    )
    item = worker.queue.get(timeout=1)
    worker._handle_item(item)

    assert not video.exists()
    assert not ts.exists()


def test_queue_persists_to_disk(tmp_path, reset_uploader_singleton):
    video = tmp_path / "vod.mp4"
    video.write_bytes(b"data")
    worker = reset_uploader_singleton
    worker.enqueue(filename=str(video), streamer_config=_streamer_config())

    assert Path(worker.queue_path).is_file()
    data = Path(worker.queue_path).read_text(encoding="utf-8")
    assert "vod.mp4" in data
    assert worker.pending_count() == 1


def test_restores_queue_on_start(tmp_path):
    import json

    queue_path = tmp_path / "upload_queue.json"
    video = tmp_path / "pending.mp4"
    video.write_bytes(b"x")
    queue_path.write_text(
        json.dumps(
            [
                {
                    "filename": str(video),
                    "service": "youtube",
                    "attempt_count": 1,
                    "save_on_fail": False,
                    "save_locally": True,
                    "max_attempts": 5,
                    "rclone_remote": "",
                    "rclone_directory": "",
                    "ts_path": None,
                }
            ]
        ),
        encoding="utf-8",
    )

    uploader_mod.Uploader._instance = None
    worker = Uploader(
        queue_path=str(queue_path), auto_start=False, base_backoff_seconds=0.01
    )
    try:
        assert worker.pending_count() == 1
        item = worker.queue.get(timeout=1)
        assert item["filename"].endswith("pending.mp4")
        assert item["attempt_count"] == 1
    finally:
        worker.stop(timeout=1.0)
        uploader_mod.Uploader._instance = None
