import os
import platform
import subprocess
from configparser import ConfigParser
from utils import run_command
from loguru import logger

YOUTUBE_UPLOADER_LINUX = "/root/youtubeuploader/youtubeuploader"
YOUTUBE_UPLOADER_WINDOWS = "C:\\youtubeuploader\\youtubeuploader.exe"


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
    

def upload_rclone(filename: str, config: ConfigParser) -> None:
    remote = config.get("rclone", "remote")
    directory = config.get("rclone", "directory")
    save_locally = config.getboolean("local", "save_locally", fallback=True)

    # Build remote destination path
    filename_only = os.path.basename(filename)
    remote_path = f"{remote}:{directory}/{filename_only}"

    # Copy or move option
    command_name = "copyto" if save_locally else "moveto"

    # Build the rclone command
    command = ["rclone", command_name, filename, remote_path]

    logger.info(f"Running rclone command: {' '.join(command)}")

    # Run rclone and stream stderr to the logger
    process = subprocess.Popen(
        command,
        stderr=subprocess.PIPE,
        text=True
    )

    if process.stderr:
        for line in process.stderr:
            logger.info(line.strip())

    process.wait()

    if process.returncode != 0:
        logger.error("rclone upload failed")
        raise RuntimeError("rclone upload failed")

    logger.info("rclone upload completed successfully")

    # Respect save_on_fail setting
    save_on_fail = config.getboolean("local", "save_on_fail", fallback=True)

    if process.returncode != 0 and save_on_fail:
        logger.warning("Upload failed — keeping local file as save_on_fail is True")
    elif process.returncode == 0 and not save_locally:
        try:
            os.remove(filename)
            logger.info(f"Local file deleted after successful upload: {filename}")
        except Exception as e:
            logger.error(f"Could not delete local file: {e}")


