import queue
import threading
import os
from logger import logger
from settings import config, CLIPCEPTION_ENABLED
from utils import run_command
from uploader import upload_youtube

# clipception
from transcription import process_video, MIN_DURATION
from gen_clip import generate_clips, process_clips


class Processor:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Processor, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.queue = queue.Queue()
            self.worker_thread = threading.Thread(
                target=self._process_queue, daemon=True
            )
            self.processing_event = threading.Event()
            self.stop_event = threading.Event()
            self.initialized = True

            self.worker_thread.start()

    def process(self, video_path, streamer_name, streamer_config):
        """Add a ts file to the queue to be processed with clipception."""
        if not os.path.exists(video_path):
            logger.warning(f"Can't queue video. Path {video_path} does not exist.")
            return

        logger.debug(f"Queuing video: {video_path}")
        self.queue.put((video_path, streamer_name, streamer_config))

    def _process_queue(self):
        """Process queue continuously."""
        while not self.stop_event.is_set():
            try:
                item = self.queue.get(timeout=3)
            except queue.Empty:
                continue

            video_path, streamer_name, streamer_config = item
            new_video_path = video_path
            self.processing_event.set()
            logger.info(f"Processing video: {video_path}")

            try:
                # Convert and re-encode if needed
                new_video_path = self._convert(video_path)

                if streamer_config.getboolean("encoding", "re_encode"):
                    new_video_path = self._encode(new_video_path, streamer_config)

                if new_video_path:
                    logger.debug(f"Video saved locally: {new_video_path}")
            except Exception as e:
                logger.error(f"Error encoding/saving video locally: {str(e)}")

            # Process with clipception
            if CLIPCEPTION_ENABLED and streamer_config.getboolean(
                "clipception", "enabled"
            ):
                self._process_single_file(
                    new_video_path, streamer_name, upload_video=False
                )

            # Upload
            upload = streamer_config.getboolean("upload", "upload")
            if upload:
                try:
                    logger.info("Uploading video.")
                    upload_youtube(os.path.abspath(new_video_path))
                except Exception as e:
                    logger.error(f"Upload failed: {str(e)}")

            logger.info(f"Finished processing: {new_video_path}")

            # Delete files after upload if not set to save locally
            save_locally = streamer_config.getboolean(
                "local", "save_locally", fallback=True
            )

            if not save_locally:
                logger.info(
                    "Deleting video files after upload (save_locally is disabled)"
                )
                self._delete_video_files(video_path, new_video_path)

            self.queue.task_done()
            self.processing_event.clear()

    def stop(self):
        """Signal the worker thread to stop"""
        self.stop_event.set()
        self.worker_thread.join()

    def _delete_video_files(self, ts_path, mp4_path):
        try:
            # Delete the .ts file if it exists
            if os.path.exists(ts_path):
                os.remove(ts_path)
                logger.info(f"Deleted .ts file: {ts_path}")

            # Delete the .mp4 file if it exists
            if os.path.exists(mp4_path):
                os.remove(mp4_path)
                logger.info(f"Deleted .mp4 file: {mp4_path}")

        except Exception as e:
            logger.error(f"Error deleting video files: {str(e)}")

    def _convert(self, input_path: str) -> str:
        """Converts a file to a new format using ffmpeg."""

        output_path = os.path.splitext(input_path)[0] + ".mp4"

        command = [
            "ffmpeg",
            "-i",
            input_path,
            "-c",
            "copy",
            output_path,
            "-loglevel",
            "error",
        ]
        run_command(command)

        # Shorts video format
        if MIN_DURATION < 130:
            command = [
                "ffmpeg",
                "-i",
                output_path,
                '-vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"'
                "-c",
                "copy",
                "s" + output_path,
                "-loglevel",
                "error",
            ]
            run_command(command)

        return output_path

    def _encode(self, video_path, streamer_config):
        try:
            output_path = ""
            codec = streamer_config.get("encoding", "codec", fallback="libx265")
            crf = streamer_config.get("encoding", "crf", fallback="25")
            preset = streamer_config.get("encoding", "preset", fallback="medium")
            log_level = streamer_config.get("encoding", "log", fallback="error")

            # Build FFmpeg command
            ffmpeg_cmd = [
                "ffmpeg",
                "-i",
                video_path,
                "-c:v",
                codec,
                "-crf",
                crf,
                "-preset",
                preset,
                "-c:a",
                "copy",  # Copy audio stream
                "-loglevel",
                log_level,
                output_path,
            ]

            # Execute FFmpeg command
            logger.info(f"Re-encoding video with FFmpeg: {' '.join(ffmpeg_cmd)}")
            result = run_command(ffmpeg_cmd)

            if result.returncode != 0:
                logger.error(f"FFmpeg encoding failed: {result.stderr}")
                return None

            logger.success(f"Video saved locally: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error encoding/saving video locally: {str(e)}")
            return None

    def _process_single_file(self, video_path, streamer_name, upload_video=False):
        """Process a video file with clipception to generate clips."""
        try:
            num_clips = config.getint("clipception", "num_clips", fallback=10)
            min_score = 0  # Default minimum score threshold
            chunk_size = 10

            logger.info(f"Processing video: {video_path}")

            # Ensure the video file exists
            if not os.path.exists(video_path):
                logger.error(f"Error: Video file {video_path} not found")
                return

            # Get file information
            filename_without_ext = os.path.splitext(os.path.basename(video_path))[0]
            output_dir = os.path.dirname(video_path)

            # Step 1: Run enhanced transcription
            logger.info("STEP 1: Generating enhanced transcription...")

            try:
                process_video(video_path)
            except Exception as e:
                logger.error(f"Error during transcription: {str(e)}")
                return

            transcription_json = os.path.join(
                output_dir, f"{filename_without_ext}.enhanced_transcription.json"
            )
            if not os.path.exists(transcription_json):
                logger.error(
                    f"Error: Expected transcription file {transcription_json} was not generated"
                )
                return

            # Step 2: Generate clips JSON using GPU acceleration
            logger.info("STEP 2: Processing transcription for clip selection...")

            output_file = os.path.join(output_dir, "top_clips_one.json")

            try:
                generate_clips(
                    transcription_json,
                    output_file,
                    num_clips=num_clips,
                    chunk_size=chunk_size,
                )
            except Exception as e:
                logger.error(f"Error during clip generation: {str(e)}")
                return

            if not os.path.exists(output_file):
                logger.error(f"Error: Top clips file {output_file} was not generated")
                return

            # Step 3: Extract video clips
            logger.info("STEP 3: Extracting clips...")
            clips_output_dir = os.path.join(output_dir, "clips")

            try:
                process_clips(
                    video_path, clips_output_dir, output_file, min_score=min_score
                )
            except Exception as e:
                logger.error(f"Error during clip extraction: {str(e)}")
                return

            logger.success("All processing completed successfully! Generated files:")
            logger.info(f"1. Transcription: {transcription_json}")
            logger.info(f"2. Clip selections: {output_file}")
            logger.info(f"3. Video clips: {clips_output_dir}/")

        except Exception as e:
            logger.error(f"Error processing video {video_path}: {str(e)}")


processor = Processor()
