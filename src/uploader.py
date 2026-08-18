import json
import os
import platform
import queue
import subprocess
import threading
import time
from typing import Any

from logger import logger
from utils import run_command

YOUTUBE_UPLOADER_LINUX = "/root/youtubeuploader/youtubeuploader"
YOUTUBE_UPLOADER_WINDOWS = "C:\\youtubeuploader\\youtubeuploader.exe"

# Pending uploads survive process restarts.
DEFAULT_QUEUE_PATH = os.path.join("recordings", "upload_queue.json")
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BASE_BACKOFF_SECONDS = 2.0


def upload_youtube(filename: str) -> None:
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"File not found: {filename}")

    if platform.system() == "Windows":
        uploader_path = YOUTUBE_UPLOADER_WINDOWS
        filename = os.path.normpath(filename)
    else:
        uploader_path = YOUTUBE_UPLOADER_LINUX

    if not os.path.isfile(uploader_path):
        cwd_uploader = os.path.join(os.getcwd(), os.path.basename(uploader_path))
        if os.path.isfile(cwd_uploader):
            uploader_path = cwd_uploader
        else:
            raise FileNotFoundError(
                f"YouTube uploader not found in either {uploader_path} or {cwd_uploader}"
            )

    command = [uploader_path, "-filename", filename]
    result = run_command(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = result.stdout.decode().strip()
    if stdout:
        logger.info(stdout)

    if result.returncode != 0:
        raise RuntimeError("youtubeuploader failed to upload the file")


def upload_rclone(filename: str, remote: str, directory: str = "") -> None:
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"File not found: {filename}")
    if not remote:
        raise ValueError("rclone remote is not configured")

    dest = f"{remote}:{directory}" if directory else f"{remote}:"
    command = ["rclone", "copy", filename, dest]
    result = run_command(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stderr = result.stderr.decode().strip() if result.stderr else ""
    if result.returncode != 0:
        raise RuntimeError(stderr or "rclone failed to upload the file")


def perform_upload(filename: str, service: str, options: dict[str, Any]) -> None:
    service = (service or "youtube").strip().lower()
    if service == "youtube":
        upload_youtube(filename)
    elif service == "rclone":
        upload_rclone(
            filename,
            remote=options.get("rclone_remote", ""),
            directory=options.get("rclone_directory", ""),
        )
    else:
        raise RuntimeError(f"Unsupported upload service: {service}")


class Uploader:
    """Background upload worker with retries and a disk-backed queue."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Uploader, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        queue_path: str = DEFAULT_QUEUE_PATH,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        base_backoff_seconds: float = DEFAULT_BASE_BACKOFF_SECONDS,
        auto_start: bool = True,
    ):
        if hasattr(self, "initialized"):
            return

        self.queue_path = queue_path
        self.max_attempts = max(1, int(max_attempts))
        self.base_backoff_seconds = float(base_backoff_seconds)
        self.queue: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._upload_fn = perform_upload
        self._auto_start = auto_start
        self.initialized = True

        self._load_persisted_queue()
        if auto_start and self.queue.qsize() > 0:
            self._ensure_worker()

    def enqueue(
        self,
        filename: str,
        service: str = "youtube",
        streamer_config=None,
        attempt_count: int = 0,
        ts_path: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        """Queue a file for upload. Does not block the caller."""
        abs_path = os.path.abspath(filename)
        if not os.path.exists(abs_path):
            logger.warning(f"Can't queue upload. Path {abs_path} does not exist.")
            return

        item = self._build_item(
            filename=abs_path,
            service=service,
            streamer_config=streamer_config,
            attempt_count=attempt_count,
            ts_path=ts_path,
            options=options,
        )
        self.queue.put(item)
        self._persist_queue()
        if self._auto_start:
            self._ensure_worker()
        logger.info(
            f"Queued upload: {abs_path} (service={item['service']}, attempt={item['attempt_count']})"
        )

    def _ensure_worker(self) -> None:
        with self._lock:
            if self.worker_thread is not None and self.worker_thread.is_alive():
                return
            self.stop_event.clear()
            self.worker_thread = threading.Thread(
                target=self._process_queue, name="uploader", daemon=True
            )
            self.worker_thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the worker to stop and wait briefly for it."""
        self.stop_event.set()
        thread = self.worker_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._persist_queue()

    def pending_count(self) -> int:
        return self.queue.qsize()

    def _build_item(
        self,
        filename: str,
        service: str,
        streamer_config,
        attempt_count: int,
        ts_path: str | None,
        options: dict[str, Any] | None,
    ) -> dict[str, Any]:
        opts = dict(options or {})
        if streamer_config is not None:
            service = streamer_config.get("upload", "service", fallback=service)
            opts.setdefault(
                "save_on_fail",
                streamer_config.getboolean("upload", "save_on_fail", fallback=False),
            )
            opts.setdefault(
                "save_locally",
                streamer_config.getboolean("local", "save_locally", fallback=True),
            )
            opts.setdefault(
                "max_attempts",
                streamer_config.getint(
                    "upload", "max_attempts", fallback=self.max_attempts
                ),
            )
            opts.setdefault(
                "rclone_remote", streamer_config.get("rclone", "remote", fallback="")
            )
            opts.setdefault(
                "rclone_directory",
                streamer_config.get("rclone", "directory", fallback=""),
            )
        else:
            opts.setdefault("save_on_fail", False)
            opts.setdefault("save_locally", True)
            opts.setdefault("max_attempts", self.max_attempts)

        return {
            "filename": filename,
            "service": (service or "youtube").strip().lower(),
            "attempt_count": int(attempt_count),
            "ts_path": os.path.abspath(ts_path) if ts_path else None,
            "save_on_fail": bool(opts.get("save_on_fail", False)),
            "save_locally": bool(opts.get("save_locally", True)),
            "max_attempts": max(1, int(opts.get("max_attempts", self.max_attempts))),
            "rclone_remote": opts.get("rclone_remote", "") or "",
            "rclone_directory": opts.get("rclone_directory", "") or "",
        }

    def _process_queue(self) -> None:
        while not self.stop_event.is_set():
            try:
                item = self.queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                self._handle_item(item)
            except Exception:
                logger.exception("Unexpected error in upload worker")
            finally:
                self.queue.task_done()
                self._persist_queue()

    def _handle_item(self, item: dict[str, Any]) -> None:
        filename = item["filename"]
        service = item["service"]
        attempt = int(item.get("attempt_count", 0))
        max_attempts = int(item.get("max_attempts", self.max_attempts))

        if not os.path.isfile(filename):
            logger.error(f"Skipping upload; file missing: {filename}")
            return

        try:
            logger.info(
                f"Uploading {filename} via {service} (attempt {attempt + 1}/{max_attempts})"
            )
            self._upload_fn(
                filename,
                service,
                {
                    "rclone_remote": item.get("rclone_remote", ""),
                    "rclone_directory": item.get("rclone_directory", ""),
                },
            )
        except Exception as exc:
            logger.exception(f"Upload failed for {filename}: {exc}")
            next_attempt = attempt + 1
            if next_attempt < max_attempts:
                delay = self.base_backoff_seconds * (2**attempt)
                logger.info(
                    f"Retrying upload of {filename} in {delay:.1f}s "
                    f"(attempt {next_attempt + 1}/{max_attempts})"
                )
                if self.stop_event.wait(delay):
                    # Shutting down: put item back for next start.
                    item["attempt_count"] = next_attempt
                    self.queue.put(item)
                    return
                item["attempt_count"] = next_attempt
                self.queue.put(item)
                return

            self._on_final_failure(item)
            return

        logger.success(f"Upload finished: {filename}")
        self._on_success(item)

    def _on_success(self, item: dict[str, Any]) -> None:
        if item.get("save_locally", True):
            return
        logger.info("Deleting local files after successful upload (save_locally=false)")
        self._delete_files(item.get("ts_path"), item["filename"])

    def _on_final_failure(self, item: dict[str, Any]) -> None:
        filename = item["filename"]
        save_on_fail = item.get("save_on_fail", False)
        save_locally = item.get("save_locally", True)

        if save_on_fail:
            logger.error(
                f"Upload failed permanently; keeping file because save_on_fail=true: {filename}"
            )
            return

        if save_locally:
            logger.error(
                f"Upload failed permanently; keeping file because save_locally=true: {filename}"
            )
            return

        logger.error(
            f"Upload failed permanently; deleting local files (save_on_fail=false, save_locally=false): {filename}"
        )
        self._delete_files(item.get("ts_path"), filename)

    def _delete_files(self, ts_path: str | None, video_path: str) -> None:
        for path in (ts_path, video_path):
            if not path:
                continue
            try:
                if os.path.exists(path):
                    os.remove(path)
                    logger.info(f"Deleted file: {path}")
            except Exception:
                logger.exception(f"Error deleting file: {path}")

    def _snapshot_queue(self) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self.queue.queue)
        return items

    def _persist_queue(self) -> None:
        items = self._snapshot_queue()
        directory = os.path.dirname(self.queue_path)
        try:
            if directory:
                os.makedirs(directory, exist_ok=True)
            tmp_path = f"{self.queue_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(items, handle, indent=2)
            os.replace(tmp_path, self.queue_path)
        except Exception:
            logger.exception(f"Failed to persist upload queue to {self.queue_path}")

    def _load_persisted_queue(self) -> None:
        if not os.path.isfile(self.queue_path):
            return
        try:
            with open(self.queue_path, encoding="utf-8") as handle:
                items = json.load(handle)
            if not isinstance(items, list):
                logger.warning(f"Ignoring invalid upload queue file: {self.queue_path}")
                return
            restored = 0
            for raw in items:
                if not isinstance(raw, dict) or "filename" not in raw:
                    continue
                item = {
                    "filename": raw["filename"],
                    "service": str(raw.get("service", "youtube")).strip().lower(),
                    "attempt_count": int(raw.get("attempt_count", 0)),
                    "ts_path": raw.get("ts_path"),
                    "save_on_fail": bool(raw.get("save_on_fail", False)),
                    "save_locally": bool(raw.get("save_locally", True)),
                    "max_attempts": max(
                        1, int(raw.get("max_attempts", self.max_attempts))
                    ),
                    "rclone_remote": raw.get("rclone_remote", "") or "",
                    "rclone_directory": raw.get("rclone_directory", "") or "",
                }
                self.queue.put(item)
                restored += 1
            if restored:
                logger.info(
                    f"Restored {restored} pending upload(s) from {self.queue_path}"
                )
        except Exception:
            logger.exception(f"Failed to load upload queue from {self.queue_path}")


# Module-level singleton used by processor / stream_manager.
# Tests reset Uploader._instance and construct their own instances.
def get_uploader() -> Uploader:
    return Uploader()


uploader = get_uploader()
